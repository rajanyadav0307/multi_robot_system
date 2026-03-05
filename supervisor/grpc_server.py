import asyncio
import json
import time
import uuid

import paho.mqtt.client as mqtt
import redis
from redis.exceptions import RedisError

from common.command_store import (
    create_command,
    get_command,
    get_command_for_idempotency,
    mark_command_failed,
    mark_command_published,
)
from common.config import (
    GRPC_BIND_IP,
    GRPC_PORT,
    MQTT_BROKER,
    MQTT_PORT,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
)


def _load_grpc_runtime():
    try:
        import grpc
    except Exception as exc:
        raise RuntimeError(
            "grpcio is not installed. Install dependencies and generate stubs first."
        ) from exc

    try:
        from grpc_api.generated import fleetops_pb2, fleetops_pb2_grpc
    except Exception as exc:
        raise RuntimeError(
            "gRPC stubs are missing. Run: python scripts/generate_grpc_stubs.py"
        ) from exc

    return grpc, fleetops_pb2, fleetops_pb2_grpc


def _decode_if_bytes(value):
    return value.decode() if isinstance(value, bytes) else value


class FleetOpsService:
    def __init__(self, pb2, mqtt_client):
        self.pb2 = pb2
        self.mqtt_client = mqtt_client
        self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

    def _robot_state_list(self):
        robots = []
        try:
            entries = self.redis_client.hgetall("robots")
        except RedisError as exc:
            print(f"[GRPC] Redis read failed for robots: {exc}")
            return robots

        for raw_key, raw_value in entries.items():
            try:
                robot_id = _decode_if_bytes(raw_key)
                state = json.loads(_decode_if_bytes(raw_value))
            except Exception:
                continue

            robots.append(
                self.pb2.RobotState(
                    robot_id=robot_id,
                    status=state.get("status", "disconnected"),
                    last_task=state.get("last_task", "idle"),
                    last_task_output=state.get("last_task_output", ""),
                    last_command_id=state.get("last_command_id", ""),
                    last_seen=int(state.get("last_seen", 0)),
                    battery_percent=float(state.get("battery_percent", 0.0)),
                    cpu_percent=float(state.get("cpu_percent", 0.0)),
                    memory_percent=float(state.get("memory_percent", 0.0)),
                    uptime_sec=int(state.get("uptime_sec", 0)),
                )
            )
        return robots

    async def DispatchCommand(self, request, context):
        robot_id = request.robot_id.strip()
        cmd = request.cmd.strip()
        cmd_type = request.type.strip() or "command"
        requested_by = request.requested_by.strip() or "grpc"
        idempotency_key = request.idempotency_key.strip()

        if not robot_id or not cmd:
            return self.pb2.DispatchCommandResponse(
                command_id="",
                state="failed",
                deduplicated=False,
                message="robot_id and cmd are required",
            )

        existing = get_command_for_idempotency(idempotency_key) if idempotency_key else None
        if existing:
            return self.pb2.DispatchCommandResponse(
                command_id=existing.get("command_id", ""),
                state=existing.get("state", "unknown"),
                deduplicated=True,
                message="Command deduplicated using idempotency_key",
            )

        command_id = str(uuid.uuid4())
        create_command(
            command_id=command_id,
            target=robot_id,
            cmd=cmd,
            cmd_type=cmd_type,
            source=requested_by,
            idempotency_key=idempotency_key,
        )

        mqtt_topic = f"robot/{robot_id}/commands"
        payload = {
            "cmd": cmd,
            "type": cmd_type,
            "command_id": command_id,
            "requested_at": int(time.time()),
            "deadline_ms": int(request.deadline_ms),
            "requested_by": requested_by,
        }
        info = self.mqtt_client.publish(mqtt_topic, json.dumps(payload))
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            mark_command_failed(command_id, f"mqtt_publish_failed_rc={info.rc}")
            return self.pb2.DispatchCommandResponse(
                command_id=command_id,
                state="failed",
                deduplicated=False,
                message=f"MQTT publish failed rc={info.rc}",
            )

        mark_command_published(command_id, mqtt_topic)
        return self.pb2.DispatchCommandResponse(
            command_id=command_id,
            state="published",
            deduplicated=False,
            message="Command accepted",
        )

    async def GetCommandStatus(self, request, context):
        command_id = request.command_id.strip()
        record = get_command(command_id)
        if not record:
            return self.pb2.GetCommandStatusResponse(found=False)

        status = self.pb2.CommandStatus(
            command_id=record.get("command_id", ""),
            target=record.get("target", ""),
            cmd=record.get("cmd", ""),
            type=record.get("type", "command"),
            state=record.get("state", "unknown"),
            created_at=int(record.get("created_at", 0)),
            updated_at=int(record.get("updated_at", 0)),
            source=record.get("source", ""),
            error=record.get("error", ""),
            result_output=record.get("result_output", ""),
            ack_type=record.get("ack_type", ""),
        )
        return self.pb2.GetCommandStatusResponse(found=True, status=status)

    async def ListRobots(self, request, context):
        return self.pb2.ListRobotsResponse(robots=self._robot_state_list())

    async def StreamRobotStates(self, request, context):
        interval_ms = int(request.interval_ms or 1000)
        interval_sec = max(0.2, interval_ms / 1000.0)
        try:
            while True:
                yield self.pb2.ListRobotsResponse(robots=self._robot_state_list())
                await asyncio.sleep(interval_sec)
        except asyncio.CancelledError:
            return


async def serve():
    grpc, fleetops_pb2, fleetops_pb2_grpc = _load_grpc_runtime()

    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        mqtt_client = mqtt.Client()

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    except Exception as exc:
        print(f"[GRPC] MQTT initial connect failed: {exc}")
    mqtt_client.loop_start()

    server = grpc.aio.server()
    service = FleetOpsService(fleetops_pb2, mqtt_client)

    class FleetOpsAdapter(fleetops_pb2_grpc.FleetOpsServicer):
        def __init__(self, impl):
            self._impl = impl

        async def DispatchCommand(self, request, context):
            return await self._impl.DispatchCommand(request, context)

        async def GetCommandStatus(self, request, context):
            return await self._impl.GetCommandStatus(request, context)

        async def ListRobots(self, request, context):
            return await self._impl.ListRobots(request, context)

        async def StreamRobotStates(self, request, context):
            async for item in self._impl.StreamRobotStates(request, context):
                yield item

    servicer = FleetOpsAdapter(service)

    fleetops_pb2_grpc.add_FleetOpsServicer_to_server(servicer, server)

    listen_addr = f"{GRPC_BIND_IP}:{GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    print(f"[GRPC] Listening on {listen_addr}")

    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        mqtt_client.loop_stop()
        try:
            mqtt_client.disconnect()
        except Exception:
            pass


def main():
    asyncio.run(serve())


if __name__ == "__main__":
    main()
