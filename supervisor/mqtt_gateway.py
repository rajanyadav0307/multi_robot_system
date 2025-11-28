import json
import paho.mqtt.client as mqtt
from supervisor.state import connected_robots

class MQTTGateway:
    """Bridges MQTT commands → TCP robots (same-process only)"""

    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_message = self.on_message

    def start(self):
        try:
            self.client.connect("localhost", 1883)
            self.client.subscribe("robot/+/commands")
            self.client.loop_start()
            print("[MQTT] ✅ Gateway connected and listening")
        except Exception as e:
            print("[MQTT] ❌ Connection failed:", e)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            robot_id = msg.topic.split("/")[1]
            cmd = payload.get("cmd", "noop")
            cmd_type = payload.get("type", "command")

            print(f"[MQTT] 📥 Command for {robot_id}: {cmd} ({cmd_type})")

            if robot_id not in connected_robots:
                print(f"[MQTT] ❌ Robot {robot_id} NOT connected")
                return

            writer = connected_robots[robot_id]
            tcp_msg = json.dumps({
                "type": cmd_type,
                "cmd": cmd
            }).encode() + b"\n"

            writer.write(tcp_msg)
            print(f"[MQTT] ✅ Forwarded command to {robot_id}")

        except Exception as e:
            print("[MQTT] ❌ Error handling message:", e)
