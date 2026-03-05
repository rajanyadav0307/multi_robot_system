import json
import time

import redis
from redis.exceptions import RedisError

from common.config import REDIS_DB, REDIS_HOST, REDIS_PORT


COMMANDS_HASH_KEY = "commands"
IDEMPOTENCY_HASH_KEY = "command_idempotency"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


def _now_ts():
    return int(time.time())


def _save_command(command_id, command_record):
    try:
        r.hset(COMMANDS_HASH_KEY, command_id, json.dumps(command_record))
    except RedisError as exc:
        print(f"[COMMAND STORE] Redis write failed for {command_id}: {exc}")


def get_command(command_id):
    if not command_id:
        return None

    try:
        raw = r.hget(COMMANDS_HASH_KEY, command_id)
    except RedisError as exc:
        print(f"[COMMAND STORE] Redis read failed for {command_id}: {exc}")
        return None

    if not raw:
        return None

    try:
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)
    except Exception:
        return None


def get_command_for_idempotency(idempotency_key):
    if not idempotency_key:
        return None

    try:
        raw = r.hget(IDEMPOTENCY_HASH_KEY, idempotency_key)
    except RedisError as exc:
        print(f"[COMMAND STORE] Redis idempotency read failed: {exc}")
        return None

    if not raw:
        return None

    command_id = raw.decode() if isinstance(raw, bytes) else str(raw)
    return get_command(command_id)


def create_command(
    command_id,
    target,
    cmd,
    cmd_type="command",
    source="unknown",
    idempotency_key=None,
):
    now = _now_ts()
    record = {
        "command_id": command_id,
        "target": target,
        "cmd": cmd,
        "type": cmd_type or "command",
        "state": "queued",
        "source": source,
        "idempotency_key": idempotency_key or "",
        "created_at": now,
        "updated_at": now,
        "mqtt_topic": "",
        "error": "",
        "result_output": "",
        "ack_type": "",
    }
    _save_command(command_id, record)

    if idempotency_key:
        try:
            r.hset(IDEMPOTENCY_HASH_KEY, idempotency_key, command_id)
        except RedisError as exc:
            print(f"[COMMAND STORE] Redis idempotency write failed: {exc}")

    return record


def _update_command(command_id, updates):
    record = get_command(command_id)
    if not record:
        return None

    record.update(updates)
    record["updated_at"] = _now_ts()
    _save_command(command_id, record)
    return record


def mark_command_published(command_id, mqtt_topic):
    return _update_command(
        command_id,
        {
            "state": "published",
            "mqtt_topic": mqtt_topic,
            "error": "",
        },
    )


def mark_command_dispatched(command_id):
    return _update_command(
        command_id,
        {
            "state": "dispatched",
            "error": "",
        },
    )


def mark_command_failed(command_id, error):
    return _update_command(
        command_id,
        {
            "state": "failed",
            "error": str(error),
        },
    )


def mark_command_completed(command_id, output, ack_type="ack"):
    return _update_command(
        command_id,
        {
            "state": "acknowledged",
            "result_output": output or "",
            "ack_type": ack_type,
            "error": "",
        },
    )
