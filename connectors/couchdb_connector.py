import couchdb
from connectors.base_connector import BaseConnector

class CouchDBConnector(BaseConnector):

    def __init__(self):
        self.server = None
        self.listeners = {}  # Format: { collection_name: (thread, stop_event) }

    def connect(self, url="http://localhost:5984",
                username="admin", password="admin123", **kwargs) -> bool:
        try:
            self.server = couchdb.Server(url)
            self.server.resource.credentials = (username, password)
            list(self.server)
            return True
        except Exception as e:
            print(f"CouchDB connection error: {e}")
            return False

    def get_collections(self, db_name: str = "") -> list:
        """Retourne toutes les bases CouchDB (= équivalent des collections)"""
        try:
            return [db for db in self.server if not db.startswith("_")]
        except Exception as e:
            print(f"Erreur get_collections CouchDB: {e}")
            return []

    def get_documents(self, db_name: str, collection_name: str, limit=None) -> list:
        """collection_name = nom de la base CouchDB"""
        try:
            db = self.server[collection_name]
            docs = []
            for doc_id in db:
                if doc_id.startswith("_design"):
                    continue  # ignorer les design documents
                doc = dict(db[doc_id])
                doc.pop("_id", None)
                doc.pop("_rev", None)
                docs.append(doc)
                if limit and len(docs) >= limit:
                    break
            return docs
        except Exception as e:
            print(f"Erreur get_documents CouchDB: {e}")
            return []

    def start_listener(self, db_name: str, collection_name: str, callback) -> bool:
        import threading
        import time

        self.stop_listener(collection_name)

        stop_event = threading.Event()

        def watch_loop():
            try:
                db = self.server[collection_name]
                last_seq = "now"
                while not stop_event.is_set():
                    try:
                        # Utiliser longpoll avec un timeout court pour pouvoir s'arrêter rapidement
                        changes = db.changes(feed='longpoll', since=last_seq, timeout=3000)
                        results = changes.get('results', [])
                        if results:
                            callback()
                            last_seq = changes.get('last_seq', last_seq)
                    except Exception:
                        time.sleep(2)
            except Exception as e:
                print(f"Erreur dans le thread écouteur CouchDB pour {collection_name} : {e}")

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
        self.server = None