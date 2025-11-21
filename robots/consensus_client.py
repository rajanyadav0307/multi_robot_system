import asyncio
from common.message_protocol import encode_message

class ConsensusClient:
    """Handles ACK sending for assigned tasks."""

    def __init__(self, robot_id, writer):
        self.robot_id = robot_id
        self.writer = writer

    async def send_ack(self, task_id):
        """Send ACK to supervisor for a task."""
        ack_msg = encode_message({
            "type": "ack",
            "robot_id": self.robot_id,
            "task_id": task_id
        })
        self.writer.write(ack_msg + b'\n')
        await self.writer.drain()
        print(f"[CONSENSUS CLIENT] Sent ACK for task {task_id}")
