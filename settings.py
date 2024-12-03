from dotenv import load_dotenv
import os

load_dotenv()

MONGO_USER = os.getenv("MONGO-USER")
MONGO_PASS = os.getenv("MONGO-PASS")
MONGO_ADDRESS = os.getenv("MONGO-ADDRESS")

