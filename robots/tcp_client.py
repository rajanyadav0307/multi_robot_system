# robots/tcp_client.py
import asyncio
import json
import time
import psutil
from common.config import SUPERVISOR_IP, SUPERVISOR_PORT, HEARTBEAT_INTERVAL
from common.utils import get_robot_id, get_timestamp

robot_id = get_robot_id()


async def send_heartbeat(writer):
    while True:
        writer.write(json.dumps({"type": "heartbeat"}).encode() + b"\n")
        await writer.drain()
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def send_telemetry(writer):
    start = time.time()
    while True:
        uptime = int(time.time() - start)

        try:
            batt = psutil.sensors_battery()
            battery = float(batt.percent) if batt else 0.0
        except:
            battery = 0.0

        telem = {
            "battery_percent": round(battery, 2),
            "cpu_percent": round(psutil.cpu_percent(), 2),
            "memory_percent": round(psutil.virtual_memory().percent, 2),
            "uptime_sec": uptime,
            "last_seen": get_timestamp(),
        }

        writer.write(json.dumps({"type": "telemetry", "payload": telem}).encode() + b"\n")
        await writer.drain()
        await asyncio.sleep(HEARTBEAT_INTERVAL * 2)


async def handle_server(reader, writer):
    while True:
        line = await reader.readline()
        if not line:
            break

        msg = json.loads(line.decode())
        task = msg.get("cmd") or msg.get("task")

        if task:
            writer.write(json.dumps({"type": "ack", "task": task}).encode() + b"\n")
            await writer.drain()
            await asyncio.sleep(1)
            writer.write(json.dumps({"type": "ack", "task": task}).encode() + b"\n")
            await writer.drain()


async def robot_main():
    while True:
        try:
            reader, writer = await asyncio.open_connection(SUPERVISOR_IP, SUPERVISOR_PORT)
            writer.write((robot_id + "\n").encode())
            await writer.drain()

            hb = asyncio.create_task(send_heartbeat(writer))
            telem = asyncio.create_task(send_telemetry(writer))
            await handle_server(reader, writer)

        except:
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(robot_main())
