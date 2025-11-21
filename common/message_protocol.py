import json

def encode_message(msg_dict):
    return json.dumps(msg_dict).encode()

def decode_message(msg_bytes):
    return json.loads(msg_bytes.decode())
