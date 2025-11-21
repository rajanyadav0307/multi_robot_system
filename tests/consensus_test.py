import asyncio
from supervisor.consensus_manager import ConsensusManager
from supervisor.tcp_server import connected_robots

async def main():
    task_id = "task_001"
    robot_ids = list(connected_robots.keys())
    consensus_mgr = ConsensusManager(connected_robots)
    await consensus_mgr.assign_task(task_id, robot_ids, "move", {"x":10,"y":20})

asyncio.run(main())
