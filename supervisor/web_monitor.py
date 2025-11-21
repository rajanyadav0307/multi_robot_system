# supervisor/web_monitor.py
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import asyncio
import json
import redis
import paho.mqtt.client as mqtt
from common.config import (
    MQTT_BROKER, MQTT_PORT,
    REDIS_HOST, REDIS_PORT,
    WEB_MONITOR_IP, WEB_MONITOR_PORT
)

app = FastAPI()
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

mqtt_client = mqtt.Client()
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()
except Exception:
    print("[WEB MONITOR] MQTT connect failed; commands will be disabled")

clients = []


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

        # broadcast
        for ws in list(clients):
            try:
                await ws.send_json(robots)
            except:
                try:
                    clients.remove(ws)
                except:
                    pass

        await asyncio.sleep(1)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            target = msg.get("target")
            cmd = msg.get("cmd")
            if target and cmd:
                topic = f"robot/{target}/commands"
                try:
                    mqtt_client.publish(topic, json.dumps({"cmd": cmd}))
                except:
                    print("[WEB MONITOR] MQTT publish failed")
    except:
        if websocket in clients:
            clients.remove(websocket)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse("""
<!doctype html>
<html>
<head>
<title>Robot Supervisor Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { padding: 20px; }
  .status-alive { color: green; font-weight: bold; }
  .status-disconnected { color: red; font-weight: bold; }
  .metric { min-width: 90px; }
</style>
</head>
<body>
  <div class="container">
    <h2>Robot Supervisor Dashboard</h2>
    <table id="robotTable" class="table table-striped table-hover">
      <thead>
        <tr>
          <th>Robot ID</th>
          <th>Status</th>
          <th>Last Task</th>
          <th>Last Seen</th>
          <th>Battery (%)</th>
          <th>CPU (%)</th>
          <th>Memory (%)</th>
          <th>Uptime (sec)</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <script>
    const ws = new WebSocket("ws://127.0.0.1:8000/ws");
    ws.onmessage = event => {
      const robots = JSON.parse(event.data);
      const tbody = document.querySelector("#robotTable tbody");
      tbody.innerHTML = "";

      for (const [rid, state] of Object.entries(robots)) {
        const lastSeen = state.last_seen
          ? new Date(state.last_seen * 1000).toLocaleTimeString()
          : "N/A";

        const row = `
          <tr>
            <td>${rid}</td>
            <td class="${state.status === "alive" ? "status-alive" : "status-disconnected"}">
              ${state.status}
            </td>
            <td>${state.last_task || "idle"}</td>
            <td>${lastSeen}</td>
            <td>${state.battery_percent}</td>
            <td>${state.cpu_percent}</td>
            <td>${state.memory_percent}</td>
            <td>${state.uptime_sec}</td>
          </tr>`;
        tbody.insertAdjacentHTML("beforeend", row);
      }
    };
  </script>
</body>
</html>
""")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_robot_states())
