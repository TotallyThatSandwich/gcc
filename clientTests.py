import asyncio
import websockets
from requests import request
from hashlib import md5
import socketio

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
    def __init__(self, username:str, password:str):
        self.username = username
        self.password = password
        self.auth = auth
        self.room = None
        self.channel = None
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        
        self.headers = {"Authentication": self.auth}

    #def getAuth(self):
    #    hasPass = md5(password.encode()).hexdigest()
    #    response = request("POST", "http://localhost:5000/getauth", json={"username":username, "passwordHash": hasPass})
    #    response = response.json()
    #    print(hasPass)
    #    print(response)
    #    return response["token"]
    
    async def connect(self):
        self.sio.connect(f"ws://localhost:5000", namespaces=[f"/{self.channel}"], wait_timeout=10)
        self.sio.wait()
        return "Connected to server"
    
    async def joinRoom(self, room):
        
        response = await self.sio.emit("join_room", {"room":room})
        response = response.json()

        if response["status"] != 201:
            raise Exception("Failed to join room")
        self.room = room
        return response

    async def leaveRoom(self):
        response = await self.sio.emit("on_leave_room", {"room":self.room})
        self.room = None


    async def sendMessage(self, message):
        if self.Room == None or self.channel == None:
            return "Not in a room."
        
        response = await self.sio.emit("send_message", {"content":message})
        response = response.json()
        return response

    def getChannelFromId(self, channel):
        response = request("GET", f"http://localhost:5000/channels/{channel}", headers=self.headers)
        response = response.json()

        self.channel = response["channelId"]

        return response

async def main():
    client = Client(username, password)
    channel = await create_channel("general", "694201", {"read":True, "write":True})
    channel = client.getChannelFromId(channel="694201")
    print(await client.connect())
    print(await client.joinRoom("general"))
    await client.sendMessage("Hello World!")
    

if __name__ == "__main__":
    asyncio.run(main())