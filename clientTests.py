import asyncio
import websockets
from requests import request
from hashlib import md5
import socketio

from uuid import uuid4

from rich import print as rprint
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

async def create_channel(channelName:str, channelId:str, channelPerms:dict):
    response = request("POST", "http://localhost:5000/channels/create", headers= {"Authorization": auth}, json={"channelName":channelName, "channelId":channelId, "channelPerms":channelPerms})
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
        self.channel = None
        self.channelName = None
        self.sio = socketio.Client(logger=True, engineio_logger=False)

        self.headers = {"Authentication": self.auth}

        self.console = Console()

        self.prefix = "[bold]<{username} - {time}>[/bold]"

        self.commands = {
            "/exit": lambda self: self.sio.disconnect(),
            "/leave": lambda self: self.leaveRoom(),
            "/join": lambda self: self.joinRoom(self.console.input("[italic]Enter room name[/italic]:")),
            "/create": lambda self: asyncio.run(self.createChannel(self.console.input("[italic]Enter channel name[/italic]: "), str(uuid4()), {})),
    }

    #def getAuth(self):
    #    hasPass = md5(password.encode()).hexdigest()
    #    response = request("POST", "http://localhost:5000/getauth", json={"username":username, "passwordHash": hasPass})
    #    response = response.json()
    #    print(hasPass)
    #    print(response)
    #    return response["token"]

    async def createChannel(self, channelName:str, channelId:str, channelPerms:dict):
        response = request("POST", "http://localhost:5000/channels/create", headers= {"Authorization": self
        .auth}, json={"channelName":channelName, "channelId":channelId, "channelPerms":channelPerms})

        if response.status_code != 201:
            return response["error"]
        return response

    async def signUp(self):
        response = request("POST", "http://localhost:5000/user/new", json={"username":self.username,"email":self.email, "passwordHash": md5(self.password)})
    
        if response.status_code != 201:
            return response["error"]
        response = response.json()
        self.auth = response["token"]

    async def login(self):
        response = request("POST", "http://localhost:5000/getauth", json={"username":self.username, "passwordHash": md5(self.password.encode('utf-8'))})

        if response.status_code!=200:
            await self.signUp()
            return
        
        response = response.json()
        self.auth = response["token"]

    
    async def connect(self):
        with self.console.status(f"Connecting to {self.channelName}...", spinner="aesthetic"):
            try:
                self.sio.connect(f"ws://localhost:5000", wait_timeout=10, namespaces=[f"/{self.channel}"])
                self.sio.on("connect", lambda: print("Connected to server!"))
                self.sio.on("disconnect", self.on_disconnect)
                self.sio.on("receive_message", self.on_message)
                self.console.rule("Connected to server!")
            except Exception as e:
                self.console.print_exception()
                self.console.print("[bold red]Failed to connect to server.[/bold red]")
                self.sio.shutdown()
                return False
            
    # client commands

    
    
    async def joinRoom(self, room):
        self.console.print(f"[bold red]Joining[/bold red] [italic]{room}[/]")
        response = self.sio.call(event="join_room", data = {"room":room, "user": self.username, "token":self.auth}, namespace=f"/{self.channel}")

        if response["status"] != 200:
            return response["message"]
        
        self.room = room
        print(response)
        self.console.rule(f"[bold red]{self.room}[/bold red]")
        return f"Successfully joined room {room} with {response['content']['users']}"

    async def leaveRoom(self):
        response = self.sio.emit("leave_room", {"room":self.room}, namespace=f"/{self.channel}")

        if response['status'] != 200:
            return response['message']
        self.room = None
        return response
    


    async def sendMessage(self, message):
        if self.room == None or self.channel == None:
            return "Not in a room."
        if message[0] == "/":
            if message in list(self.commands.keys()):
                return self.commands[message](self)
            else:
                return self.console.print(f"Command {message} not found.")

        
        self.sio.emit("send_message", {"user": self.username, "content":message, "room": self.room}, namespace=f"/{self.channel}")

    def on_message(self, data):
        print(data)
        author = data["user"]
        message = data["message"]

        self.console.print(self.prefix.format(username=author, time=datetime.now().strftime("%H:%M:%S")) + f" {message}")

    def getChannelFromId(self, channel):
        response = request("GET", f"http://localhost:5000/channels/{channel}", headers=self.headers)

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
    response = request("DELETE", "http://localhost:5000/channels", headers= {"Authorization": auth})

    if response.status_code != 200:
        return response["error"]
    return response

async def populate_channels():
    response = request("POST", "http://localhost:5000/channels/populate", headers= {"Authorization": auth})

    if response.status_code != 200:
        return response["error"]
    return response

async def main():
    #await delete_channels()
    await populate_channels()
    username, password, email = input("username, password, email: ").split(", ")
    client = Client(username, password, email)

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