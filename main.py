import pymongo as pm
import settings
from flask import Flask, jsonify, request
import binascii
import os

client = pm.MongoClient(settings.MONGO_ADDRESS, username=settings.MONGO_USER, password=settings.MONGO_PASS)
db = client["db"]
auth = db["auth"]
users = db["users"]
channels = db["channels"]
messages = db["messages"]

app = Flask(__name__)

def generate_token():
    generated_token = binascii.hexlify(os.urandom(10)).decode()
    while auth.find_one({ "token": generate_token }) is not None:
        generated_token = binascii.hexlify(os.urandom(10)).decode()
    return generated_token

#auth
@app.route('/checkauth', methods=['GET'])
def check_auth():
        data = request.get_json()
        user = auth.find_one({ "token": data["token"] })
        if user is None:
                return jsonify({"error": "Invalid token"}), 401
        if user["username"] != data["username"]:
                return jsonify({"error": "Invalid token"}), 401
        return jsonify({"token": user["token"]}), 200

@app.route('/getauth', methods=['GET'])
def post_auth():
        data = request.get_json()
        user = auth.find_one({ "username": data["username"], "passwordHash": data["password"] })
        if user is None:
                return jsonify({"error": "Invalid credentials"}), 401
        return jsonify({"token": user["token"]}), 200


# user
@app.route('/user/new', methods=['POST'])
def post_user():
        data = request.get_json()
        user = users.find_one({ "username": data["username"] })
        if user is not None:
                return jsonify({"error": "User already exists"}), 400
        users.insert_one({ "username": data["username"], "userId": data["userId"] })
        auth.insert_one({ "username": data["username"], "passwordHash": data["password"], "token": generate_token() })
        return jsonify({"username": data["username"], "userId": data["userId"]}), 201

@app.route('/user/<userId>', methods=['GET'])
def get_user(userId):
        user = users.find_one({ "userId": userId })
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify({"username": user["username"], "userId": user["userId"]}), 200

# channels
@app.route('/channels', methods=['POST'])
def post_channel():
        data = request.get_json()
        channel = channels.find_one({ "channelId": data["channelId"] })
        if channel is not None:
                return jsonify({"error": "Channel already exists"}), 400
        channels.insert_one({"channelId": data["channelId"], "messages": []})
        return jsonify({"channelId": data["channelId"], "messages": []}), 201

@app.route('/channels', methods=['GET'])
def get_channels():
        channels_list = []
        for channel in channels.find():
                channels_list.append({"channelId": channel["channelId"], "messages": channel["messages"]})
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({ "channelId": channelId })
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        return jsonify({"channelId": channel["channelId"], "messages": channel["messages"]}), 200

#messages
@app.route('/channels/<channelId>/messages', methods=['POST'])
def post_message(channelId):
        data = request.get_json()
        channel = channels.find_one({ "channelId": channelId })
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        messages.insert_one({ "channelId": channelId, "message": data["message"], "timestamp": data["timestamp"], "sentuser": users.find_one({ "userId": data["userId"] }) })
        return jsonify({"message": data["message"]}), 201

@app.route('/channels/<channelId>/messages', methods=['GET'])
def get_messages(channelId):
        channel = channels.find_one({ "channelId": channelId })
        messagelist = []
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        for message in messages.find({}):
                messagelist.append({"channelId" : message["channelId"], "message": message["message"]})
        return jsonify({"messages": channel["messages"]}), 200


if __name__ == "__main__":
        app.run(debug=True)
