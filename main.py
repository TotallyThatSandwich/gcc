import pymongo as pm
import settings
from flask import Flask, jsonify, request

client = pm.MongoClient(settings.MONGO_ADDRESS, username=settings.MONGO_USER, password=settings.MONGO_PASS)
db = client["db"]
users = db["users"]
channels = db["channels"]

app = Flask(__name__)

@app.route('/user/<userId>', methods=['GET'])
def get_user(userId):
        user = users.find_one({ "userId": userId })
        if user is None:
                return jsonify({"error": "User not found"}), 404
        return jsonify({"username": user["username"], "userId": user["userId"]}), 200

# channels
@app.route('/channels', methods=['POST'])
def post_channel():
        data = request.get_json()
        channel = channels.find_one({ "channelId": data["channelId"] })
        if channel is not None:
                return jsonify({"error": "Channel already exists"}), 400
        channels.insert_one({"channelId": data["channelId"], "messages": []})
        return jsonify({"channelId": data["channelId"], "messages": []}), 201

@app.route('/channels', methods=['GET'])
def get_channels():
        channels_list = []
        for channel in channels.find():
                channels_list.append({"channelId": channel["channelId"], "messages": channel["messages"]})
        return jsonify({"channels": channels_list}), 200

@app.route('/channels/<channelId>', methods=['GET'])
def get_channel(channelId):
        channel = channels.find_one({ "channelId": channelId })
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        return jsonify({"channelId": channel["channelId"], "messages": channel["messages"]}), 200

#messages
@app.route('/channels/<channelId>/messages', methods=['POST'])
def post_message(channelId):
        data = request.get_json()
        channel = channels.find_one({ "channelId": channelId })
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        channel["messages"].append({"messageId": data["messageId"], "message": data["message"]})
        channels.update_one({ "channelId": channelId }, { "$set": { "messages": channel["messages"] } })
        return jsonify({"message": data["message"]}), 201

@app.route('/channels/<channelId>/messages', methods=['GET'])
def get_messages(channelId):
        channel = channels.find_one({ "channelId": channelId })
        if channel is None:
                return jsonify({"error": "Channel not found"}), 404
        return jsonify({"messages": channel["messages"]}), 200


if __name__ == "__main__":
        app.run(debug=True)
