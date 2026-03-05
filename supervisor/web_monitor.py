import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import paho.mqtt.client as mqtt
import redis
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from common.config import REDIS_DB, REDIS_HOST, REDIS_PORT, MQTT_BROKER, MQTT_PORT

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
DASHBOARD_PATH = Path(__file__).with_name("dashboard.html")

clients = []
try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except Exception:
    mqtt_client = mqtt.Client()
mqtt_connected = False


class CommandRequest(BaseModel):
    target: str
    cmd: str
    type: str = "command"


def _on_mqtt_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    mqtt_connected = (rc == 0)
    if mqtt_connected:
        print(f"[WEB MONITOR] MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"[WEB MONITOR] MQTT connect failed rc={rc}")


def _on_mqtt_disconnect(client, userdata, flags=None, rc=0, properties=None):
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:
        print(f"[WEB MONITOR] MQTT disconnected unexpectedly rc={rc}")
    else:
        print("[WEB MONITOR] MQTT disconnected")


mqtt_client.on_connect = _on_mqtt_connect
mqtt_client.on_disconnect = _on_mqtt_disconnect


@asynccontextmanager
async def lifespan(_app):
    """Start and stop background resources cleanly."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    except Exception as exc:
        print(f"[WEB MONITOR] MQTT initial connect failed: {exc}")
    mqtt_client.loop_start()

    task = asyncio.create_task(broadcast_robot_states())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        mqtt_client.loop_stop()
        try:
            mqtt_client.disconnect()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)


def get_robot_states():
    robots = {}
    try:
        entries = r.hgetall("robots")
    except redis.exceptions.RedisError as exc:
        print(f"[WEB MONITOR] Redis read failed: {exc}")
        return robots

    for k, v in entries.items():
        robot_id = k.decode()
        try:
            state = json.loads(v.decode())
            robots[robot_id] = {
                "status": state.get("status", "disconnected"),
                "last_task": state.get("last_task", "idle"),
                "last_task_output": state.get("last_task_output", ""),
                "last_command_id": state.get("last_command_id", ""),
                "last_seen": state.get("last_seen", 0),
                "battery_percent": state.get("battery_percent", 0.0),
                "cpu_percent": state.get("cpu_percent", 0.0),
                "memory_percent": state.get("memory_percent", 0.0),
                "uptime_sec": state.get("uptime_sec", 0),
            }
        except Exception:
            continue

    return robots


def publish_command(target, cmd, cmd_type="command"):
    command_id = str(uuid.uuid4())
    message = {
        "cmd": cmd,
        "type": cmd_type,
        "command_id": command_id,
        "requested_at": int(time.time()),
    }
    info = mqtt_client.publish(f"robot/{target}/commands", json.dumps(message))
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed rc={info.rc}")
    return command_id

async def broadcast_robot_states():
    """Continuously send robot states to all connected WebSocket clients."""
    while True:
        robots = get_robot_states()

        # Broadcast to all clients
        for ws in list(clients):
            try:
                await ws.send_json(robots)
            except Exception:
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
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await ws.send_json({"error": "invalid_json"})
                continue

            target = msg.get("target")
            cmd = msg.get("cmd")
            cmd_type = msg.get("type", "command")  # default normal command
            if target and cmd:
                try:
                    command_id = publish_command(target, cmd, cmd_type)
                    await ws.send_json({"accepted": True, "command_id": command_id})
                except RuntimeError as exc:
                    await ws.send_json({"accepted": False, "error": str(exc)})
    except Exception:
        if ws in clients:
            clients.remove(ws)
    finally:
        if ws in clients:
            clients.remove(ws)


@app.get("/health")
async def health():
    redis_ok = True
    try:
        r.ping()
    except redis.exceptions.RedisError:
        redis_ok = False

    status = "ok" if redis_ok and mqtt_connected else "degraded"
    return {
        "status": status,
        "redis": redis_ok,
        "mqtt": mqtt_connected,
    }


@app.get("/api/robots")
async def robots():
    return get_robot_states()


@app.post("/api/commands")
async def send_command(req: CommandRequest):
    try:
        command_id = publish_command(req.target, req.cmd, req.type)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"published": True, "command_id": command_id}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML page."""
    return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))
