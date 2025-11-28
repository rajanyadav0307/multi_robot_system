# supervisor/state.py

# Shared in-memory state between Supervisor components
connected_robots = {}   # robot_id -> asyncio.StreamWriter
