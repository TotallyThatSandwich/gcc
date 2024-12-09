import asyncio
import pymongo as pm
from pymongo import collection
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
auth:collection.Collection = db["auth"]
users:collection.Collection = db["users"]
channels:collection.Collection = db["channels"]
messages:collection.Collection = db["messages"]

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

                ``send_message``: Sends a server side message to all users in the channel.

                ``fetch_usernames_from_ids``: Fetches usernames from user IDs connected to the channel.

                ``fetch_usernames_from_dict``: Fetches usernames from a dictionary of user IDs.

                ``on_get_sid``: Fetches the session ID of a user from their user ID.

                ``on_get_users``: Fetches the users in the channel.

                ``on_connect``: Connects the user to the channel.

                ``on_disconnect``: Disconnects the user from the channel.

                ``on_send_message``: Sends a message to all users in the channel.

                ``on_join_room``: Connects the user to a channel.

                ``on_leave_room``: Disconnects the user from a channel.
        
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
                self.users = {}
                print("Created namespace:", namespace)

        def fetch_usernames_from_ids(self, ids=None) -> list[str]:
                """Fetches usernames from user IDs connected to the channel.

                Args:
                    ids (list): A list of user IDs to fetch usernames from.

                Returns:
                    list: A list of usernames.
                """
                usernames = []
                for user in ids:
                        usernames.append(self.users[user]["username"])
                return usernames

        def fetch_usernames_from_dict(self, users:list[dict]) -> list[str]:
                """Fetches usernames from a dictionary of user IDs.

                Args:
                    users (list[dict]): A list of dictionaries containing user infomation.
                    [{"sid": sid, "username": username}]

                Returns:
                    list: A list of usernames.
                """
                usernames = []
                try:
                        for user in users:
                                usernames.append(user["username"])
                except Exception as e:
                        print(e)
                        return []
                return usernames

        def on_get_sid(self, data):
                """Fetches the session ID of a user from their user ID.

                Args:
                    data (dict): a dictionary containing ``{"content": userId} or {"content": username}``

                Returns:
                    dict: A response containing the status of the request and the session ID of the user if found.
                """
                try:
                        sid = self.users[data["content"]] # fetches the sid from a user id
                        return {"status": 200, "content": sid} # fetches the sid from a user id
                except:
                        return {"status": 404, "content": "User not found"}
               
               
        def on_get_users(self, data):
                """Fetches the users in the channel.

                Args:
                    data (dict): A dictionary containing the room name.

                Returns:
                    dict: A response containing the status of the request and a list of users in the room.
                """
                room = data["target"]
                
                active_users = [] # outside of room
                users_in_room:list[dict] = self.rooms[room]["users"] # inside of room
                for user in self.users:
                        if user not in users_in_room:
                                active_users.append(user)

                # for user in self.users:
                #         if user in self.rooms[room]["users"]:
                #                 users_in_room.append(user["username"])
                #         else:
                #                 active_users.append(user["username"])
                print(users_in_room)

                usernames_in_room = self.fetch_usernames_from_dict(users_in_room)
                print(usernames_in_room)
                usernames_active = self.fetch_usernames_from_dict(active_users)
                print(usernames_active)

                content = f"room: {', '.join(usernames_in_room)}\nchannel: {', '.join(usernames_active)}"
                self.send_message({"user": "gcc", "target": request.sid, "content": content})

                if room not in list(self.rooms.keys()):
                        return {"status": 404, "content": "Room not found"}
                return {"status": 200, "content": {"room": users_in_room, "online": active_users}}

        def on_connect(self, auth):
                print()
                sid = request.sid
                userId = auth["userId"]
                
                self.users.update({userId: {"sid": sid, "username": auth["user"]}})

        def on_disconnect(self):
                print("disconnected")
                sid = request.sid

                for user in list(self.users.keys()):
                        print(user)
                        if self.users[user]["sid"] == sid:
                                self.users.pop(user)
                                break
                        for room in self.rooms:
                                if user in self.rooms[room]["users"]:
                                        self.rooms[room]["users"].remove(user)
                                        break
                else:
                        return {"status": 404, "content": "User not found"}

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
        
        def on_get_rooms(self):
                sid = request.sid
                self.send_message({"user": "gcc", "target": sid, "content": ", ".join(list(self.rooms.keys()))})
                return {"status": 200, "content": list(self.rooms.keys())}

        def room_exists(self, room):
                if self.room in rooms:
                        return True
                return False
        
        def send_message(self, data):
               target = data['target']
               emit("receive_message", data, broadcast=True, to=target, include_self=True)

        def on_send_message(self, data):
                """Sends a message to users defined by the data sent.

                Args:
                    data (dict): A dictionary containing infomatino about the message.
                        elements:
                                ``user``: The name of the user sending the message.
                                ``content``: The content of the message.
                                ``target`` (optional): The room to send the message to.

                Returns:
                    dict: A dictionary containing the status of the message.
                """
                room = data['target']
                try:
                        print(f"{data['user']} has sent message {data['content']} to room {room} \n")
                        emit("receive_message", data, broadcast=True, to=room, include_self=True)
                        return {"status": 200, "content": "Message sent"}
                except:
                       return {"status": 500, "content": "Internal server error"}

        # Connection
        def on_join_room(self, data):
                """A function to join the user to a room.

                Args:
                        data (dict): A dictionary containing user information. Should contain ``{room: room}``]
                """

                room = data['room']
                if not self.check_auth(data['token']):
                        emit("error", {"error": "Invalid credentials"})
                        return {"status": 401, "content": "Invalid credentials"}

                join_room(room=room)
                emit("connection", f"connecting user to room: {room}", to=room)

                if room not in list(self.rooms.keys()):
                       print("\nRoom does not exist, creating room")
                       self.create_room(room)

                self.rooms[room]["users"].append(self.users[data["userId"]])

                return {"status": 200, "content": {"content": "Connected to room", "users": self.rooms[room]["users"]}}

        def on_leave_room(self, data):
                """A function to disconnect the user from a room.

                Args:
                        data (dict): A dictionary containing user information.
                """
                room = data['room']
                leave_room(room=room)
                self.rooms[room]["users"].remove(data["userId"])
                emit("connection", f"disconnecting user from room: {room}", to=room)
                return {"status": 200, "content": {"content": "Disconnected from room"}}
                
        # Messages
        def on_messages(self, data):
                print(data["content"])


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

