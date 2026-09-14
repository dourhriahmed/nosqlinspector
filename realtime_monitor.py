# realtime_monitor.py
import threading
import time

_lock = threading.Lock()

# Registry mapping session_id to session state details:
# {
#     session_id: {
#         "connector": connector_instance,
#         "db_name": db_name,
#         "active_listeners": set()  # set of collection names currently being watched
#     }
# }
session_registry = {}

# Registry mapping session_id to set of collection names that have changed:
# {
#     session_id: set([col1, col2, ...])
# }
session_changes = {}

def register_change(session_id, collection_name):
    """Signale qu'une modification a eu lieu dans une collection pour une session donnée."""
    with _lock:
        if session_id not in session_changes:
            session_changes[session_id] = set()
        session_changes[session_id].add(collection_name)
        print(f"[realtime_monitor] Changement enregistré pour la session {session_id}, collection: {collection_name}")

def get_changed_collections(session_id) -> set:
    """Récupère la liste des collections modifiées depuis le dernier appel et réinitialise le set."""
    with _lock:
        changes = session_changes.get(session_id, set())
        if changes:
            session_changes[session_id] = set()
        return changes

def sync_listeners(session_id, connector, db_name, selected_collections):
    """
    Synchronise les écouteurs de changements en arrière-plan pour correspondre
    aux collections sélectionnées par l'utilisateur.
    """
    if not session_id or not connector:
        return

    with _lock:
        # Initialiser la session si elle n'existe pas
        if session_id not in session_registry:
            session_registry[session_id] = {
                "connector": None,
                "db_name": None,
                "active_listeners": set()
            }

        session_state = session_registry[session_id]

        # Si le connecteur ou la base de données a changé, on nettoie tout avant de recommencer
        if session_state["connector"] != connector or session_state["db_name"] != db_name:
            print(f"[realtime_monitor] Nouveau connecteur ou nouvelle BDD détectés pour la session {session_id}. Réinitialisation...")
            if session_state["connector"]:
                try:
                    session_state["connector"].stop_all_listeners()
                except Exception as e:
                    print(f"[realtime_monitor] Erreur lors de l'arrêt des anciens écouteurs: {e}")
            session_state["connector"] = connector
            session_state["db_name"] = db_name
            session_state["active_listeners"] = set()
            if session_id in session_changes:
                session_changes[session_id] = set()

        # Identifier les écouteurs à arrêter (ceux qui ne sont plus sélectionnés)
        to_stop = session_state["active_listeners"] - set(selected_collections)
        for col in to_stop:
            print(f"[realtime_monitor] Arrêt de l'écouteur pour la session {session_id}, collection: {col}")
            try:
                connector.stop_listener(col)
            except Exception as e:
                print(f"[realtime_monitor] Erreur arrêt écouteur {col}: {e}")
            session_state["active_listeners"].remove(col)

        # Identifier les écouteurs à démarrer (ceux nouvellement sélectionnés)
        to_start = set(selected_collections) - session_state["active_listeners"]
        for col in to_start:
            print(f"[realtime_monitor] Démarrage de l'écouteur pour la session {session_id}, collection: {col}")
            # Callback de notification
            # On utilise une fonction lambda pour capturer la session et la collection courantes
            def make_callback(sid, cname):
                return lambda: register_change(sid, cname)
            
            try:
                success = connector.start_listener(db_name, col, make_callback(session_id, col))
                if success:
                    session_state["active_listeners"].add(col)
                else:
                    print(f"[realtime_monitor] Impossible de démarrer l'écouteur pour {col}")
            except Exception as e:
                print(f"[realtime_monitor] Exception lors du démarrage de l'écouteur pour {col}: {e}")

def cleanup_session(session_id):
    """Arrête tous les écouteurs d'une session et nettoie ses états."""
    with _lock:
        if session_id in session_registry:
            session_state = session_registry.pop(session_id)
            connector = session_state["connector"]
            if connector:
                print(f"[realtime_monitor] Nettoyage complet des écouteurs pour la session {session_id}")
                try:
                    connector.stop_all_listeners()
                except Exception as e:
                    print(f"[realtime_monitor] Erreur lors du nettoyage de la session {session_id}: {e}")
        session_changes.pop(session_id, None)
