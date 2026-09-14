# connectors/mongodb_connector.py
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from connectors.base_connector import BaseConnector

class MongoDBConnector(BaseConnector):

    def __init__(self):
        self.client = None
        self.listeners = {}  # Format: { collection_name: (thread, stop_event) }

    def connect(self, uri="mongodb://localhost:27017", **kwargs) -> bool:
        self.client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.client.admin.command("ping")
        return True

    def get_collections(self, db_name: str) -> list:
        try:
            return self.client[db_name].list_collection_names()
        except Exception:
            return []

    def get_documents(self, db_name: str, collection_name: str, limit=None) -> list:
        collection = self.client[db_name][collection_name]
        cursor = collection.find({}, {"_id": 0})
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def start_listener(self, db_name: str, collection_name: str, callback) -> bool:
        import threading
        import time
        from pymongo.errors import PyMongoError

        # Arrêter un écouteur existant s'il y en a un
        self.stop_listener(collection_name)

        stop_event = threading.Event()

        def watch_loop():
            try:
                db = self.client[db_name]
                collection = db[collection_name]

                # Tenter d'utiliser les Change Streams (nécessite un Replica Set)
                try:
                    with collection.watch(max_await_time_ms=1000) as stream:
                        while not stop_event.is_set():
                            change = stream.try_next()
                            if change is not None:
                                callback()
                            time.sleep(0.5)
                except PyMongoError:
                    # Fallback : Si les change streams ne sont pas supportés, on fait du polling du nombre de documents
                    last_count = collection.count_documents({})
                    while not stop_event.is_set():
                        try:
                            current_count = collection.count_documents({})
                            if current_count != last_count:
                                last_count = current_count
                                callback()
                        except Exception:
                            pass
                        
                        # Attendre 5 secondes par petits intervalles pour être réactif à l'arrêt
                        for _ in range(50):
                            if stop_event.is_set():
                                break
                            time.sleep(0.1)
            except Exception as e:
                print(f"Erreur dans le thread écouteur MongoDB pour {collection_name} : {e}")

        thread = threading.Thread(target=watch_loop, daemon=True)
        self.listeners[collection_name] = (thread, stop_event)
        thread.start()
        return True

    def stop_listener(self, collection_name: str):
        if collection_name in self.listeners:
            thread, stop_event = self.listeners.pop(collection_name)
            stop_event.set()
            thread.join(timeout=1.0)

    def stop_all_listeners(self):
        for coll_name in list(self.listeners.keys()):
            self.stop_listener(coll_name)

    def close(self):
        self.stop_all_listeners()
        if self.client:
            self.client.close()