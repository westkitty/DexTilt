from dextilt_receiver.crypto import generate_token, sign_command, verify_command_signature
from dextilt_receiver.constants import COMMAND_PROTOCOL


def sample_message(receiver_id="receiver-12345678", device_id="device-12345678"):
    return {
        "protocol": COMMAND_PROTOCOL,
        "device_id": device_id,
        "receiver_id": receiver_id,
        "command_id": "notify_test",
        "gesture_id": "manual",
        "timestamp_ms": 1730000000000,
        "nonce": "nonce-123456789",
        "confidence": 100,
    }


def test_sign_and_verify_round_trip():
    secret = generate_token(32)
    msg = sample_message()
    msg["signature"] = sign_command(msg, secret)
    assert verify_command_signature(msg, secret)


def test_invalid_signature_rejected():
    secret = generate_token(32)
    wrong = generate_token(32)
    msg = sample_message()
    msg["signature"] = sign_command(msg, secret)
    assert not verify_command_signature(msg, wrong)
