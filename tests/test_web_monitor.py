import redis

from supervisor import web_monitor


def test_get_robot_states_handles_redis_failure(monkeypatch):
    def _boom(*args, **kwargs):
        raise redis.exceptions.ConnectionError("redis down")

    monkeypatch.setattr(web_monitor.r, "hgetall", _boom)
    assert web_monitor.get_robot_states() == {}


def test_publish_command_surfaces_mqtt_failure(monkeypatch):
    class PublishResult:
        rc = 4

    monkeypatch.setattr(web_monitor.mqtt_client, "publish", lambda *args, **kwargs: PublishResult())

    try:
        web_monitor.publish_command("robot_a", "move", "command")
    except RuntimeError as exc:
        assert "MQTT publish failed" in str(exc)
    else:
        raise AssertionError("publish_command should raise when MQTT returns error")
