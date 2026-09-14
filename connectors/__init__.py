from connectors.mongodb_connector import MongoDBConnector
from connectors.couchdb_connector import CouchDBConnector
from connectors.firestore_connector import FirestoreConnector

CONNECTORS = {
    "MongoDB": MongoDBConnector,
    "CouchDB": CouchDBConnector,
    "Firebase Firestore": FirestoreConnector,
}