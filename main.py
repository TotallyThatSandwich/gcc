import asyncio
import pymongo as pm
from pymongo import collection
import json
import settings
import binascii
import os
import uuid
# Flask
from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO, send, emit, Namespace, join_room, leave_room
from flask_cors import CORS, cross_origin

# Image handling
from bson.binary import Binary
from PIL import Image, ImageChops
from io import BytesIO
UPLOAD_FOLDER = os.path.join(os.getcwd(), "resources")

# Random
from random import randint

# Marshmallow
from marshmallow import Schema, fields, ValidationError, validates, EXCLUDE, INCLUDE, validate

client = pm.MongoClient(settings.MONGO_ADDRESS, username=settings.MONGO_USER, password=settings.MONGO_PASS)
db = client["db"]
auth:collection.Collection = db["auth"]
users:collection.Collection = db["users"]
channels:collection.Collection = db["channels"]
messages:collection.Collection = db["messages"]
images:collection.Collection = db["images"]

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
cors = CORS(app)
socket = SocketIO(app)

cachedChannels = {}

class UserInfo(Schema):
        class Meta:
                unknown = EXCLUDE
        username = fields.String(required=True)
        userId = fields.String(required=True)
        email = fields.Email(required=True)
        displayName = fields.String()
        friends = fields.Dict(fields.String(), fields.List(fields.UUID()), load_default={"pending": [], "requested": [], "friends": []})

        @validates("email")
        def validate_email(self, email):
                print(validate.Email()(email))

class RoomPerms(Schema):
        class Meta:
                unknown = INCLUDE # ensure that custom permissions can be added on the fly.
        read = fields.Bool()
        write = fields.Bool()
        delete = fields.Bool()
class RoomInfo(Schema):
        name = fields.String(required=True)
        perms = fields.Nested(RoomPerms)

class UserAuth(Schema):
        class Meta:
                unknown = EXCLUDE

        username = fields.String(required=True)
        passwordHash = fields.String(required=True)
        token = fields.String()

class ChannelPerms(Schema):
        pass

class ChannelInfo(Schema):
        class Meta:
                unknown = EXCLUDE
        channelId = fields.Str(required=True)
        channelName = fields.Str(required=True)
        channelPerms = fields.Nested(ChannelPerms)

class MessageInfo(Schema):
        messageId = fields.Int(required=True)
        content = fields.Str(required=True)
        user = fields.Str(required=True)
        timestamp = fields.DateTime(required=True)
        target = fields.Str(required=True)
        targetMessage: int | None = fields.Int()



# Websockets
class channelClass(Namespace): # chat_room V2
        def __init__(self, namespace = None, channelName = None, permissions:ChannelPerms = None):
                super().__init__(namespace)
                self.channelId = namespace
                self.channelName = None
                self.rooms = {}
                self.users = {}
                self.perms = {}

        def initFromDict(self, data):
                self.channelId = f"/{data['channelId']}"
                self.rooms = data["rooms"]
                self.users = data["users"]
                self.perms = data["perms"]       
                
        async def on_connect(self, auth):
                sid = request.sid
                userInfo = auth.copy()
                userInfo = UserInfo().load(userInfo)    
                self.users.update({sid: userInfo})
                print(f"User {userInfo['username']} connected to {self.channelId} with sid {sid}")

        # rooms
        async def fetch_rooms(self):
                return {"status": 200, "content": jsonify(self.rooms)}

        def update_room(self, room):
                try:
                        RoomInfo().load(room)
                except ValidationError as e:
                        return {"status": 400, "content": e.messages}
                self.rooms.update({room["name"]: room})

        async def on_join_room(self, data):
                room = data["room"]
                sid = request.sid

                join_room(room)
                self.rooms[room]["users"].append(self.users[sid])
                print(f"User {self.users[sid]['username']} joined room {room}")
                emit("joinEvents",  self.joinEvents().load("join", ))

        async def on_leave_room(self, data):
                room = data["room"]
                sid = request.sid

                leave_room(room)
                self.rooms[room]["users"].remove(self.users[sid])
                print(f"User {self.users[sid]['username']} left room {room}")
        
        async def on_send_message(self, data):
                target = data['target']
                
                try:
                        data = MessageInfo().load(data)
                except ValidationError as e:
                        return {"status": 400, "content": e.messages}

                if target in list(self.users.keys()):
                        emit("private_message", to=target, data=data, include_self=True)
                        return
                
                emit("message", data, broadcast=True, to=target, include_self=True)

def generate_token():
    generated_token = binascii.hexlify(os.urandom(10)).decode()
    while auth.find_one({ "token": generated_token }) is not None:
        generated_token = binascii.hexlify(os.urandom(10)).decode()
    return generated_token

