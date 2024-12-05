import asyncio
import websockets
from requests import request
from hashlib import md5

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
        self.channel = None
        
        self.headers = {"Authorization": self.auth}

    def getAuth(self):
        response = request("POST", "http://localhost:5000/getauth", json={"username":username, "passwordHash": md5(password)})
        response = response.json()

        return response["token"]
    
    def joinRoom(self, room):
        websockets.connect(f"ws://localhost:5000/connect", extra_headers=self.headers)
        
        

    async def sendMessage(self, message):
        headers = self.headers.update({"content": message})
        async with websockets.connect(f"ws://localhost:5000/{self.channel}", extra_headers=headers) as server:
            await server.send(headers)

    def getChannelFromId(self, channel):
        response = request("GET", f"http://localhost:5000/channel/{channel}", headers=self.headers)
        response = response.json()

        return response

