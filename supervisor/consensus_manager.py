import asyncio
from common.message_protocol import encode_message

class ConsensusManager:
    """Manages task distribution and waits for ACKs from multiple robots."""

    def __init__(self, connected_robots):
        self.connected_robots = connected_robots
        self.pending_acks = {}  # task_id -> set of robot_ids
        self.lock = asyncio.Lock()

    async def assign_task(self, task_id, robot_ids, command, payload):
        """Send a task to multiple robots and wait for ACKs."""
        async with self.lock:
            self.pending_acks[task_id] = set(robot_ids)

        # Send command to all robots
        for rid in robot_ids:
            if rid in self.connected_robots:
                writer = self.connected_robots[rid]["writer"]
                msg = encode_message({
                    "type": "command",
                    "command": command,
                    "payload": payload,
                    "task_id": task_id
                })
                writer.write(msg + b'\n')
                await writer.drain()
                print(f"[CONSENSUS] Task '{task_id}' sent to {rid}")

        # Wait until all ACKs are received
        while True:
            async with self.lock:
                if not self.pending_acks[task_id]:
                    print(f"[CONSENSUS] Task '{task_id}' completed by all robots")
                    break
            await asyncio.sleep(0.1)  # avoid busy-waiting

    async def handle_ack(self, robot_id, task_id):
        """Remove robot from pending ACKs when ACK is received."""
        async with self.lock:
            if task_id in self.pending_acks and robot_id in self.pending_acks[task_id]:
                self.pending_acks[task_id].remove(robot_id)
                print(f"[CONSENSUS] Received ACK from {robot_id} for task {task_id}")
