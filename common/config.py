# common/config.py

# Supervisor TCP server
SUPERVISOR_IP = "0.0.0.0"
SUPERVISOR_PORT = 8888

# Heartbeat/timeout (seconds)
HEARTBEAT_INTERVAL = 5         # robot heartbeat interval
HEARTBEAT_TIMEOUT = 15         # consider robot dead after this many seconds without heartbeat

# Redis
REDIS_HOST = "0.0.0.0"
REDIS_PORT = 6379
REDIS_DB = 0

# MQTT (used by web monitor to publish commands; optional)
MQTT_BROKER = "0.0.0.0"
MQTT_PORT = 1883

# Web monitor
WEB_MONITOR_IP = "0.0.0.0"
WEB_MONITOR_PORT = 8000
