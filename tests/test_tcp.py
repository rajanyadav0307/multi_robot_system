import asyncio
from common.config import SUPERVISOR_IP, SUPERVISOR_PORT
from common.message_protocol import encode_message

async def send_command_to_robot(robot_id, command, payload):
    """Connect to supervisor and send a command for testing."""
    reader, writer = await asyncio.open_connection(SUPERVISOR_IP, SUPERVISOR_PORT)
    
    # Send robot_id to simulate registration (for test only)
    writer.write((robot_id + '\n').encode())
    await writer.drain()

    # Send the command
    msg = encode_message({
        "type": "command",
        "command": command,
        "payload": payload
    })
    writer.write(msg + b'\n')
    await writer.drain()
    print(f"[TEST] Command '{command}' sent to {robot_id}")

    writer.close()
    await writer.wait_closed()

async def main():
    # Replace with your robot MAC or test ID
    test_robot_id = "aa:bb:cc:dd:ee:ff"
    await send_command_to_robot(test_robot_id, "move", {"x":10, "y":20})

if __name__ == "__main__":
    asyncio.run(main())
