import asyncio
import json
import time
import redis
from common.config import SUPERVISOR_IP, SUPERVISOR_PORT, HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT, REDIS_HOST, REDIS_PORT
from common.utils import get_timestamp
from supervisor.state import connected_robots
from supervisor.mqtt_gateway import MQTTGateway

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
last_heartbeat = {}

def make_robot_state(overrides=None):
    base = {
        "status": "disconnected",
        "last_task": "idle",
        "last_seen": get_timestamp(),
        "battery_percent": 0.0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "uptime_sec": 0
    }
    if overrides:
        base.update(overrides)
    return base

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"[TCP SERVER] Incoming connection from {addr}")

    robot_id = None
    try:
        raw = await reader.readline()
        if not raw:
            writer.close()
            await writer.wait_closed()
            return

        robot_id = raw.decode().strip()
        connected_robots[robot_id] = writer
        last_heartbeat[robot_id] = time.time()

        state = make_robot_state({"status": "alive", "last_seen": get_timestamp()})
        r.hset("robots", robot_id, json.dumps(state))

        print(f"[TCP SERVER] ✅ Robot connected: {robot_id}")

        while True:
            line = await reader.readline()
            if not line:
                break

            msg = json.loads(line.decode())
            mtype = msg.get("type")

            if mtype == "heartbeat":
                last_heartbeat[robot_id] = time.time()
                cur = json.loads(r.hget("robots", robot_id))
                cur["status"] = "alive"
                cur["last_seen"] = get_timestamp()
                r.hset("robots", robot_id, json.dumps(cur))

            elif mtype == "telemetry":
                payload = msg.get("payload", {})
                cur = json.loads(r.hget("robots", robot_id))
                cur.update({
                    "battery_percent": float(payload.get("battery_percent", 0.0)),
                    "cpu_percent": float(payload.get("cpu_percent", 0.0)),
                    "memory_percent": float(payload.get("memory_percent", 0.0)),
                    "uptime_sec": int(payload.get("uptime_sec", 0)),
                    "last_seen": get_timestamp()
                })
                r.hset("robots", robot_id, json.dumps(cur))

            elif mtype == "ack":
                task = msg.get("task", "unknown")
                cur = json.loads(r.hget("robots", robot_id))

                cur["last_task"] = task
                cur["last_ack_time"] = get_timestamp()  # track recent ACK
                cur["last_seen"] = get_timestamp()

                # Maintain last 20 ACKs
                history = cur.get("ack_history", [])
                history.append({"task": task, "time": get_timestamp()})
                if len(history) > 20:
                    history.pop(0)
                cur["ack_history"] = history

                r.hset("robots", robot_id, json.dumps(cur))

    except Exception as e:
        print(f"[TCP SERVER] ❌ Exception for {robot_id}: {e}")

    finally:
        if robot_id:
            cur = json.loads(r.hget("robots", robot_id))
            cur["status"] = "disconnected"
            cur["last_seen"] = get_timestamp()
            r.hset("robots", robot_id, json.dumps(cur))

            connected_robots.pop(robot_id, None)
            last_heartbeat.pop(robot_id, None)
            print(f"[TCP SERVER] Cleaned up robot: {robot_id}")

        writer.close()
        await writer.wait_closed()

async def monitor_heartbeats():
    while True:
        now = time.time()
        for rid, ts in list(last_heartbeat.items()):
            if now - ts > HEARTBEAT_TIMEOUT:
                cur = json.loads(r.hget("robots", rid))
                cur["status"] = "disconnected"
                cur["last_seen"] = get_timestamp()
                r.hset("robots", rid, json.dumps(cur))
                connected_robots.pop(rid, None)
                last_heartbeat.pop(rid, None)
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def main():
    server = await asyncio.start_server(handle_client, SUPERVISOR_IP, SUPERVISOR_PORT)
    print(f"[TCP SERVER] Listening on {SUPERVISOR_IP}:{SUPERVISOR_PORT}")

    # Start heartbeat monitor
    asyncio.create_task(monitor_heartbeats())

    # Start MQTT gateway
    mqtt_gateway = MQTTGateway()
    mqtt_gateway.start()

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
