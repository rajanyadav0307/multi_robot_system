import importlib

import common.config as config


def test_config_defaults(monkeypatch):
    keys = [
        "SUPERVISOR_BIND_IP",
        "SUPERVISOR_IP",
        "SUPERVISOR_HOST",
        "SUPERVISOR_PORT",
        "HEARTBEAT_INTERVAL",
        "HEARTBEAT_TIMEOUT",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "MQTT_BROKER",
        "MQTT_PORT",
        "WEB_MONITOR_BIND_IP",
        "WEB_MONITOR_IP",
        "WEB_MONITOR_PORT",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    cfg = importlib.reload(config)

    assert cfg.SUPERVISOR_BIND_IP == "0.0.0.0"
    assert cfg.SUPERVISOR_HOST == "127.0.0.1"
    assert cfg.REDIS_HOST == "127.0.0.1"
    assert cfg.MQTT_BROKER == "127.0.0.1"
    assert cfg.WEB_MONITOR_BIND_IP == "0.0.0.0"
    assert cfg.SUPERVISOR_PORT == 8888
    assert cfg.REDIS_PORT == 6379
    assert cfg.MQTT_PORT == 1883
    assert cfg.WEB_MONITOR_PORT == 8000


def test_invalid_port_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_PORT", "bad-int")
    cfg = importlib.reload(config)
    assert cfg.SUPERVISOR_PORT == 8888