def dictify(collection):
        return json.loads(json.dumps(collection, default=str))

#auth
@app.route('/checkauth', methods=['GET'])
def check_auth():
        headers = request.headers

        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        user = auth.find_one({ "token": headers.get('Authorization') })

        return jsonify(user), 200

@app.route('/getauth', methods=['POST'])
def post_auth():
        print("getting auth")
        data = request.get_json()
        user = auth.find_one({ "username": data["username"], "passwordHash": data["passwordHash"] })
        if user is None:
                return jsonify({"error": "Invalid credentials"}), 401
        return jsonify({"token": user["token"]}), 200


# user
@app.route('/user/new', methods=['POST'])
def post_user():
        print("creating user")
        data = request.get_json()
        user = users.find_one({ "username": data["username"] })
        if user is not None:
                return jsonify({"error": "User already exists"}), 400
        user_id = generate_user_id()
        token = str(generate_token())
        users.insert_one({ "username": data["username"], "email": data["email"], "userId": user_id })
        auth.insert_one({ "username": data["username"], "passwordHash": data["passwordHash"], "token": token })
        return jsonify({ "username": data["username"], "passwordHash": data["passwordHash"], "token": token }), 201

@app.route('/userfromid/<userId>', methods=['GET'])
def get_user_from_id(userId):
        user = users.find_one({"userId": userId})
        headers = request.headers
        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({ "token": token })

        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify(user), 200

@app.route('/userfromname/<userName>', methods=['GET'])
def get_user_from_name(userName):
        user = users.find_one({ "username": userName })
        headers = request.headers
        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({ "token": token })

        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify(dictify(user)), 200

@app.route('/users', methods=['GET'])
def get_users():
        users_list = []
        headers = request.headers
        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
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
@app.route('/channels', methods=['GET'])
def get_channels():
        channels_list = []
        headers = request.headers
        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({ "token": token })
        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        
        for channel in channels.find():
                channels_list.append({"channelId": channel["channelId"], "channelName": channel["channelName"], "channelPerms": channel["channelPerms"]})
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers

        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
                print("gay")
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({"token": token})

        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404 
        return jsonify(dictify(channel)), 200

#messages
@app.route('/channels/<channelId>/messages', methods=['GET'])
def get_messages(channelId):
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers
        messageId = request.args.get('messageId')
        room = request.args.get('room')

        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({ "token": token })

        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        
        messages_list = messages.find({"channelId": channelId, "room": room})\
                        .sort("messageId", pm.DESCENDING)\
                        .skip(messages.count_documents() - messageId)\
                        .limit(100)
        
        return jsonify({"messages": messages_list.to_list()}), 200

@app.route('/channels/<channelId>/messages', methods=['POST'])
def send_message(channelId):
        data = request.get_json()
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers

        if headers.get('Authorization') is None:
                return jsonify({"error": "Invalid token"}), 401
        
        token = headers.get('Authorization')
        auth_user = auth.find_one({ "token": token })

        if auth_user is None:
                return jsonify({"error": "Invalid token"}), 401
        
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        
        messageId = messages.count_documents() + 1
        data.update({"messageId": messageId})
        messages.insert_one(data)

        room:chat_room = rooms[channelId]
        room.on_send_message(data=data)

        return data, 201

@app.route('/messages/<messageId>', methods=['GET'])
def get_message(messageId):
        message = messages.find_one({"messageId": messageId})
        if message is None:
                return jsonify({"error": "Message not found"}), 404
        return jsonify(message), 200



@app.route('/channels', methods=['DELETE'])
def delete_channels():
        print("deleting channels")
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
        if channels.find_one({"channelId": data['channelId']}) is not None:
                return jsonify({"error": "Channel already exists"}), 400
        channels.insert_one({"channelId": data['channelId'], "channelName": data['channelName'], "channelPerms": data['channelPerms']})

        socket.on_namespace(chat)
        return jsonify(channelDict), 201

@app.route("/channels/populate", methods=['POST'])
def populate_channels():
        create_chat_rooms()
        return jsonify({"message": "Populated channels"}), 200


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
        namespaces = channels.find()
        print(channels)
        for channel in namespaces:
                if channel['channelId'] in list(rooms.keys()):
                        continue
        
                print("channel", channel)
                chat = chat_room(f"/{channel['channelId']}", channel["channelName"], channel["channelPerms"])
                rooms.update({channel["channelId"] : chat})
                socket.on_namespace(chat)
        return rooms


if __name__ == "__main__":
        asyncio.run(app.run(debug=True))
        asyncio.run(create_chat_rooms())
        
        
        
