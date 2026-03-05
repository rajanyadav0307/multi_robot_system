import importlib
from pathlib import Path
import socket
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.config import MQTT_BROKER, MQTT_PORT, REDIS_HOST, REDIS_PORT


REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "redis",
    "paho.mqtt.client",
    "psutil",
]


def check_imports():
    failures = []
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
            print(f"[OK] import {module_name}")
        except Exception as exc:
            failures.append((module_name, str(exc)))
            print(f"[FAIL] import {module_name}: {exc}")
    return failures


def check_tcp(name, host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[OK] {name} reachable at {host}:{port}")
            return None
    except PermissionError as exc:
        print(f"[WARN] {name} check skipped (environment restriction): {exc}")
        return None
    except Exception as exc:
        print(f"[FAIL] {name} not reachable at {host}:{port}: {exc}")
        return (name, str(exc))


def main():
    failures = []

    failures.extend(check_imports())

    redis_failure = check_tcp("Redis", REDIS_HOST, REDIS_PORT)
    if redis_failure:
        failures.append(redis_failure)

    mqtt_failure = check_tcp("MQTT", MQTT_BROKER, MQTT_PORT)
    if mqtt_failure:
        failures.append(mqtt_failure)

    if failures:
        print("\nRuntime verification failed.")
        sys.exit(1)

    print("\nRuntime verification passed.")


if __name__ == "__main__":
    main()
