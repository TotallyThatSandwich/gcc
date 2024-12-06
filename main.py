import pymongo as pm
import json
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, send, emit, Namespace, join_room, leave_room
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
socket = SocketIO(app)

rooms = {}



# Websockets
class chat_room(Namespace):
        """A class to represent a namespace of the websocket. After creating a channel(``chat_room``), methods below are automatically handled as events.\n
        When a user joins a channel, they should be connected to the websocket with the namespace ``/chat_room.channelId`` where the following events are handled.

        Methods: 
                ``check_auth``: Checks if ``auth`` exists in the database.
                        args:
                                auth (str): The token of the user.

                ``create_room``: Creates a room in the channel.
                        args:
                                room (str): The room name for the room to be created.
                
                ``room_exists``: Checks if a room exists in the channel.
                        args:
                                room (str): The room name to check.
        
        Events:
                ``on_send_message``: Sends a message to all users in the channel.

                ``on_receive_message``: Receives a message from a user and sends it to all users in the channel.

                ``on_join_room``: Connects the user to a channel.
                        args:

                ``on_leave_room``: Disconnects the user from a channel.

        Args:
            Namespace (_type_): _description_
        """
        def __init__(self, namespace = None, chat_name = None, permissions:dict = None):
                super().__init__(namespace)
                print(namespace)
                self.channelId = namespace
                self.chat_name = chat_name
                self.permissions = permissions
                self.rooms:dict = {}

        # Basic methods
        def check_auth(self, auth_token) -> bool:
                if not auth.find({ "token": auth_token }):
                        return False
                return True
                        
        def create_room(self, room:str) -> dict:
                """Creates a room dictionary and appends it to ``self.rooms``.

                Args:
                        room (str): name of the room to be created.
                
                Returns:
                        room (dict): A dictionary containing the room name and an empty list of users.
                """
                room = {"name": room, "users": []}
                self.rooms.update({room["name"]: room})
                return room

        def delete_room(self, room:str):
                for i in self.rooms:
                        if i["name"] == room:
                                self.rooms.remove(i)
                                break      
                else:
                        return False
                return True
                

        def room_exists(self, room):
                if self.room in rooms:
                        return True
                return False

        def send_message(self, data):
                room = data['room']
                print(f"user has sent message {data['content']} to room {room}")
                emit("receive_message", data, broadcast=True, to=room)

        # Connection
        def on_join_room(self, data):
                """A function to join the user to a room.

                Args:
                        data (dict): A dictionary containing user information.
                """
                room = data['room']
                if not self.check_auth(data['token']):
                        emit("error", {"error": "Invalid credentials"})
                        return {"status": 401, "message": "Invalid credentials"}

                join_room(room=room)
                emit("connection", f"connecting user to room: {room}", to=room)

                if room not in self.rooms:
                       self.create_room(room)
                self.room[room]["users"].append(data["author"])

                return {"status": 200, "content": {"message": "Connected to room", "users": self.rooms[room]["users"]}}

        def on_leave_room(self, data):
                """A function to disconnect the user from a room.

                Args:
                        data (dict): A dictionary containing user information.
                """
                room = data['room']
                if not self.check_auth(data['token']):
                        socket.emit("error", jsonify({"error": "Invalid credentials"}, 401))
                        return {"status": 401, "message": "Invalid credentials"}

                leave_room(room=room)
                emit("connection", f"disconnecting user from room: {room}", to=room)
                return {"status": 200, "content": {"message": "Disconnected from room"}}
                
        # Messages
        def on_messages(self, data):
                print(data["content"])


class user:
        def __init__(self, username:str, email:str, userId:str, channel:chat_room):
                self.username = username
                self.email = email
                self.userId = userId
                self.channel:chat_room = None

        def join_channel(self, channel):
                pass


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
        user_id = generate_user_id()
        token = str(generate_token())
        users.insert_one({ "username": data["username"], "email": data["email"], "userId": user_id })
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
        channels.insert_one({"channelId": data["channelId"], "channelName": data["channelName"]})
        return jsonify({"channelId": data["channelId"], "channelName": data["channelName"]}), 201

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
                channels_list.append({"channelId": channel["channelId"]})
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers
        if headers.get('Authorization') is not None:
            token = headers.get('Authorization')
            auth_user = auth.find_one({ "token": token })
            if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        return jsonify({"channelId": channel["channelId"], "channelName": channel["channelName"]}), 200

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

@app.route('/channels', methods=['DELETE'])
def delete_channels():
        for channel in channels.find():
                channels.delete_one({ "channelId": channel["channelId"] })
        return jsonify({"message": "Channel deleted"}), 200

@app.route("/namespaces", methods=['POST'])
def fetch_namespaces():
       return socket._nsps.keys()
#rooms  
@app.route("/channels/create", methods=['POST'])
def create_channel():
        data = request.get_json()
        chat = chat_room(f"/{data['channelId']}", data['channelName'], data['channelPerms'])
        print(chat.namespace)
        channelDict = {"channelId": data['channelId'], "channelName": data['channelName'], "channelPerms": data['channelPerms']}
        channels.insert_one({"channelId": data['channelId'], "channelName": data['channelName'], "channelPerms": data['channelPerms']})

        socket.on_namespace(chat)
        return jsonify(channelDict), 201


@socket.on("hello_world", namespace="/test")
def on_test(data):
        print(data)

@socket.on("greetings", namespace="/test")
def on_greetings(data):
        print(data)
        emit("greetings", "Herro world!")


def create_chat_rooms():
        """Generates chat room classes of database information.

        Args:
            channels (collection): A raw collection of chat elements found in the database.
        """
        channels = channels.find()
        print(channels)
        for channel in channels:
                chat = chat_room(f"/{channel['channelId']}", channel["channelName"], channel["channelPerms"])
                rooms.update({channel["channelId"] : chat})
                socket.on_namespace(chat)
        return rooms


if __name__ == "__main__":
        app.run(debug=True)
