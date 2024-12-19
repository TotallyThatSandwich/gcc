from random import randint
from PIL import Image, ImageChops
# class chat_room(Namespace):
#         """A class to represent a namespace of the websocket. After creating a channel(``chat_room``), methods below are automatically handled as events.\n
#         When a user joins a channel, they should be connected to the websocket with the namespace ``/chat_room.channelId`` where the following events are handled.

#         Methods: 
#                 ``check_auth``: Checks if ``auth`` exists in the database.
#                         args:
#                                 auth (str): The token of the user.

#                 ``create_room``: Creates a room in the channel.
#                         args:
#                                 room (str): The room name for the room to be created.
                
#                 ``room_exists``: Checks if a room exists in the channel.
#                         args:
#                                 room (str): The room name to check.

#                 ``send_message``: Sends a server side message to all users in the channel.

#                 ``fetch_usernames_from_ids``: Fetches usernames from user IDs connected to the channel.

#                 ``fetch_usernames_from_dict``: Fetches usernames from a dictionary of user IDs.

#                 ``on_get_sid``: Fetches the session ID of a user from their user ID.

#                 ``on_get_users``: Fetches the users in the channel.

#                 ``on_connect``: Connects the user to the channel.

#                 ``on_disconnect``: Disconnects the user from the channel.

#                 ``on_send_message``: Sends a message to all users in the channel.

#                 ``on_join_room``: Connects the user to a channel.

#                 ``on_leave_room``: Disconnects the user from a channel.
        
#         Events:
#                 ``on_send_message``: Sends a message to all users in the channel.

#                 ``on_receive_message``: Receives a message from a user and sends it to all users in the channel.

#                 ``on_join_room``: Connects the user to a channel.
#                         args:

#                 ``on_leave_room``: Disconnects the user from a channel.

#         Args:
#             Namespace (_type_): _description_
#         """
#         def __init__(self, namespace = None, chat_name = None, permissions:ChannelPerms = None):
#                 super().__init__(namespace)
#                 print(namespace)
#                 self.channelId = namespace
#                 self.chat_name = chat_name
#                 self.permissions = permissions
#                 self.rooms:dict = {}
#                 self.users = {}
#                 print("Created namespace:", namespace)

#         def fetch_usernames_from_ids(self, ids=None) -> list[str]:
#                 """Fetches usernames from user IDs connected to the channel.

#                 Args:
#                     ids (list): A list of user IDs to fetch usernames from.

#                 Returns:
#                     list: A list of usernames.
#                 """
#                 usernames = []
#                 for user in ids:
#                         usernames.append(self.users[user]["username"])
#                 return usernames

#         def fetch_usernames_from_dict(self, users:list[dict]) -> list[str]:
#                 """Fetches usernames from a dictionary of user IDs.

#                 Args:
#                     users (list[dict]): A list of dictionaries containing user infomation.
#                     [{"sid": sid, "username": username}]

#                 Returns:
#                     list: A list of usernames.
#                 """
#                 usernames = []
#                 try:
#                         for user in users:
#                                 usernames.append(user["username"])
#                 except Exception as e:
#                         print(e)
#                         return []
#                 return usernames

#         def on_get_sid(self, data):
#                 """Fetches the session ID of a user from their user ID.

#                 Args:
#                     data (dict): a dictionary containing ``{"content": userId} or {"content": username}``

#                 Returns:
#                     dict: A response containing the status of the request and the session ID of the user if found.
#                 """
#                 try:
#                         sid = self.users[data["content"]] # fetches the sid from a user id
#                         return {"status": 200, "content": sid} # fetches the sid from a user id
#                 except:
#                         return {"status": 404, "content": "User not found"}
               
               
#         def on_get_users(self, data):
#                 """Fetches the users in the channel.

#                 Args:
#                     data (dict): A dictionary containing the room name.

#                 Returns:
#                     dict: A response containing the status of the request and a list of users in the room.
#                 """
#                 room = data["target"]
                
#                 active_users = [] # outside of room
#                 users_in_room:list[dict] = self.rooms[room]["users"] # inside of room
#                 for user in self.users:
#                         if user not in users_in_room:
#                                 active_users.append(user)

#                 # for user in self.users:
#                 #         if user in self.rooms[room]["users"]:
#                 #                 users_in_room.append(user["username"])
#                 #         else:
#                 #                 active_users.append(user["username"])
#                 print(users_in_room)

#                 usernames_in_room = self.fetch_usernames_from_dict(users_in_room)
#                 print(usernames_in_room)
#                 usernames_active = self.fetch_usernames_from_dict(active_users)
#                 print(usernames_active)

#                 content = f"room: {', '.join(usernames_in_room)}\nchannel: {', '.join(usernames_active)}"
#                 self.send_message({"user": "gcc", "target": request.sid, "content": content})

