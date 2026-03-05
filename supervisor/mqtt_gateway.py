import asyncio
import json
import paho.mqtt.client as mqtt
from common.command_store import mark_command_dispatched, mark_command_failed
from common.config import MQTT_BROKER, MQTT_PORT
from supervisor.state import connected_robots

class MQTTGateway:
    """Bridges MQTT commands → TCP robots (same-process only)"""

    def __init__(self, loop):
        self.loop = loop
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except Exception:
            self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.connected = False

    def start(self):
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
            self.client.loop_start()
            print(f"[MQTT] Gateway starting at {MQTT_BROKER}:{MQTT_PORT}")
        except Exception as e:
            print("[MQTT] ❌ Connection failed:", e)

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.connected = True
            self.client.subscribe("robot/+/commands")
            print("[MQTT] ✅ Gateway connected and listening")
        else:
            self.connected = False
            print(f"[MQTT] ❌ Connect returned rc={rc}")

    def on_disconnect(self, client, userdata, flags=None, rc=0, properties=None):
        self.connected = False
        if rc != 0:
            print(f"[MQTT] ⚠️ Unexpected disconnect rc={rc}")
        else:
            print("[MQTT] Disconnected")

    async def _forward_to_robot(self, writer, payload):
        writer.write(payload)
        await writer.drain()

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            robot_id = msg.topic.split("/")[1]
            cmd = payload.get("cmd", "noop")
            cmd_type = payload.get("type", "command")
            command_id = payload.get("command_id")

            print(f"[MQTT] 📥 Command for {robot_id}: {cmd} ({cmd_type}) id={command_id}")

            if robot_id not in connected_robots:
                print(f"[MQTT] ❌ Robot {robot_id} NOT connected")
                if command_id:
                    mark_command_failed(command_id, f"robot_not_connected:{robot_id}")
                return

            writer = connected_robots[robot_id]
            tcp_payload = {
                "type": cmd_type,
                "cmd": cmd,
            }
            if command_id:
                tcp_payload["command_id"] = command_id

            tcp_msg = json.dumps(tcp_payload).encode() + b"\n"
            fut = asyncio.run_coroutine_threadsafe(
                self._forward_to_robot(writer, tcp_msg),
                self.loop,
            )
            fut.result(timeout=5)
            if command_id:
                mark_command_dispatched(command_id)
            print(f"[MQTT] ✅ Forwarded command to {robot_id} id={command_id}")

        except Exception as e:
            print("[MQTT] ❌ Error handling message:", e)
            if "command_id" in locals() and command_id:
                mark_command_failed(command_id, str(e))
