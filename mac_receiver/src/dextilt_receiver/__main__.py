from __future__ import annotations

import argparse

import uvicorn

from .app import create_app
from .config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DexTilt Mac Receiver")
    parser.add_argument("--config", default=None, help="Path to DexTilt receiver config JSON")
    parser.add_argument("--host", default=None, help="Host interface to bind, default from config")
    parser.add_argument("--port", type=int, default=None, help="Port to bind, default 47391")
    parser.add_argument("--dry-run-actions", action="store_true", help="Do not run macOS actions; log what would happen")
    args = parser.parse_args()

    config = load_config(args.config)
    host = args.host or str(config.get("host", "0.0.0.0"))
    port = int(args.port or config.get("port", 47391))
    dry = True if args.dry_run_actions else None
    app = create_app(config_path=args.config, dry_run_actions=dry)
    print("DexTilt Mac Receiver starting")
    print(f"Port: {port}")
    print(f"Dashboard: http://127.0.0.1:{port}/status")
    print("Pair from Android by scanning the QR on the dashboard.")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
