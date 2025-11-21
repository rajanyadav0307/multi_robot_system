import socket
import json
from common.config import SUPERVISOR_IP, SUPERVISOR_PORT

def send_command_to_supervisor(command: dict, host=SUPERVISOR_IP, port=SUPERVISOR_PORT):
    """Send a JSON command to the supervisor TCP server"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall((json.dumps(command) + "\n").encode())
        print(f"[TEST] Command sent: {command}")
    except ConnectionRefusedError:
        print("[ERROR] Supervisor not running or connection refused")

if __name__ == "__main__":
    # Example command: move all robots to x=10, y=20
    command = {
        "type": "command",
        "target": "all",          # can be specific robot ID or "all"
        "cmd": "move",
        "payload": {"x": 10, "y": 20}
    }
    send_command_to_supervisor(command)