def generate_user_id() -> str:
        generated_id = str(uuid.uuid4())
        while users.find_one({ "userId": generated_id }) is not None:
                generated_id = str(uuid.uuid4())
        return generated_id

def check_auth_from_headers(headers) -> bool:
        """Checks if the request has a valid token in the headers.

        Args:
            headers (dict): request headers.

        Returns:
            bool: True if the token is valid, False if not.
        """
        if headers.get('Authorization') is not None:
                if auth.find_one({ "token": headers.get('Authorization') }) != None:
                        return True
        return False

# * auth
@app.route('/checkauth', methods=['GET']) # Fetches user info using token
def check_auth():
        headers = request.headers

        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        user = auth.find_one({ "token": headers.get('Authorization') })
        try:
                user = UserAuth().load(user)
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400

        return jsonify(user), 200

@app.route('/getauth', methods=['POST']) # Fetches user info using username and password
def post_auth():
        print("getting auth")
        data = request.get_json()

        try:
                auth_user:dict = UserAuth().load(data)

                if auth.find_one(auth_user) is None:
                        raise ValidationError("Invalid credentials")
                
                auth_user.update({"token": auth.find_one(auth_user)["token"]})

                return jsonify(auth_user), 200
        except ValidationError as e:
                print(e.messages)
                if "Invalid credentials" in e.messages:
                        return jsonify({"error": "Invalid credentials"}), 401
                return jsonify({"error":e.messages}), 400


# * user
def generate_default_pfps(userId):
        defaultPfp = images.find_one({"pfpdefault": {"$exists": True}})
        
        if defaultPfp is None:
                if not os.path.exists("resources/GCC_pfp.png"):
                        raise FileNotFoundError("Default profile picture not found")

                image = Image.open("resources/GCC_pfp.png")
                image = image.resize((128, 128))
                imgByteArr = BytesIO()
                image.save(imgByteArr, format="png")
                defaultPfp = imgByteArr.getvalue()
                images.insert_one({"pfpdefault": defaultPfp})
                image.close()
        else:
                defaultPfp = defaultPfp["pfpdefault"]

        image = Image.open(BytesIO(defaultPfp))
        
        backgroundColour = (randint(0, 230), randint(0, 90), randint(0, 255))
        print(backgroundColour)

        backgroundColour = (randint(0, 255), randint(0, 255), randint(0, 255)) # ! Let the user choose, placeholder for now

        background = Image.new("RGB", (128, 128), color=backgroundColour)

        inverted = ImageChops.invert(background)
        inverted = inverted.convert("RGBA")
        inverted = ImageChops.overlay(inverted, image)

        background.paste(inverted, (0, 0), image)

        background.save(f"resources/{userId}.png", format="png")

        inverted.close()
        background.close()
        image.close()

        
