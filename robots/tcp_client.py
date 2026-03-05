import asyncio
import json
import time
import psutil
import subprocess
from common.config import SUPERVISOR_HOST, SUPERVISOR_PORT, HEARTBEAT_INTERVAL
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
            command_id = msg.get("command_id")

            if cmd_type == "bash" and cmd:
                print(f"[ROBOT] ⚡ Executing bash: {cmd} id={command_id}")
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    output = result.stdout + result.stderr
                except Exception as e:
                    output = f"Error: {e}"

                # Send bash output as ACK type
                ack_msg = json.dumps({
                    "type": "bash_output",
                    "task": cmd,
                    "output": output,
                    "command_id": command_id,
                }).encode() + b"\n"
                writer.write(ack_msg)
                await writer.drain()
                print(f"[ROBOT] ✅ Sent bash output for {cmd} id={command_id}")

            elif cmd:
                print(f"[ROBOT] ✅ Received command: {cmd} id={command_id}")
                ack_msg = json.dumps({
                    "type": "ack",
                    "task": cmd,
                    "output": "",
                    "command_id": command_id,
                }).encode() + b"\n"
                writer.write(ack_msg)
                await writer.drain()
                print(f"[ROBOT] ✅ Sent ACK for {cmd} id={command_id}")

        except Exception as e:
            print(f"[ROBOT] ❌ Error handling message: {e}")

async def robot_main():
    while True:
        hb_task = None
        telem_task = None
        writer = None
        try:
            reader, writer = await asyncio.open_connection(SUPERVISOR_HOST, SUPERVISOR_PORT)
            writer.write((robot_id + "\n").encode())
            await writer.drain()

            print(f"[ROBOT] ✅ Connected as {robot_id}")

            hb_task = asyncio.create_task(send_heartbeat(writer))
            telem_task = asyncio.create_task(send_telemetry(writer))
            await handle_server(reader, writer)
        except Exception:
            pass
        finally:
            for task in (hb_task, telem_task):
                if task:
                    task.cancel()
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(robot_main())
