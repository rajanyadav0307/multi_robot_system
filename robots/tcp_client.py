import asyncio
import json
import time
import psutil
import subprocess
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
        batt = psutil.sensors_battery()
        battery = float(batt.percent) if batt else 0.0

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
        try:
            msg = json.loads(line.decode())
            cmd = msg.get("cmd")
            cmd_type = msg.get("type", "command")

            if cmd_type == "bash" and cmd:
                print(f"[ROBOT] ⚡ Executing bash: {cmd}")
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    output = result.stdout + result.stderr
                except Exception as e:
                    output = f"Error: {e}"

                # Send bash output as ACK type
                ack_msg = json.dumps({
                    "type": "bash_output",
                    "task": cmd,
                    "output": output
                }).encode() + b"\n"
                writer.write(ack_msg)
                await writer.drain()
                print(f"[ROBOT] ✅ Sent bash output for {cmd}")

            elif cmd:
                print(f"[ROBOT] ✅ Received command: {cmd}")
                ack_msg = json.dumps({
                    "type": "ack",
                    "task": cmd,
                    "output": ""
                }).encode() + b"\n"
                writer.write(ack_msg)
                await writer.drain()
                print(f"[ROBOT] ✅ Sent ACK for {cmd}")

        except Exception as e:
            print(f"[ROBOT] ❌ Error handling message: {e}")

async def robot_main():
    while True:
        try:
            reader, writer = await asyncio.open_connection(SUPERVISOR_IP, SUPERVISOR_PORT)
            writer.write((robot_id + "\n").encode())
            await writer.drain()

            print(f"[ROBOT] ✅ Connected as {robot_id}")

            hb_task = asyncio.create_task(send_heartbeat(writer))
            telem_task = asyncio.create_task(send_telemetry(writer))
            await handle_server(reader, writer)
        except:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(robot_main())
