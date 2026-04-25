PROJECT_NAME = "DexTilt"
DISPLAY_NAME = "DexTilt Mac Receiver"
COMMAND_PROTOCOL = "dextilt.v1"
PAIRING_PROTOCOL = "dextilt.pairing.v1"
DEFAULT_PORT = 47391
GESTURE_SCHEMA_VERSION = "dextilt.gesture.v1"
SIGNING_FIELDS = [
    "protocol",
    "device_id",
    "receiver_id",
    "command_id",
    "gesture_id",
    "timestamp_ms",
    "nonce",
    "confidence",
]
