import asyncio
import websockets
from requests import request
from hashlib import md5
import socketio

from uuid import uuid4

from rich import print as rprint
from rich.pretty import pprint
from rich.live import Live
from rich.console import Console
from rich.progress import Progress

from datetime import datetime


import websockets.asyncio
import websockets.asyncio.client
import websockets.connection

import settings
username = settings.USERNAME
password = settings.PASSWORD
auth = settings.AUTH
server = settings.SERVER


async def create_channel(channelName:str, channelId:str, channelPerms:dict):
    response = request("POST", f"{server}/channels/create", headers= {"Authorization": auth}, json={"channelName":channelName, "channelId":channelId, "channelPerms":channelPerms})
    response = response.json()

class Client:
    def __init__(self, username:str, password:str, email:str, userId:str =None):
        
        # user credentials
        self.username = username
        self.userId = userId
        self.password = password
        self.auth = auth
        self.email = email

        # user data
        self.room = None
        self.target = None
        self.channel = None
        self.channelName = None
        self.sio = socketio.Client()

        self.dataScheme = {"event": None, "data": {"target": None, "user": self.username, "userId": self.userId, "content": None}, "namespace": None}

        self.headers = {"Authorization": self.auth}

        self.console = Console()

        self.prefix = "[bold]<{username} - {time} - @{target}>[/bold]"

        self.commands = {
            "/exit": lambda self: self.sio.disconnect(),
            "/leave": lambda self: self.leaveRoom(),
            "/join": lambda self: asyncio.create_task(self.joinRoom(self.console.input("[italic]Enter room name[/italic]: "))),
            "/create": lambda self: asyncio.create_task(self.createChannel(self.console.input("[italic]Enter channel name[/italic]: "), str(uuid4()), {})),
            "/rooms": lambda self: self.get_rooms(),
            "/users": lambda self: asyncio.create_task(self.get_users())
    }
        
    def updateSchema(self):
        self.dataScheme.update({"data": {"user": self.username, "userId": self.userId, "token": self.auth, "content": None}})
        return self.dataScheme

    async def createChannel(self, channelName:str, channelId:str, channelPerms:dict):
        response = request("POST", f"http://{server}/channels/create", headers= {"Authorization": self
        .auth}, json={"channelName":channelName, "channelId":channelId, "channelPerms":channelPerms})

        if response.status_code != 201:
            return response.json()["error"]
        return response
    
    async def get_users(self):
        if self.target == None:
            target = self.room
        else:
            target = self.target

        data = {"target": target}
        response = self.sio.call("get_users", data=data, namespace=f"/{self.channel}")

        if response["status"] != 200:
            return response["content"]
        inRoom = response["content"]["room"]
        activeUsers = response["content"]["online"]
        
        # self.console.print("Room:", inRoom, "Channel:", activeUsers)

    async def signUp(self):
        response = request("POST", f"http://{server}/user/new", json={"username":self.username,"email":self.email, "passwordHash": md5(self.password.encode()).hexdigest()})
    
        if response.status_code != 201:
            return response.json()["error"]
        response = response.json()
        self.auth = response["token"]

    async def login(self):
        response = request("POST", f"http://{server}/getauth", json={"username":self.username, "passwordHash": md5(self.password.encode()).hexdigest()})

        if response.status_code!=200:
            await self.signUp()
            return
        
        response = response.json()
        self.auth = response["token"]

        response = request("GET", f"http://{server}/userfromname/{self.username}", headers=self.headers)
        
        if response.status_code != 200:
            print(response)
            return response.json()["error"]
        response = response.json()
        self.userId = response["userId"]

    
    async def connect(self):
        with self.console.status(f"Connecting to {self.channelName}...", spinner="aesthetic"):
            try:
                self.sio.connect(f"ws://{server}", auth= {"Authenticatiation": self.auth, "user": self.username, "userId": self.userId}, wait_timeout=10, namespaces=[f"/{self.channel}"])
                self.sio.on("connect", lambda: print("Connected to server!"))
                self.sio.on("disconnect", self.on_disconnect, namespace=f"/{self.channel}")
                self.sio.on("receive_message", self.on_message, namespace=f"/{self.channel}") # message event, should be used to parse through all possible messages.
                self.console.rule("Connected to server!")
            except Exception as e:
                self.console.print_exception()
                self.console.print("[bold red]Failed to connect to server.[/bold red]")
                self.sio.shutdown()
                return False
            
    def get_rooms(self):
        if self.channel == None:
            return "Not in a channel."
        
        response = self.sio.call(event="get_rooms", namespace=f"/{self.channel}")

        if response["status"] != 200:
            return response["content"]
        return response["content"]
            
    # client commands

    async def joinRoom(self, room):
        if self.target != None:
            self.leaveRoom()
        self.console.print(f"[bold red]Joining[/bold red] [italic]{room}[/]")
        response = self.sio.call(event="join_room", data = {"room":room, "user": self.username, "userId": self.userId, "token":self.auth}, namespace=f"/{self.channel}")

        if response["status"] != 200:
            return response["content"]
        
        self.room = room
        print(response)
        self.console.rule(f"[bold red]{self.room}[/bold red]")
        return f"Successfully joined room {room} with {response['content']['users']}"

    def leaveRoom(self):
        response = self.sio.emit("leave_room", {"user": self.username, "userId": self.userId, "room":self.room}, namespace=f"/{self.channel}")

        if response['status'] != 200:
            return response['content']
        self.room = None
        return response
    
    def getUserSId(self, userId=None, user=None):
        if self.sio.connected == False:
            return "Not connected to server."

        if userId == None:
            response = request("GET", f"http://{server}/userfromname/{user}", headers=self.headers)
            if response.status_code != 200:
                return response.json()["error"]
            userId = response.json()["userId"]

        response = self.sio.call("get_sid", {"content": userId}, namespace=f"/{self.channel}")
    
    async def sendMessage(self, message):

        if self.target == None:
            if self.room == None:
                return "Not in a room."
            target = self.room

        if message[0] == "/":
            if message in list(self.commands.keys()):
                return self.commands[message](self)
            else:
                return self.console.print(f"Command {message} not found.")
        
        if message[0] == "@":
            target = message.split(" ")[0][1:]
            message = " ".join(message.split(" ")[1:])
        else:
            target = self.target

        body = {"target": target, "user": self.username, "userId": self.userId, "content": message, "timestamp": datetime.now().strftime(), "targetMessage": None}
        response = request("GET", f"http://{server}/channels/{self.channelId}/messages", headers=self.headers, json=body)

    def on_message(self, data):
        author = data["user"]
        message = data["content"]
        target = data["target"]

        self.console.print(self.prefix.format(username=author, time=datetime.now().strftime("%H:%M:%S"), target=target) + f" {message}")

    def getChannelFromId(self, channel):
        response = request("GET", f"http://{server}/channels/{channel}", headers=self.headers)

        if response.status_code != 200:
            print("Channel doesn't exist.")
            return False
        response = response.json()
        self.channel = response['channelId']
        self.channelName = response["channelName"]

        return response
    
    def on_disconnect(self):
        self.sio.shutdown()
        self.console.print("Disconnected from server.")
        

async def user_input_loop(client: Client):
    while True:
        message = await asyncio.to_thread(client.console.input)
        if message != "":
            await client.sendMessage(message)

async def delete_channels():
    response = request("DELETE", f"http://{server}/channels", headers= {"Authorization": auth})

    if response.status_code != 200:
        return response["error"]
    return response

async def populate_channels():
    response = request("POST", f"http://{server}/channels/populate", headers= {"Authorization": auth})

    if response.status_code != 200:
        return response["error"]
    return response

async def main():
    #await delete_channels()
    await populate_channels()
    username, password, email = input("username, password, email: ").split(", ")
    client = Client(username, password, email)
    await client.login()

    channel = client.getChannelFromId(channel="0721")
    if channel == False:
        await client.createChannel("gcgs", "0721", {})
        client.getChannelFromId(channel="0721")
    await client.connect()
    await client.joinRoom("general")

    input_task = asyncio.create_task(user_input_loop(client))

    await input_task

if __name__ == "__main__":
    asyncio.run(main())