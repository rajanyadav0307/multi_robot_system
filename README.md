# Multi Robot System

Distributed Python system for supervising multiple robots over TCP, relaying commands through MQTT, and monitoring status through a FastAPI dashboard.

## What this project does
- Robots connect to a supervisor over TCP.
- Robots send heartbeats + telemetry (`battery`, `cpu`, `memory`, `uptime`).
- Supervisor stores robot state in Redis.
- Dashboard streams robot state over WebSocket and sends commands through MQTT.
- Supervisor MQTT gateway forwards those commands back to connected robots.

## Project structure
```text
multi_robot_system/
├── common/
│   ├── config.py            # Host/port and interval settings
│   ├── message_protocol.py  # JSON encode/decode helpers
│   └── utils.py             # Timestamps + robot id from MAC
├── robots/
│   ├── tcp_client.py        # Robot runtime: heartbeat, telemetry, command handling
│   └── consensus_client.py
├── supervisor/
│   ├── tcp_server.py        # Main TCP supervisor + heartbeat monitor + MQTT bridge
│   ├── mqtt_gateway.py      # MQTT -> TCP forwarding
│   ├── web_monitor.py       # FastAPI app + WebSocket + MQTT publisher
│   ├── dashboard.html       # Web UI
│   └── consensus_manager.py
├── tests/
│   ├── test_tcp.py
│   ├── consensus_test.py
│   └── send_command.py
└── requirements.txt
```

## Prerequisites
- Python 3.10+ (tested locally with Python 3.12)
- Redis server running on port `6379`
- MQTT broker running on port `1883` (for example, Mosquitto)

## 1) Create and activate virtual environment
From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Configure hosts/ports
Edit `common/config.py` if needed.

Important for local development:
- `SUPERVISOR_IP = "0.0.0.0"` is fine for server bind.
- `REDIS_HOST` and `MQTT_BROKER` should typically be `127.0.0.1` (not `0.0.0.0`) when clients connect locally.

Also note:
- `supervisor/mqtt_gateway.py` currently connects to MQTT at `localhost:1883` directly.
- If your broker is remote, update that file (or adapt code to read from config).

## 3) Start infrastructure services
Choose one approach.

### Option A: Docker
```bash
docker run -d --name mrs-redis -p 6379:6379 redis:7
docker run -d --name mrs-mqtt -p 1883:1883 eclipse-mosquitto:2
```

### Option B: Native services
- Start Redis (`redis-server`)
- Start Mosquitto (`mosquitto`)

## 4) Run the system
Use separate terminals.

### Terminal 1: Supervisor TCP server
```bash
python -m supervisor.tcp_server
```

### Terminal 2: Web monitor (FastAPI dashboard)
```bash
uvicorn supervisor.web_monitor:app --host 0.0.0.0 --port 8000
```

### Terminal 3: Robot client
```bash
python -m robots.tcp_client
```

Open dashboard:
- http://127.0.0.1:8000

## 5) Send commands
From the dashboard:
- Select a robot
- Send a normal command like `move` or `scan`
- Send bash commands with prefix `bash:` (example: `bash:uname -a`)

Robot client behavior:
- Normal command -> sends ACK
- Bash command -> executes command and sends output back

## Running multiple robots
`robots/tcp_client.py` derives `robot_id` from machine MAC address.  
If you run multiple robot processes on the same machine, they can share the same robot ID and overwrite each other in state.

For local simulation of many robots, use different machines/containers or customize robot ID logic.

## Useful test/helper scripts
- `tests/send_command.py`: sends one JSON command to supervisor TCP port
- `tests/test_tcp.py`: async helper to send a command-style payload
- `tests/consensus_test.py`: consensus manager exercise script

## Troubleshooting
- `ModuleNotFoundError: redis` (or similar):
  - Activate venv and reinstall: `pip install -r requirements.txt`
- Dashboard loads but no robot appears:
  - Verify `python -m robots.tcp_client` is running
  - Check supervisor logs for robot connection
- MQTT command path not working:
  - Verify broker is running on port `1883`
  - Ensure `web_monitor.py` broker config and `mqtt_gateway.py` broker target match
- Redis/MQTT connection refused:
  - Confirm services are running and host/port in `common/config.py` are correct

## Security note
`bash:` commands execute directly on the robot client using `subprocess.run(..., shell=True)`.  
Run this project only in trusted environments.
