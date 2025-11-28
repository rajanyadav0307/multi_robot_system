from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import redis
import paho.mqtt.client as mqtt
from common.config import REDIS_HOST, REDIS_PORT, MQTT_BROKER, MQTT_PORT

app = FastAPI()
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

clients = []

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_start()

async def broadcast_robot_states():
    while True:
        robots = {}
        entries = r.hgetall("robots")
        for k, v in entries.items():
            robot_id = k.decode()
            try:
                state = json.loads(v.decode())
                robots[robot_id] = state
            except:
                continue

        for ws in list(clients):
            try:
                await ws.send_json(robots)
            except:
                clients.remove(ws)

        await asyncio.sleep(1)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            target = msg.get("target")
            cmd = msg.get("cmd")
            if target and cmd:
                mqtt_client.publish(f"robot/{target}/commands", json.dumps({"cmd": cmd}))
    except:
        if ws in clients:
            clients.remove(ws)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(open("supervisor/dashboard.html").read())

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_robot_states())