#                 if room not in list(self.rooms.keys()):
#                         return {"status": 404, "content": "Room not found"}
#                 return {"status": 200, "content": {"room": users_in_room, "online": active_users}}

#         def on_connect(self, auth):
#                 print()
#                 sid = request.sid
#                 userId = auth["userId"]
                
#                 self.users.update({userId: {"sid": sid, "username": auth["user"]}})

#         def on_disconnect(self):
#                 print("disconnected")
#                 sid = request.sid

#                 for user in list(self.users.keys()):
#                         print(user)
#                         if self.users[user]["sid"] == sid:
#                                 self.users.pop(user)
#                                 break
#                         for room in self.rooms:
#                                 if user in self.rooms[room]["users"]:
#                                         self.rooms[room]["users"].remove(user)
#                                         break
#                 else:
#                         return {"status": 404, "content": "User not found"}

#         def check_auth(self, auth_token) -> bool:
#                 if not auth.find({ "token": auth_token }):
#                         return False
#                 return True
                        
#         def create_room(self, room:str) -> dict:
#                 """Creates a room dictionary and appends it to ``self.rooms``.

#                 Args:
#                         room (str): name of the room to be created.
                
#                 Returns:
#                         room (dict): A dictionary containing the room name and an empty list of users.
#                 """
#                 room = {"name": room, "users": []}
#                 self.rooms.update({room["name"]: room})
#                 return room

#         def delete_room(self, room:str):
#                 for i in self.rooms:
#                         if i["name"] == room:
#                                 self.rooms.remove(i)
#                                 break      
#                 else:
#                         return False
#                 return True
        
#         def on_get_rooms(self):
#                 sid = request.sid
#                 self.send_message({"user": "gcc", "target": sid, "content": ", ".join(list(self.rooms.keys()))})
#                 return {"status": 200, "content": list(self.rooms.keys())}

#         def room_exists(self, room):
#                 if self.room in rooms:
#                         return True
#                 return False
        
#         def send_message(self, data):
#                target = data['target']
#                emit("receive_message", data, broadcast=True, to=target, include_self=True)

#         def on_send_message(self, data):
#                 """Sends a message to users defined by the data sent.

#                 Args:
#                     data (dict): A dictionary containing infomatino about the message.
#                         elements:
#                                 ``user``: The name of the user sending the message.
#                                 ``content``: The content of the message.
#                                 ``target`` (optional): The room to send the message to.

#                 Returns:
#                     dict: A dictionary containing the status of the message.
#                 """
#                 room = data['target']
#                 try:
#                         print(f"{data['user']} has sent message {data['content']} to room {room} \n")
#                         emit("receive_message", data, broadcast=True, to=room, include_self=True)
#                         return {"status": 200, "content": "Message sent"}
#                 except:
#                        return {"status": 500, "content": "Internal server error"}

#         # Connection
#         def on_join_room(self, data):
#                 """A function to join the user to a room.

#                 Args:
#                         data (dict): A dictionary containing user information. Should contain ``{room: room}``]
#                 """

#                 room = data['room']
#                 if not self.check_auth(data['token']):
#                         emit("error", {"error": "Invalid credentials"})
#                         return {"status": 401, "content": "Invalid credentials"}

#                 join_room(room=room)
#                 emit("connection", f"connecting user to room: {room}", to=room)

#                 if room not in list(self.rooms.keys()):
#                        print("\nRoom does not exist, creating room")
#                        self.create_room(room)

#                 self.rooms[room]["users"].append(self.users[data["userId"]])

#                 return {"status": 200, "content": {"content": "Connected to room", "users": self.rooms[room]["users"]}}

#         def on_leave_room(self, data):
#                 """A function to disconnect the user from a room.

#                 Args:
#                         data (dict): A dictionary containing user information.
#                 """
#                 room = data['room']
#                 leave_room(room=room)
#                 self.rooms[room]["users"].remove(data["userId"])
#                 emit("connection", f"disconnecting user from room: {room}", to=room)
#                 return {"status": 200, "content": {"content": "Disconnected from room"}}
                
#         # Messages
#         def on_messages(self, data):
#                 print(data["content"])
import os


backgroundColour = (randint(0, 230), randint(0, 90), randint(0, 255))
print(backgroundColour)

image = Image.open(fp="resources/GCC_pfp.png")
image  = image.convert("RGBA")
image.save("resources/tempGCC_pfp.png", "PNG")
image.close()

image = Image.open(fp="resources/tempGCC_pfp.png")
image = image.resize((128, 128))

backgroundColour = (randint(0, 255), randint(0, 255), randint(0, 255))

background = Image.new("RGB", (128, 128), color=backgroundColour)

inverted = ImageChops.invert(background)
inverted = inverted.convert("RGBA")
inverted = ImageChops.overlay(inverted, image)

background.paste(inverted, (0, 0), image)
background.show()
os.remove("resources/tempGCC_pfp.png")