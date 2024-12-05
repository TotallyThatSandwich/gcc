import asyncio
import websockets
from requests import request
from hashlib import md5

import websockets.asyncio
import websockets.asyncio.client
import websockets.connection

import settings
username = settings.USERNAME
password = settings.PASSWORD

async def create_channel(channelName:str, channelId:int, channelPerms:dict):
    response = request("POST", "http://localhost:5000/createChannel", json={"channelName":channelName, "channelId":channelId, "channelPerms":channelPerms})
    return response

class Client:
    def __init__(self, username:str, password:str):
        self.username = username
        self.password = password
        self.auth = self.getAuth()
        self.room = None
        self.server = None
        
        self.headers = {"token": self.auth}

    def getAuth(self):
        response = request("POST", "http://localhost:5000/getauth", json={"username":username, "passwordHash": md5(password)})
        response = response.json()

        return response["token"]
    
    async def connect(self):
        self.server:websockets.asyncio.client.ClientConnection = await websockets.connect(f"ws://localhost:5000/{self.channel}", extra_headers=self.headers)
    
    async def joinRoom(self, room):
        if self.server is None:
            return "Not connected to a server"
        
        response = await self.server.send("join_room", {"room":room})
        response = response.json()

        if response["status"] != 401:
            raise Exception("Failed to join room")
        self.room = room

    async def leaveRoom(self):
        if self.server is None:
            return "Not connected to a server"
        if self.room is None:
            return "Not in a room"
        
        response = await self.server.send("leave_room", {"room":self.room})

    async def sendMessage(self, message):
        if self.server is None:
            return "Not connected to a server"
        await self.server.send("send_message", {"content":message})

    def getChannelFromId(self, channel):
        response = request("GET", f"http://localhost:5000/channel/{channel}", headers=self.headers)
        response = response.json()

        return response

