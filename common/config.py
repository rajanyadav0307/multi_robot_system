import os


def _get_int(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[CONFIG] Invalid int for {name}={raw!r}, using {default}")
        return default


# Supervisor TCP server
# Use SUPERVISOR_HOST for clients that connect to the server.
SUPERVISOR_BIND_IP = os.getenv("SUPERVISOR_BIND_IP", os.getenv("SUPERVISOR_IP", "0.0.0.0"))
SUPERVISOR_HOST = os.getenv("SUPERVISOR_HOST", "127.0.0.1")
SUPERVISOR_PORT = _get_int("SUPERVISOR_PORT", 8888)

# Backward-compatible alias used by existing imports.
SUPERVISOR_IP = SUPERVISOR_BIND_IP

# Heartbeat/timeout (seconds)
HEARTBEAT_INTERVAL = _get_int("HEARTBEAT_INTERVAL", 5)    # robot heartbeat interval
HEARTBEAT_TIMEOUT = _get_int("HEARTBEAT_TIMEOUT", 15)     # consider robot dead if no heartbeat

# Redis
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = _get_int("REDIS_PORT", 6379)
REDIS_DB = _get_int("REDIS_DB", 0)

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = _get_int("MQTT_PORT", 1883)

# Web monitor
WEB_MONITOR_BIND_IP = os.getenv("WEB_MONITOR_BIND_IP", os.getenv("WEB_MONITOR_IP", "0.0.0.0"))
WEB_MONITOR_PORT = _get_int("WEB_MONITOR_PORT", 8000)

# Backward-compatible alias used by existing imports.
WEB_MONITOR_IP = WEB_MONITOR_BIND_IP
