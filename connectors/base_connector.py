# connectors/base_connector.py
from abc import ABC, abstractmethod

class BaseConnector(ABC):

    @abstractmethod
    def connect(self, **kwargs) -> bool:
        """Établir la connexion. Retourne True si succès."""
        pass

    @abstractmethod
    def get_collections(self, db_name: str) -> list:
        """Retourne la liste des collections/tables."""
        pass

    @abstractmethod
    def get_documents(self, db_name: str, collection_name: str, limit=None) -> list:
        """Retourne les documents sous forme de liste de dicts Python."""
        pass

    @abstractmethod
    def close(self):
        """Fermer la connexion."""
        pass

    def start_listener(self, db_name: str, collection_name: str, callback) -> bool:
        """Démarre un écouteur de changements en arrière-plan.
        Appelle `callback()` à chaque modification détectée.
        Retourne True si l'écouteur est démarré avec succès.
        """
        return False

    def stop_listener(self, collection_name: str):
        """Arrête l'écouteur de changements pour la collection spécifiée."""
        pass

    def stop_all_listeners(self):
        """Arrête tous les écouteurs de changements actifs."""
        pass