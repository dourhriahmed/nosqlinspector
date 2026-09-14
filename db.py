import os
from pymongo import MongoClient
from couchbase.cluster import Cluster, PasswordAuthenticator
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

db_type = os.getenv("DATABASE_TYPE")
db_name = os.getenv("DATABASE_NAME")

if db_type == "mongodb":
    mongodb_uri = os.getenv("MONGODB_URI")
    mongo_client = MongoClient(mongodb_uri)
    db = mongo_client[db_name]

elif db_type == "couchbase":
    couchbase_uri = os.getenv("COUCHBASE_URI")
    couchbase_user = os.getenv("COUCHBASE_USER")
    couchbase_password = os.getenv("COUCHBASE_PASSWORD")
    cluster = Cluster(couchbase_uri)
    cluster.authenticate(PasswordAuthenticator(couchbase_user, couchbase_password))
    db = cluster.bucket(db_name)

elif db_type == "firestore":
    firestore_project = os.getenv("FIRESTORE_PROJECT")
    db = firestore.Client(project=firestore_project).collection(db_name)