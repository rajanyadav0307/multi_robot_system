from common import command_store


class FakeRedis:
    def __init__(self):
        self.hashes = {}

    def hset(self, key, field, value):
        self.hashes.setdefault(key, {})[field] = value

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)


def test_command_store_lifecycle(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(command_store, "r", fake)

    command_store.create_command(
        command_id="cmd-1",
        target="robot_a",
        cmd="scan",
        cmd_type="command",
        source="test",
        idempotency_key="idem-1",
    )
    rec = command_store.get_command("cmd-1")
    assert rec["state"] == "queued"
    assert rec["target"] == "robot_a"

    command_store.mark_command_published("cmd-1", "robot/robot_a/commands")
    rec = command_store.get_command("cmd-1")
    assert rec["state"] == "published"

    command_store.mark_command_dispatched("cmd-1")
    rec = command_store.get_command("cmd-1")
    assert rec["state"] == "dispatched"

    command_store.mark_command_completed("cmd-1", output="ok", ack_type="ack")
    rec = command_store.get_command("cmd-1")
    assert rec["state"] == "acknowledged"
    assert rec["result_output"] == "ok"
    assert rec["ack_type"] == "ack"

    dedup = command_store.get_command_for_idempotency("idem-1")
    assert dedup["command_id"] == "cmd-1"


def test_command_mark_failed(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(command_store, "r", fake)

    command_store.create_command(
        command_id="cmd-2",
        target="robot_b",
        cmd="move",
        source="test",
    )
    command_store.mark_command_failed("cmd-2", "robot_offline")
    rec = command_store.get_command("cmd-2")
    assert rec["state"] == "failed"
    assert rec["error"] == "robot_offline"
