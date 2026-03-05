from common.message_protocol import decode_message, encode_message


def test_roundtrip_message_protocol():
    payload = {"type": "heartbeat", "value": 1}
    encoded = encode_message(payload)
    decoded = decode_message(encoded)
    assert decoded == payload
