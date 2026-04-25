# Mac Setup

Default receiver port: `47391`.

## Setup

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/setup.sh
```

The setup script creates `.venv`, installs Python dependencies, creates `~/.dextilt/config.json` if missing, and keeps real config/state/log files outside Git.

## Run manually

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/run.sh
```

The receiver prints the dashboard URL and port. Open:

```text
http://127.0.0.1:47391/status
```

The receiver binds to the configured host. The default config uses `0.0.0.0` so the phone can reach the Mac on LAN. Do not expose this port to the public internet.

## Test health

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/test_health.sh
```

## Run core automated tests

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/run_core_tests.sh
```

## Test signed command from Mac

With the receiver running:

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/test_signed_command.sh --command notify_test
```

The signed command script pairs a local test device through the one-time pairing flow and then sends an HMAC-signed command.

## Optional LaunchAgent

Install after manual tests pass:

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/install_launch_agent.sh
```

Uninstall:

```sh
cd ~/Projects/DexTilt/mac_receiver
./scripts/uninstall_launch_agent.sh
```

## Dashboard Dock launcher

v1 uses the local dashboard URL. Create a macOS Shortcut, Automator app, or script-wrapped app named `DexTilt Mac Receiver` that opens `http://127.0.0.1:47391/status`, then drag it to the Dock.
