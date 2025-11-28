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

# MQTT client for forwarding commands from dashboard
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_start()

async def broadcast_robot_states():
    """Continuously send robot states to all connected WebSocket clients."""
    while True:
        robots = {}
        entries = r.hgetall("robots")
        for k, v in entries.items():
            robot_id = k.decode()
            try:
                state = json.loads(v.decode())
                # Include last_task_output
                robots[robot_id] = {
                    "status": state.get("status", "disconnected"),
                    "last_task": state.get("last_task", "idle"),
                    "last_task_output": state.get("last_task_output", ""),
                    "last_seen": state.get("last_seen", 0),
                    "battery_percent": state.get("battery_percent", 0.0),
                    "cpu_percent": state.get("cpu_percent", 0.0),
                    "memory_percent": state.get("memory_percent", 0.0),
                    "uptime_sec": state.get("uptime_sec", 0)
                }
            except:
                continue

        # Broadcast to all clients
        for ws in list(clients):
            try:
                await ws.send_json(robots)
            except:
                clients.remove(ws)

        await asyncio.sleep(1)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint to receive commands and push robot states."""
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            target = msg.get("target")
            cmd = msg.get("cmd")
            cmd_type = msg.get("type", "command")  # default normal command
            if target and cmd:
                mqtt_client.publish(f"robot/{target}/commands", json.dumps({
                    "cmd": cmd,
                    "type": cmd_type
                }))
    except:
        if ws in clients:
            clients.remove(ws)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML page."""
    return HTMLResponse(open("supervisor/dashboard.html").read())

@app.on_event("startup")
async def startup_event():
    """Start background task to broadcast robot states."""
    asyncio.create_task(broadcast_robot_states())
