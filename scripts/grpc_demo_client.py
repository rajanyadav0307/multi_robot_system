import asyncio
import uuid

from common.config import GRPC_HOST, GRPC_PORT


def _load_grpc_runtime():
    try:
        import grpc
    except Exception as exc:
        raise RuntimeError("grpcio is not installed.") from exc

    try:
        from grpc_api.generated import fleetops_pb2, fleetops_pb2_grpc
    except Exception as exc:
        raise RuntimeError(
            "gRPC stubs are missing. Run: python scripts/generate_grpc_stubs.py"
        ) from exc

    return grpc, fleetops_pb2, fleetops_pb2_grpc


async def main():
    grpc, fleetops_pb2, fleetops_pb2_grpc = _load_grpc_runtime()

    target = f"{GRPC_HOST}:{GRPC_PORT}"
    async with grpc.aio.insecure_channel(target) as channel:
        stub = fleetops_pb2_grpc.FleetOpsStub(channel)

        print(f"[GRPC CLIENT] Connected to {target}")

        robot_snapshot = await stub.ListRobots(fleetops_pb2.ListRobotsRequest())
        if robot_snapshot.robots:
            robot_id = robot_snapshot.robots[0].robot_id
        else:
            robot_id = "robot_demo"

        req = fleetops_pb2.DispatchCommandRequest(
            robot_id=robot_id,
            cmd="scan",
            type="command",
            deadline_ms=5000,
            idempotency_key=f"demo-{uuid.uuid4()}",
            requested_by="grpc_demo_client",
        )
        dispatch = await stub.DispatchCommand(req)
        print(
            f"[GRPC CLIENT] Dispatch: id={dispatch.command_id} "
            f"state={dispatch.state} deduplicated={dispatch.deduplicated}"
        )

        status = await stub.GetCommandStatus(
            fleetops_pb2.GetCommandStatusRequest(command_id=dispatch.command_id)
        )
        print(
            f"[GRPC CLIENT] Status found={status.found} "
            f"state={status.status.state if status.found else 'n/a'}"
        )

        stream = stub.StreamRobotStates(
            fleetops_pb2.StreamRobotStatesRequest(interval_ms=1000)
        )
        count = 0
        async for snapshot in stream:
            print(f"[GRPC CLIENT] Snapshot robots={len(snapshot.robots)}")
            count += 1
            if count >= 3:
                stream.cancel()
                break


if __name__ == "__main__":
    asyncio.run(main())
