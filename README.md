# Multi Robot System

Distributed Python system for supervising multiple robots over TCP, relaying commands through MQTT, and monitoring status through a FastAPI dashboard.

## Why this is relevant for backend tooling roles
- Multi-service backend architecture (TCP + HTTP/WebSocket + MQTT + Redis + gRPC).
- Traceable command flow with generated `command_id` from API request to robot ACK.
- Operational visibility via `/health`, `/api/robots`, and gRPC state streaming.
- Reliability hardening: configurable runtime, reconnect-safe messaging, and runtime verification script.

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
│   ├── command_store.py     # Redis-backed command state machine
│   ├── message_protocol.py  # JSON encode/decode helpers
│   └── utils.py             # Timestamps + robot id from MAC
├── grpc_api/
│   └── generated/           # Generated protobuf/grpc Python stubs
├── proto/
│   └── fleetops.proto       # FleetOps gRPC API contract
├── robots/
│   ├── tcp_client.py        # Robot runtime: heartbeat, telemetry, command handling
│   └── consensus_client.py
├── supervisor/
│   ├── tcp_server.py        # Main TCP supervisor + heartbeat monitor + MQTT bridge
│   ├── grpc_server.py       # FleetOps gRPC server
│   ├── mqtt_gateway.py      # MQTT -> TCP forwarding
│   ├── web_monitor.py       # FastAPI app + WebSocket + MQTT publisher
│   ├── dashboard.html       # Web UI
│   └── consensus_manager.py
├── scripts/
│   ├── generate_grpc_stubs.py
│   ├── grpc_demo_client.py
│   └── verify_runtime.py
├── tests/
│   ├── test_command_store.py
│   ├── test_config.py
│   ├── test_message_protocol.py
│   └── test_web_monitor.py
└── requirements.txt
```

## Prerequisites
- Python 3.10+ (tested locally with Python 3.12)
- Docker (recommended) or native Redis + MQTT services

## 1) Create and activate virtual environment
From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Shortcut:
```bash
make install
```

## 2) Configure hosts/ports
Edit `common/config.py` if needed.

Default configuration is local-friendly:
- `SUPERVISOR_BIND_IP=0.0.0.0` (server bind)
- `SUPERVISOR_HOST=127.0.0.1` (client connect host)
- `REDIS_HOST=127.0.0.1`
- `MQTT_BROKER=127.0.0.1`
- `GRPC_BIND_IP=0.0.0.0`
- `GRPC_HOST=127.0.0.1`
- `GRPC_PORT=50051`

You can override all host/port settings with environment variables.

## 3) Start infrastructure services
Recommended:

```bash
docker compose up -d
```

This starts:
- Redis on `6379`
- Mosquitto MQTT broker on `1883`

Optional native alternative:
- Start Redis (`redis-server`)
- Start Mosquitto (`mosquitto`)

## 4) Verify local runtime dependencies
```bash
python scripts/verify_runtime.py
```

Shortcut:
```bash
make verify
```

## 5) Generate gRPC stubs
```bash
python scripts/generate_grpc_stubs.py
```

Shortcut:
```bash
make generate-grpc
```

## 6) Run the system
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

### Terminal 4: gRPC control plane
```bash
python -m supervisor.grpc_server
```

Equivalent `make` commands:
- `make run-supervisor`
- `make run-web`
- `make run-robot`
- `make run-grpc`

Open dashboard:
- http://127.0.0.1:8000

## 7) Send commands
From the dashboard:
- Select a robot
- Send a normal command like `move` or `scan`
- Send bash commands with prefix `bash:` (example: `bash:uname -a`)

Robot client behavior:
- Normal command -> sends ACK
- Bash command -> executes command and sends output back

The system attaches a `command_id` to each command and surfaces it in the dashboard for traceability.

## API endpoints
- `GET /health` -> service status (`redis`, `mqtt`)
- `GET /api/robots` -> current robot states
- `POST /api/commands` -> publish command to robot
- `GET /api/commands/{command_id}` -> command lifecycle state

Example:
```bash
curl -X POST http://127.0.0.1:8000/api/commands \
  -H "Content-Type: application/json" \
  -d '{"target":"robot_abc","cmd":"scan","type":"command","idempotency_key":"scan-001"}'
```

## gRPC FleetOps API
The gRPC server exposes:
- `DispatchCommand`
- `GetCommandStatus`
- `ListRobots`
- `StreamRobotStates`

Run demo client:
```bash
python scripts/grpc_demo_client.py
```

Shortcut:
```bash
make grpc-demo
```

## Running multiple robots
`robots/tcp_client.py` derives `robot_id` from machine MAC address.  
If you run multiple robot processes on the same machine, they can share the same robot ID and overwrite each other in state.

For local simulation of many robots, use different machines/containers or customize robot ID logic.

## Useful test/helper scripts
- `tests/send_command.py`: sends one JSON command to supervisor TCP port
- `tests/test_tcp.py`: async helper to send a command-style payload
- `tests/consensus_test.py`: consensus manager exercise script
- `pytest -q`: unit tests for config/protocol/web monitor behavior

## Troubleshooting
- `ModuleNotFoundError: redis` (or similar):
  - Activate venv and reinstall: `pip install -r requirements.txt`
- Dashboard loads but no robot appears:
  - Verify `python -m robots.tcp_client` is running
  - Check supervisor logs for robot connection
- MQTT command path not working:
  - Verify broker is running on port `1883`
  - Check `/health` to confirm `mqtt: true`
- gRPC server fails to start with stub import error:
  - Run `python scripts/generate_grpc_stubs.py`
- `grpcio` / `grpc_tools` import errors:
  - Reinstall dependencies: `pip install -r requirements.txt`
- Redis/MQTT connection refused:
  - Confirm services are running and env host/port values are correct

## Security note
`bash:` commands execute directly on the robot client using `subprocess.run(..., shell=True)`.  
Run this project only in trusted environments.