@app.route('/user/pfp', methods=['PUT'])
def upload_pfp():
        # ! IT FUCKING WORKS, but image sizing SHOULD BE DONE BEFOREHAND OTHERWISE IMAGES WILL BE WARPED.
        print("uploading pfp")
        token = request.headers.get('Authorization')
        if not check_auth_from_headers(request.headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        user = auth.find_one({ "token": token })
        user = users.find_one({ "username": user["username"] })

        if user is None:
                return jsonify({"error": "User not found"}), 404
        try:
                user = UserInfo().load(user)
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400
        
        requestFiles = request.files
        if len(requestFiles) == 0:
                return jsonify({"error": {"files": ["No files uploaded"]}}), 400
        
        file = requestFiles['file']
        if file.filename == '':
                return jsonify({"error": {"files": ["No selected file"]}}), 400
        if not file:
                return jsonify({"error": {"files": ["No file part"]}}), 400
        fileFormat = file.filename.split('.')[-1]
        if fileFormat not in ["png", "jpg", "jpeg", "gif"]:
                return jsonify({"error": {"files": ["Invalid file type"]}}), 400
        
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        
        image = Image.open(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image = image.resize((128, 128))
        imgByteArr = BytesIO()
        image.save(imgByteArr, format=fileFormat)
        imgByteArr = imgByteArr.getvalue()

        images.update_one({"userId": user["userId"]}, { "$set": { "pfp": imgByteArr } })
        image.close()
        return jsonify(user), 201

@app.route('/user/<userId>/pfp', methods=['GET'])
def get_default_pfp(userId):
        if not check_auth_from_headers(request.headers):
                return jsonify({"error": "Invalid credentials"}), 401

        user = users.find_one({"userId": userId})
        if user is None:
                return jsonify({"error": "User not found"}), 404
        
        try:
                user = UserInfo().load(user)
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400
        
        if images.find_one({"userId": userId}) is None:
                generate_default_pfps(userId)
                with open("resources/" + f"{userId}.png", "rb") as f:
                        imgdata = f.read()
                
                if images.find_one({"userId": userId}) is None:
                        images.insert_one({"userId": userId, "pfp": imgdata})
                else:
                        images.update_one({"userId": userId}, {"$set": {"pfp": imgdata}})
                return jsonify({"message": "Successfully created new profile picture!"}), 201
        
        imageBytes = images.find_one({"userId": userId})['pfp']
        imageBytes = BytesIO(imageBytes)

        imageBytes.seek(0)
        byteRead = imageBytes.read()
        
        imageBytes = BytesIO(byteRead)
        image = Image.open(imageBytes)
        image = image.convert("RGBA")
        image.save("resources/" + f"{userId}.png")
        image.close()
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{userId}.png")
        try:
                print("sending", file_path)
                return send_file(file_path), 200
        except FileNotFoundError:
                return jsonify({"error": "File not found"}), 404
        
        # ! CURRENTLY, IMAGES ARE BEING DELETED AT THE START OF THE PROGRAM, FIND A FUCKING ALTERNATIVE!

@app.route('/user/new', methods=['POST'])
def post_user():
        print("creating user")
        data = request.get_json()

        user_id = generate_user_id()
        token = str(generate_token())

        data.update({"userId": user_id, "token": token})

        try:
                userInfo = UserInfo().load(data)
                userAuth = UserAuth().load(data)

                if auth.find_one({ "username": userAuth["username"] }) is not None:
                        raise ValidationError("Username already exists")
                
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400

        users.insert_one(userInfo.copy()) # !fucking bullshit, why does insert_one mutate userInfo? Must do .copy() to prevent mutation
        auth.insert_one(document=userAuth.copy())
        return jsonify({"Authentication": userAuth, "User": userInfo}), 201

@app.route('/user/<userId>', methods=['DELETE'])
def delete_user(userId):
        user = users.find_one({ "userId ": userId })
        if user is None:
                return jsonify({"error": "User not found"}), 404
        users.delete_one({ "userId": userId })
        return jsonify({"message": "User deleted"}), 200

@app.route('/userfromid/<userId>', methods=['GET'])
def get_user_from_id(userId):
        user = users.find_one({"userId": userId})
        user = UserInfo().load(user)

        if not check_auth_from_headers(request.headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        if user is None:
                return jsonify({"error": "User not found"}), 404
        
        return jsonify(user), 200

@app.route('/userfromname/<userName>', methods=['GET'])
def get_user_from_name(userName):

        headers = request.headers
        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401

        user = users.find_one({ "username": userName })

        try:
                user = UserInfo().load(user)
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400
        
        return jsonify(user), 200


ACCEPT = "accept"
DECLINE = "decline"
REQUEST = "request"
UNFRIEND = "unfriend"
UNREQUEST = "unrequest"
def update_friends_list(userId, targetId, action):
        if userId == targetId:
                return jsonify({"error": {"target": ["Cannot friend yourself"]}}), 400
        try:
                user = users.find_one({"userId": userId})
                target = users.find_one({"userId": targetId})

                user:dict = UserInfo().load(user)
                target:dict = UserInfo().load(target)

                user.setdefault("friends", {"pending": [], "requested": [], "friends": []})
                target.setdefault("friends", {"pending": [], "requested": [], "friends": []})
        except:
                return jsonify({"error": "User not found"}), 404

        #! A lot of these cases assume that the UIDs are present in the lists already. Checks should be made before.
        if action == ACCEPT:
                user["friends"]["friends"].append(targetId)
                target["friends"]["friends"].append(userId)
                user["friends"]["pending"].remove(targetId)
                target["friends"]["requested"].remove(userId)
        if action == DECLINE:
                user["friends"]["pending"].remove(targetId)
                target["friends"]["requested"].remove(userId)
        if action == REQUEST:
                user["friends"]["requested"].append(targetId)
                target["friends"]["pending"].append(userId)
        if action == UNFRIEND:
                user["friends"]["friends"].remove(targetId)
                target["friends"]["friends"].remove(userId)
        if action == UNREQUEST:
                user["friends"]["requested"].remove(targetId)
                target["friends"]["pending"].remove(userId)

        users.update_one({"userId": userId}, {"$set": user.copy()})
        users.update_one({"userId": targetId}, {"$set": target.copy()})

        return jsonify(user), 201
        

@app.route('/user/friend', methods=['POST'])
def request_friend():
        headers = request.headers
        action = request.args.get('action')

        if action not in [ACCEPT, DECLINE, REQUEST, UNFRIEND, UNREQUEST]:
                return jsonify({"error": {"action": ["Invalid action"]}}), 400
        
        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        data = request.get_json()

        return update_friends_list(data["self"]["userId"], data["target"]["userId"], action)


@app.route('/users', methods=['GET'])
def get_users():
        users_list = []
        headers = request.headers

        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        try:
                users_list = UserInfo(many=True).load(users.find().to_list())
                return jsonify({"users": users_list}), 200
        except ValidationError as e:
                print(e.messages)
                return jsonify({"users": e.valid_data}), 400

# * channels
@app.route('/channels', methods=['GET'])
def get_channels():
        channels_list = []
        headers = request.headers
        
        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        try:
                channels_list = channels.find().to_list()
                channels_list = ChannelInfo(many=True).load(channels_list)
        except ValidationError as e:
                print(e.messages)
                return jsonify({"channels": e.valid_data}), 400
        print("No channels found")
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers

        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        try:
                channel = ChannelInfo().load(channel)
        except ValidationError as e:
                return jsonify(e.messages), 400

        return jsonify(channel), 200

#messages
@app.route('/channels/<channelId>/messages', methods=['GET'])
def get_messages(channelId):
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers
        messageId = request.args.get('messageId', default=messages.count_documents(), type=int)
        room = request.args.get('room')

        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        
        messages_list = messages.find({"channelId": channelId, "room": room})\
                        .sort("messageId", pm.DESCENDING)\
                        .skip(messages.count_documents() - messageId)\
                        .limit(100)\
                        .to_list()
        
        messages_list = MessageInfo(many=True).load(messages_list)
        
        
        return jsonify({"messages": messages_list}), 200

@app.route('/channels/<channelId>/messages', methods=['POST'])
def send_message(channelId):
        data = request.get_json()
        channel = channels.find_one({"channelId": channelId})
        headers = request.headers

        if not check_auth_from_headers(headers):
                return jsonify({"error": "Invalid credentials"}), 401
        
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        
        messageId = messages.count_documents() + 1
        data.update({"messageId": messageId})

        try:
                message = MessageInfo().load(data)
                messages.insert_one(message.copy())
                
                room:channelClass = cachedChannels[channelId]
                room.on_send_message(data=data)
        except ValidationError as e:
                return jsonify(e.messages), 400
        

        return jsonify(message), 201

@app.route('/messages/<messageId>', methods=['GET'])
def get_message(messageId):
        message = messages.find_one({"messageId": messageId})
        try:
                message = MessageInfo().load(message)
        except ValidationError as e:
                return jsonify(e.messages), 400
        return jsonify(message), 200

@app.route('/channels', methods=['DELETE'])
def delete_channels():
        print("deleting channels")
        for channel in channels.find():
                channels.delete_one({ "channelId": channel["channelId"] })
        
        cachedChannels.clear()
        return jsonify({"message": "Channel deleted"}), 200

@app.route("/namespaces", methods=['POST'])
def fetch_namespaces():
       return socket._nsps.keys()
#rooms  
@app.route("/channels/create", methods=['POST'])
def create_channel():

        if not check_auth_from_headers(request.headers):
                return jsonify({"error": "Invalid credentials"}), 401

        
        try:
                data = request.get_json()
                channelDict = ChannelInfo().load(data)
        except ValidationError as e:
                return jsonify({"error": e.messages}), 400
        except Exception as e:
                return jsonify({"error": str(e)}), 400

        if channels.find_one({"channelId": channelDict["channelId"]}) is not None:
                return jsonify({"error": {"channel name": ["Channel already exists"]}}), 400
        channels.insert_one(channelDict.copy())

        chat = channelClass(f"/{channelDict['channelId']}", channelDict["channelName"], channelDict["channelPerms"])
        socket.on_namespace(chat)
        return jsonify(channelDict), 201

@app.route("/channels/populate", methods=['POST'])
def populate_channels():
        create_channels()
        return jsonify({"message": "Populated channels"}), 200

async def create_channels():
        """Generates chat room classes of database information.

        Args:
            channels (collection): A raw collection of chat elements found in the database.
        """
        namespaces = channels.find()
        print(channels)
        for channel in namespaces:
                if channel['channelId'] in list(cachedChannels.keys()):
                        continue
                try:
                        channelDict = ChannelInfo().load(channel)
                        chat = channelClass()
                        chat.initFromDict(channelDict)
                        cachedChannels.update({channel["channelId"] : chat})
                        socket.on_namespace(chat)
                except ValidationError as e:
                        print(e.messages)
                        continue
                except Exception as e:
                        print(e)
                        continue
        return cachedChannels


if __name__ == "__main__":
        for files in os.listdir("resources"):
                if files != "GCC_pfp.png":
                        os.remove(os.path.join("resources", files))
        asyncio.run(app.run(debug=True))
        asyncio.create_task(create_channels())



