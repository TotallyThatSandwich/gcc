from dotenv import load_dotenv
import os

load_dotenv(override=True)

MONGO_USER = os.getenv("MONGO-USER")
MONGO_PASS = os.getenv("MONGO-PASS")
MONGO_ADDRESS = os.getenv("MONGO-ADDRESS")

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
AUTH = os.getenv("AUTH")

SERVER = os.getenv("SERVER")
