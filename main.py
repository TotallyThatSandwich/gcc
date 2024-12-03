import pymongo as pm
import settings

def main():
    DB = pm.MongoClient(settings.MONGO_ADDRESS, username=settings.MONGO_USER, password=settings.MONGO_PASS)
    print(DB.list_database_names())

if __name__ == "__main__":
        main()
