import firebase_admin
from firebase_admin import credentials, firestore
from connectors.base_connector import BaseConnector
import os

class FirestoreConnector(BaseConnector):

    def __init__(self):
        self.db = None
        self.app = None
        self.listeners = {}  # Format: { collection_name: watch_object }

    def connect(self, credentials_path="", **kwargs) -> bool:
        try:
            if firebase_admin._apps:
                firebase_admin.delete_app(firebase_admin.get_app())

            # Priorité 1 : fichier JSON si fourni manuellement
            # Priorité 2 : variable d'environnement GOOGLE_APPLICATION_CREDENTIALS
            # Priorité 3 : chemin par défaut dans le projet
            if credentials_path and os.path.exists(credentials_path):
                cred = credentials.Certificate(credentials_path)
            elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                cred = credentials.ApplicationDefault()
            else:
                # Cherche dans le dossier du projet automatiquement
                default_path = os.path.join(os.path.dirname(__file__), "..", "serviceAccountKey.json")
                if os.path.exists(default_path):
                    cred = credentials.Certificate(default_path)
                else:
                    print("Aucune credentials trouvée.")
                    return False

            self.app = firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            return True

        except Exception as e:
            print(f"Firestore connection error: {e}")
            return False

    def get_collections(self, db_name: str = "") -> list:
        try:
            return [col.id for col in self.db.collections()]
        except Exception as e:
            print(f"Erreur get_collections: {e}")
            return []

    def get_documents(self, db_name: str, collection_name: str, limit=None) -> list:
        try:
            ref = self.db.collection(collection_name)
            docs = ref.limit(limit).stream() if limit else ref.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Erreur get_documents: {e}")
            return []

    def start_listener(self, db_name: str, collection_name: str, callback) -> bool:
        # Arrêter un écouteur existant s'il y en a un
        self.stop_listener(collection_name)

        try:
            col_ref = self.db.collection(collection_name)

            # Éviter de déclencher immédiatement sur l'état initial
            is_initialized = False

            def on_snapshot_callback(col_snapshot, changes, read_time):
                nonlocal is_initialized
                if not is_initialized:
                    is_initialized = True
                    return
                if changes:
                    callback()

            watch = col_ref.on_snapshot(on_snapshot_callback)
            self.listeners[collection_name] = watch
            return True
        except Exception as e:
            print(f"Erreur lors du démarrage de l'écouteur Firestore pour {collection_name} : {e}")
            return False

    def stop_listener(self, collection_name: str):
        if collection_name in self.listeners:
            watch = self.listeners.pop(collection_name)
            try:
                watch.unsubscribe()
            except Exception:
                pass

    def stop_all_listeners(self):
        for coll_name in list(self.listeners.keys()):
            self.stop_listener(coll_name)

    def close(self):
        try:
            self.stop_all_listeners()
            if self.app:
                firebase_admin.delete_app(self.app)
                self.app = None
                self.db = None
        except Exception:
            pass