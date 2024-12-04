import pymongo as pm
from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import settings
import binascii
import os
import uuid

client = pm.MongoClient(settings.MONGO_ADDRESS, username=settings.MONGO_USER, password=settings.MONGO_PASS)
db = client["db"]
auth = db["auth"]
users = db["users"]
channels = db["channels"]
messages = db["messages"]

app = Flask(__name__)
cors = CORS(app)

def generate_token():
    generated_token = binascii.hexlify(os.urandom(10)).decode()
    while auth.find_one({ "token": generated_token }) is not None:
        generated_token = binascii.hexlify(os.urandom(10)).decode()
    return generated_token

def generate_user_id():
        generated_id = str(uuid.uuid4())
        while users.find_one({ "userId": generated_id }) is not None:
                generated_id = str(uuid.uuid4())
        return generated_id

#auth
@app.route('/checkauth', methods=['GET'])
def check_auth():
        headers = request.headers
        user = auth.find_one({ "token": headers.get('Authorization') })
        if user is None:
                return jsonify({"error": "Invalid token"}), 401
        return jsonify({"token": user["token"]}), 200

@app.route('/getauth', methods=['POST'])
def post_auth():
        data = request.get_json()
        user = auth.find_one({ "username": data["username"], "passwordHash": data["passwordHash"] })
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
        userId = generate_user_id()
        token = str(generate_token())
        users.insert_one({ "username": data["username"], "email": data["email"], "userId": userId })
        auth.insert_one({ "username": data["username"], "passwordHash": data["passwordHash"], "token": token })
        return jsonify({"token": token}), 201

@app.route('/userfromid/<userId>', methods=['GET'])
def get_user_from_id(userId):
        user = users.find_one({ "userId": userId })
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify({"username": user["username"], "userId": user["userId"]}), 200

@app.route('/userfromname/<userName>', methods=['GET'])
def get_user_from_name(userName):
        user = users.find_one({ "username": userName })
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify({"username": user["username"], "userId": user["userId"]}), 200

@app.route('/users', methods=['GET'])
def get_users():
        users_list = []
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        for user in users.find():
                users_list.append({"username": user["username"], "userId": user["userId"]})
        return jsonify({"users": users_list}), 200

#@app.route('/userfromid/<userId>', methods=['DELETE'])
#def delete_user(userId):
#        user = users.find_one({ "userId": userId })
#        if user is None:
#                return jsonify({"error": "User not found"}), 404
#        users.delete_one({ "userId": userId })
#        return jsonify({"message": "User deleted"}), 200


# channels
@app.route('/channels', methods=['POST'])
def post_channel():
        data = request.get_json()
        channel = channels.find_one({ "channelId": data["channelId"] })
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if channel is not None:
                return jsonify({"error": "Channel already exists"}), 400
        channels.insert_one({"channelId": data["channelId"], "messages": []})
        return jsonify({"channelId": data["channelId"], "messages": []}), 201

@app.route('/channels', methods=['GET'])
def get_channels():
        channels_list = []
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        for channel in channels.find():
                channels_list.append({"channelId": channel["channelId"], "messages": channel["messages"]})
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({ "channelId": channelId })
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        return jsonify({"channelId": channel["channelId"], "messages": channel["messages"]}), 200

#messages
@app.route('/channels/<channelId>/messages', methods=['POST'])
def post_message(channelId):
        data = request.get_json()
        channel = channels.find_one({ "channelId": channelId })
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        messages.insert_one({ "channelId": channelId, "message": data["message"], "timestamp": data["timestamp"], "sentuser": users.find_one({ "userId": data["userId"] }) })
        return jsonify({"message": data["message"]}), 201

@app.route('/channels/<channelId>/messages', methods=['GET'])
def get_messages(channelId):
        channel = channels.find_one({ "channelId": channelId })
        messagelist = []
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        for message in messages.find({}):
                messagelist.append({"channelId" : message["channelId"], "message": message["message"]})
        return jsonify({"messages": channel["messages"]}), 200


if __name__ == "__main__":
        app.run(debug=True)
