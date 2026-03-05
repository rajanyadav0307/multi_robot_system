import asyncio
import json
import time
import redis
from redis.exceptions import RedisError
from common.config import (
    SUPERVISOR_BIND_IP,
    SUPERVISOR_PORT,
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TIMEOUT,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
)
from common.utils import get_timestamp
from supervisor.state import connected_robots
from supervisor.mqtt_gateway import MQTTGateway

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
last_heartbeat = {}

def make_robot_state(overrides=None):
    base = {
        "status": "disconnected",
        "last_task": "idle",
        "last_task_output": "",
        "last_seen": get_timestamp(),
        "battery_percent": 0.0,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "uptime_sec": 0
    }
    if overrides:
        base.update(overrides)
    return base


def load_robot_state(robot_id):
    try:
        raw = r.hget("robots", robot_id)
    except RedisError as exc:
        print(f"[TCP SERVER] ⚠️ Redis read failed for {robot_id}: {exc}")
        return make_robot_state()

    if not raw:
        return make_robot_state()

    try:
        if isinstance(raw, bytes):
            raw = raw.decode()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return make_robot_state()


def save_robot_state(robot_id, state):
    try:
        r.hset("robots", robot_id, json.dumps(state))
    except RedisError as exc:
        print(f"[TCP SERVER] ⚠️ Redis write failed for {robot_id}: {exc}")


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
        if not robot_id:
            print("[TCP SERVER] ⚠️ Empty robot id received, closing connection")
            writer.close()
            await writer.wait_closed()
            return

        previous_writer = connected_robots.get(robot_id)
        if previous_writer and previous_writer is not writer:
            print(f"[TCP SERVER] ℹ️ Replacing existing connection for {robot_id}")
            previous_writer.close()

        connected_robots[robot_id] = writer
        last_heartbeat[robot_id] = time.time()

        state = make_robot_state({"status": "alive", "last_seen": get_timestamp()})
        save_robot_state(robot_id, state)

        print(f"[TCP SERVER] ✅ Robot connected: {robot_id}")

        while True:
            line = await reader.readline()
            if not line:
                break

            try:
                msg = json.loads(line.decode())
            except json.JSONDecodeError:
                print(f"[TCP SERVER] ⚠️ Invalid JSON from {robot_id}: {line!r}")
                continue

            mtype = msg.get("type")

            if mtype == "heartbeat":
                last_heartbeat[robot_id] = time.time()
                cur = load_robot_state(robot_id)
                cur["status"] = "alive"
                cur["last_seen"] = get_timestamp()
                save_robot_state(robot_id, cur)

            elif mtype == "telemetry":
                payload = msg.get("payload", {})
                cur = load_robot_state(robot_id)
                cur.update({
                    "battery_percent": float(payload.get("battery_percent", 0.0)),
                    "cpu_percent": float(payload.get("cpu_percent", 0.0)),
                    "memory_percent": float(payload.get("memory_percent", 0.0)),
                    "uptime_sec": int(payload.get("uptime_sec", 0)),
                    "last_seen": get_timestamp()
                })
                save_robot_state(robot_id, cur)

            elif mtype == "ack":
                task = msg.get("task", "unknown")
                output = msg.get("output", "")
                command_id = msg.get("command_id")
                cur = load_robot_state(robot_id)
                cur["last_task"] = task
                cur["last_task_output"] = output
                if command_id:
                    cur["last_command_id"] = command_id
                cur["last_ack_time"] = get_timestamp()
                cur["last_seen"] = get_timestamp()

                # Maintain last 20 ACKs
                history = cur.get("ack_history", [])
                history.append({
                    "task": task,
                    "output": output,
                    "command_id": command_id,
                    "time": get_timestamp(),
                })
                if len(history) > 20:
                    history.pop(0)
                cur["ack_history"] = history

                save_robot_state(robot_id, cur)

            elif mtype == "bash_output":
                task = msg.get("task", "")
                output = msg.get("output", "")
                command_id = msg.get("command_id")
                cur = load_robot_state(robot_id)
                cur["last_task"] = task
                cur["last_task_output"] = output
                if command_id:
                    cur["last_command_id"] = command_id
                cur["last_seen"] = get_timestamp()

                # Maintain last 20 bash outputs
                history = cur.get("bash_history", [])
                history.append({
                    "task": task,
                    "output": output,
                    "command_id": command_id,
                    "time": get_timestamp(),
                })
                if len(history) > 20:
                    history.pop(0)
                cur["bash_history"] = history

                save_robot_state(robot_id, cur)
            else:
                print(f"[TCP SERVER] ⚠️ Unknown message type from {robot_id}: {mtype}")

    except Exception as e:
        print(f"[TCP SERVER] ❌ Exception for {robot_id}: {e}")

    finally:
        if robot_id:
            cur = load_robot_state(robot_id)
            cur["status"] = "disconnected"
            cur["last_seen"] = get_timestamp()
            save_robot_state(robot_id, cur)

            # Avoid removing a newer connection with the same robot_id.
            if connected_robots.get(robot_id) is writer:
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
                cur = load_robot_state(rid)
                cur["status"] = "disconnected"
                cur["last_seen"] = get_timestamp()
                save_robot_state(rid, cur)

                writer = connected_robots.pop(rid, None)
                if writer:
                    writer.close()
                last_heartbeat.pop(rid, None)
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def main():
    server = await asyncio.start_server(handle_client, SUPERVISOR_BIND_IP, SUPERVISOR_PORT)
    print(f"[TCP SERVER] Listening on {SUPERVISOR_BIND_IP}:{SUPERVISOR_PORT}")

    # Start heartbeat monitor
    asyncio.create_task(monitor_heartbeats())

    # Start MQTT gateway
    mqtt_gateway = MQTTGateway(asyncio.get_running_loop())
    mqtt_gateway.start()

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
