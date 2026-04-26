from __future__ import annotations

import base64
import io
import json
from html import escape
from typing import Any


def qr_data_url(payload: dict[str, Any]) -> str:
    import qrcode

    img = qrcode.make(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _command_target(action: dict[str, Any]) -> str:
    return str(action.get("url") or action.get("app") or action.get("key") or action.get("message") or action.get("target") or "")


def render_dashboard(status: dict[str, Any], commands: dict[str, Any] | list[str], log_events: list[dict[str, Any]]) -> str:
    if isinstance(commands, list):
        command_map = {cmd: {"type": "unknown", "label": cmd, "enabled": True} for cmd in commands}
    else:
        command_map = commands

    last_command = status.get("last_command")
    last_error = status.get("last_error")
    last_calibration = status.get("last_calibration")
    paired_devices = status.get("paired_devices", [])

    device_rows = "".join(
        f"<tr><td>{escape(str(d.get('device_name') or 'Android DexTilt'))}</td><td><code>{escape(str(d.get('device_id')))}</code></td><td>{escape(str(d.get('last_source_ip') or '-'))}</td></tr>"
        for d in paired_devices
    ) or "<tr><td colspan='3'>No paired Android device yet.</td></tr>"

    command_rows = "".join(
        f"""<tr>
<td><code>{escape(command_id)}</code><br><span class="muted">{escape(str(action.get('description') or ''))}</span></td>
<td>{escape(str(action.get('label') or command_id))}</td>
<td><code>{escape(str(action.get('type') or ''))}</code></td>
<td><code>{escape(_command_target(action))}</code></td>
<td>{'yes' if action.get('enabled', True) is not False else '<span class="bad">no</span>'}</td>
<td>
<button onclick="testCommand('{escape(command_id)}')">Test</button>
<button class="secondary" onclick="fillCommand('{escape(command_id)}')">Edit</button>
<button class="danger" onclick="deleteCommand('{escape(command_id)}')">Delete</button>
</td>
</tr>"""
        for command_id, action in sorted(command_map.items())
    ) or "<tr><td colspan='6'>No commands configured.</td></tr>"

    last_command_text = escape(json.dumps(last_command, indent=2, sort_keys=True)) if last_command else "None"
    last_calibration_text = escape(json.dumps(last_calibration, indent=2, sort_keys=True)) if last_calibration else "None"
    last_error_text = escape(str(last_error or "None"))
    receiver_id = escape(str(status.get("receiver_id")))
    port = escape(str(status.get("port")))
    paired_count = escape(str(status.get("paired_device_count", 0)))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DexTilt Mac Receiver</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
<style>
:root {{
  --bg:#070d1a; --panel-bg:rgba(8,20,45,.95);
  --border:rgba(0,200,230,.18); --accent:#00e5ff;
  --accent-dim:rgba(0,229,255,.35); --amber:#ff9100;
  --green:#00e676; --red:#ff1744;
  --text-hi:#e8f4f8; --text-lo:rgba(160,200,220,.6);
}}
*{{box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text-hi);margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}
main{{max-width:1400px;margin:0 auto;padding:24px;}}
h1{{font-family:'Orbitron',monospace;font-size:20px;letter-spacing:.06em;margin:0 0 8px;color:var(--text-hi);}}
h2{{font-family:'Orbitron',monospace;font-size:11px;color:var(--text-lo);letter-spacing:.1em;text-transform:uppercase;margin:0 0 14px 0;}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px;}}
.dex-card{{background:var(--panel-bg);border:1px solid var(--border);border-radius:8px;padding:16px;}}
.dex-card.wide{{grid-column:1/-1;}}
.sensor-value{{font-family:'Space Mono',monospace;font-variant-numeric:tabular-nums;color:var(--accent);}}
.sensor-value.flash{{animation:sflash 200ms ease-out;}}
@keyframes sflash{{from{{color:#fff;}}to{{color:var(--accent);}}}}
.status-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);vertical-align:middle;}}
.status-dot.live{{background:var(--accent);animation:spulse 1s ease-in-out infinite;}}
.status-dot.amber{{background:var(--amber);}}
.status-dot.red{{background:var(--red);}}
@keyframes spulse{{0%,100%{{opacity:1;}}50%{{opacity:.3;}}}}
#system-state-strip{{display:flex;flex-wrap:wrap;gap:12px 24px;background:var(--panel-bg);border-bottom:1px solid var(--border);padding:10px 20px;font-size:12px;font-family:'Space Mono',monospace;position:sticky;top:0;z-index:100;}}
#system-state-strip .strip-item{{display:flex;align-items:center;gap:6px;}}
#system-state-strip .strip-label{{color:var(--text-lo);}}
.btn-primary{{background:var(--accent-dim);border:1px solid var(--accent);color:var(--text-hi);font-family:'Orbitron',monospace;font-size:12px;padding:9px 18px;border-radius:6px;cursor:pointer;margin:2px;}}
.btn-primary:hover{{background:rgba(0,229,255,.5);}}
.btn-secondary{{background:transparent;border:1px solid var(--border);color:var(--text-lo);font-size:12px;padding:6px 12px;border-radius:4px;cursor:pointer;margin:2px;}}
.btn-secondary:hover{{border-color:var(--accent);color:var(--text-hi);}}
.btn-danger{{background:transparent;border:1px solid rgba(255,23,68,.5);color:var(--red);font-size:12px;padding:6px 12px;border-radius:4px;cursor:pointer;margin:2px;}}
.btn-danger:hover{{background:rgba(255,23,68,.08);}}
.danger-zone{{border:1px solid rgba(255,23,68,.2);border-radius:6px;padding:8px 12px;margin-top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;}}
.sensor-grid{{display:grid;grid-template-columns:max-content 1fr;gap:3px 16px;font-size:12px;}}
.sensor-grid .sg-label{{color:var(--text-lo);font-family:'Orbitron',monospace;font-size:10px;}}
.queue-bar{{height:4px;background:var(--border);border-radius:2px;margin:6px 0;}}
.queue-bar-fill{{height:100%;background:var(--amber);border-radius:2px;transition:width .5s linear;}}
.log-filter-btn{{background:transparent;border:1px solid var(--border);color:var(--text-lo);font-size:10px;padding:2px 8px;border-radius:3px;cursor:pointer;margin-right:4px;}}
.log-filter-btn.active{{border-color:var(--accent);color:var(--accent);}}
.muted{{color:var(--text-lo);}}
.bad{{color:var(--red);}}
.warn{{color:var(--amber);}}
.ok{{color:var(--green);}}
code,pre{{font-family:'Space Mono',monospace;font-size:11px;}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:rgba(0,0,0,.4);border:1px solid var(--border);border-radius:6px;padding:10px;color:var(--text-hi);max-height:300px;overflow:auto;}}
input,select,textarea{{width:100%;background:rgba(0,0,0,.5);color:var(--text-hi);border:1px solid var(--border);border-radius:6px;padding:8px;font-family:'Space Mono',monospace;font-size:11px;margin:4px 0 8px;}}
label{{display:block;color:var(--text-lo);font-family:'Orbitron',monospace;font-size:10px;letter-spacing:.05em;text-transform:uppercase;margin-top:6px;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
td,th{{border-bottom:1px solid var(--border);padding:7px;text-align:left;vertical-align:top;}}
th{{font-family:'Orbitron',monospace;font-size:10px;color:var(--text-lo);text-transform:uppercase;letter-spacing:.05em;}}
button{{background:var(--accent-dim);color:var(--text-hi);border:1px solid var(--accent);border-radius:5px;padding:5px 11px;cursor:pointer;margin:2px;font-size:12px;}}
button.secondary{{background:transparent;border:1px solid var(--border);color:var(--text-lo);}}
button.danger{{background:transparent;border:1px solid rgba(255,23,68,.5);color:var(--red);}}
img.qr{{background:#fff;border-radius:8px;padding:10px;max-width:200px;display:block;margin-bottom:8px;}}
.formgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;}}
details>summary{{font-family:'Orbitron',monospace;font-size:11px;color:var(--text-lo);cursor:pointer;padding:8px 0;text-transform:uppercase;letter-spacing:.08em;list-style:none;}}
details>summary::before{{content:'\\25B6 ';font-size:9px;}}
details[open]>summary::before{{content:'\\25BC ';}}

/* ── Theme panel ────────────────────────────────────────── */
#theme-panel{{position:fixed;top:0;right:0;bottom:0;width:270px;background:var(--panel-bg);border-left:1px solid var(--border);z-index:200;padding:20px;overflow-y:auto;transform:translateX(100%);transition:transform .2s ease;}}
#theme-panel.open{{transform:translateX(0);}}
.theme-section-label{{font-family:'Orbitron',monospace;font-size:10px;color:var(--text-lo);text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px 0;}}
.theme-swatches{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px;}}
.theme-swatch{{background:transparent;border:2px solid rgba(255,255,255,.1);border-radius:8px;padding:10px;cursor:pointer;text-align:left;width:100%;transition:border-color .15s,box-shadow .15s;}}
.theme-swatch.active{{border-color:var(--accent);box-shadow:0 0 8px var(--accent);}}
.theme-swatch-name{{font-family:'Orbitron',monospace;font-size:10px;letter-spacing:.04em;margin-bottom:6px;}}
.theme-swatch-dots{{display:flex;gap:4px;}}
.theme-swatch-dot{{width:8px;height:8px;border-radius:50%;}}
.fs-btns{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:20px;}}

/* ── Font-size overrides ───────────────────────────────── */
html[data-font-size="comfortable"] code,
html[data-font-size="comfortable"] pre,
html[data-font-size="comfortable"] .sensor-value{{font-size:13px!important;}}
html[data-font-size="comfortable"] .sg-label{{font-size:11px!important;}}
html[data-font-size="comfortable"] td,html[data-font-size="comfortable"] th{{font-size:13px!important;}}
html[data-font-size="comfortable"] #logs-container{{font-size:12px!important;}}
html[data-font-size="comfortable"] #system-state-strip{{font-size:13px;}}
html[data-font-size="comfortable"] .sensor-grid{{font-size:13px;}}

html[data-font-size="large"] code,
html[data-font-size="large"] pre,
html[data-font-size="large"] .sensor-value{{font-size:15px!important;}}
html[data-font-size="large"] .sg-label{{font-size:13px!important;}}
html[data-font-size="large"] td,html[data-font-size="large"] th{{font-size:15px!important;}}
html[data-font-size="large"] #logs-container{{font-size:14px!important;}}
html[data-font-size="large"] #system-state-strip{{font-size:14px;}}
html[data-font-size="large"] .sensor-grid{{font-size:15px;}}
html[data-font-size="large"] h1{{font-size:26px;}}
</style>
</head>
<body>

<div id="system-state-strip">
  <div class="strip-item">
    <span class="status-dot live"></span>
    <span class="strip-label">Receiver</span>
    <span>Running</span>
  </div>
  <div class="strip-item">
    <span id="strip-phone-dot" class="status-dot red"></span>
    <span class="strip-label">Phone</span>
    <span id="strip-phone">Not connected</span>
  </div>
  <div class="strip-item">
    <span class="strip-label">Phase</span>
    <span id="strip-phase">&#8212;</span>
  </div>
  <div class="strip-item">
    <span class="strip-label">Queue</span>
    <span id="strip-queue">empty</span>
  </div>
  <div class="strip-item">
    <span class="strip-label">Last cmd</span>
    <span id="strip-last-cmd">&#8212;</span>
  </div>
  <div class="strip-item" id="strip-live-wrap" style="display:none">
    <span class="status-dot live"></span>
    <span style="color:var(--accent);font-size:10px">Live</span>
  </div>
  <div class="strip-item" style="margin-left:auto">
    <button class="log-filter-btn" onclick="toggleThemePanel()" title="Display &amp; theme settings" style="font-size:15px;padding:1px 7px;line-height:1.4">&#9881;</button>
  </div>
</div>

<div id="theme-panel" role="dialog" aria-label="Display settings">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
    <span style="font-family:'Orbitron',monospace;font-size:13px;color:var(--text-hi);letter-spacing:.08em">Display</span>
    <button class="btn-secondary" onclick="toggleThemePanel()" style="padding:2px 9px;font-size:15px;line-height:1.4">&#10005;</button>
  </div>

  <p class="theme-section-label">Theme</p>
  <div class="theme-swatches" id="theme-swatches"></div>

  <p class="theme-section-label">Font size</p>
  <div class="fs-btns">
    <button class="log-filter-btn" id="fs-btn-compact"      onclick="setFontSize('compact')">Compact</button>
    <button class="log-filter-btn" id="fs-btn-normal"       onclick="setFontSize('normal')">Normal</button>
    <button class="log-filter-btn" id="fs-btn-comfortable"  onclick="setFontSize('comfortable')">Comfortable</button>
    <button class="log-filter-btn" id="fs-btn-large"        onclick="setFontSize('large')">Large</button>
  </div>
</div>

<main>
<h1>DexTilt</h1>
<p style="font-family:'Space Mono',monospace;font-size:11px;color:var(--text-lo);margin:0 0 20px">
  Port <code>{port}</code> &nbsp;&middot;&nbsp; Receiver <code>{receiver_id}</code> &nbsp;&middot;&nbsp; Paired: <code>{paired_count}</code>
</p>

<div class="grid">

<section class="dex-card">
<h2>Pair Android</h2>
<p class="muted" style="font-size:12px;margin:0 0 10px">Scan from DexTilt Android app. Tokens are one-time.</p>
<div id="pairing">Loading QR&#8230;</div>
<p class="muted" style="font-size:11px;margin:8px 0 0">Local: <code>http://127.0.0.1:{port}/status</code></p>
</section>

<section class="dex-card">
<h2>Phone Control</h2>
<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">
  <button class="btn-primary" onclick="queuePhoneControl('start_training')">Start Training</button>
  <button class="btn-primary" onclick="queuePhoneControl('arm')">Arm</button>
  <button class="btn-primary" onclick="queuePhoneControl('disarm')">Disarm</button>
  <button class="btn-primary" onclick="queuePhoneControl('cancel')">Cancel</button>
</div>
<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px">
  <button class="btn-secondary" onclick="queuePhoneControl('start_local_test')">Local Test</button>
  <button class="btn-secondary" onclick="queuePhoneControl('start_sensor_preview')">Start Sensor Preview</button>
  <button class="btn-secondary" onclick="queuePhoneControl('stop_sensor_preview')">Stop Sensor Preview</button>
</div>
<div class="danger-zone">
  <span style="font-size:10px;color:var(--red);font-family:'Orbitron',monospace">Destructive:</span>
  <button class="btn-danger" onclick="clearQueueConfirm()">Clear Queue</button>
  <button class="btn-danger" onclick="resetPairingConfirm()">Reset Pairing</button>
</div>
<div id="phoneControlResult" style="font-size:11px;font-family:'Space Mono',monospace;margin-top:8px;color:var(--text-lo)"></div>
</section>

<section class="dex-card" id="queue-card">
<h2>Queue</h2>
<div id="queue-empty" style="color:var(--green);font-size:12px;font-family:'Space Mono',monospace">Queue empty</div>
<div id="queue-item" style="display:none">
  <div class="sensor-grid">
    <span class="sg-label">Action</span><span id="q-action" class="sensor-value">&#8212;</span>
    <span class="sg-label">Target</span><span id="q-device" style="font-size:11px;color:var(--text-lo)">&#8212;</span>
    <span class="sg-label">Created</span><span id="q-created" style="font-size:11px;color:var(--text-lo)">&#8212;</span>
    <span class="sg-label">Expires</span><span id="q-expires" class="sensor-value">&#8212;</span>
  </div>
  <div class="queue-bar"><div id="q-bar-fill" class="queue-bar-fill" style="width:100%"></div></div>
  <button class="btn-danger" style="margin-top:6px" onclick="clearQueueConfirm()">Clear Queue</button>
</div>
</section>

<section class="dex-card">
<h2><span id="live-status-dot" class="status-dot" style="margin-right:6px"></span>Live Phone Orientation</h2>
<div id="live-phone-canvas" style="width:100%;height:220px;border-radius:6px;overflow:hidden;background:#0a0f1e"></div>
<div id="live-no-data" style="text-align:center;padding:16px;color:var(--text-lo);font-size:12px;font-family:'Space Mono',monospace">
  No live phone data yet.<br>Open DexTilt on Android and start sensor preview, training, or arming.
</div>
<div id="live-data" style="display:none">
  <div id="threejs-live-err" style="display:none;color:var(--amber);font-size:11px;padding:6px 0">3D unavailable &#8212; Three.js CDN failed.</div>
  <div class="sensor-grid" style="margin-top:10px">
    <span class="sg-label">Phase</span><span id="lv-phase" class="sensor-value">&#8212;</span>
    <span class="sg-label">Face-down</span><span id="lv-face" class="sensor-value">&#8212;</span>
    <span class="sg-label">Accel</span><span><span id="lv-ax" class="sensor-value">&#8212;</span> / <span id="lv-ay" class="sensor-value">&#8212;</span> / <span id="lv-az" class="sensor-value">&#8212;</span></span>
    <span class="sg-label">Gyro</span><span><span id="lv-gx" class="sensor-value">&#8212;</span> / <span id="lv-gy" class="sensor-value">&#8212;</span> / <span id="lv-gz" class="sensor-value">&#8212;</span></span>
    <span class="sg-label">Roll/Pitch/Yaw</span><span><span id="lv-roll" class="sensor-value">&#8212;</span>&#176; / <span id="lv-pitch" class="sensor-value">&#8212;</span>&#176; / <span id="lv-yaw" class="sensor-value">&#8212;</span>&#176;</span>
    <span class="sg-label">Quaternion</span><span id="lv-quat" class="sensor-value" style="font-size:10px">&#8212;</span>
    <span class="sg-label">Source</span><span id="lv-src" class="sensor-value">&#8212;</span>
    <span class="sg-label">Updated</span><span id="lv-age" class="sensor-value">&#8212;</span>
  </div>
</div>
</section>

<section class="dex-card">
<h2>Gesture Preview</h2>
<div id="gesture-preview-canvas" style="width:100%;height:220px;border-radius:6px;overflow:hidden;background:#0a0f1e"></div>
<div id="gp-no-data" style="text-align:center;padding:16px;color:var(--text-lo);font-size:12px;font-family:'Space Mono',monospace">
  No gesture preview yet. Train a gesture first.
</div>
<div id="gp-data" style="display:none">
  <div class="sensor-grid" style="margin:10px 0">
    <span class="sg-label">Gesture</span><span id="gp-name" class="sensor-value">&#8212;</span>
    <span class="sg-label">Duration</span><span id="gp-dur" class="sensor-value">&#8212;</span>
    <span class="sg-label">Samples</span><span id="gp-pts" class="sensor-value">&#8212;</span>
    <span class="sg-label">Confidence</span><span id="gp-conf" class="sensor-value">&#8212;</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
    <button class="btn-secondary" onclick="playGesture()">Play</button>
    <button class="btn-secondary" onclick="pauseGesture()">Pause</button>
    <button class="btn-secondary" onclick="restartGesture()">Restart</button>
    <input id="gp-slider" type="range" min="0" max="100" value="0"
           oninput="gestureFrameIdx=parseInt(this.value);updateGestureFrame(gestureFrameIdx)"
           style="flex:1;accent-color:var(--accent);margin:0;width:auto;">
  </div>
</div>
</section>

<section class="dex-card">
<h2>Paired Devices</h2>
<table><thead><tr><th>Name</th><th>Device ID</th><th>Last IP</th></tr></thead><tbody>{device_rows}</tbody></table>
</section>

<section class="dex-card">
<h2>Notification Settings</h2>
<div class="formgrid">
<label>Training<select id="setting_training"><option value="true">on</option><option value="false">off</option></select></label>
<label>Runtime<select id="setting_runtime"><option value="true">on</option><option value="false">off</option></select></label>
<label>Local test<select id="setting_localtest"><option value="true">on</option><option value="false">off</option></select></label>
<label>Command result<select id="setting_command"><option value="true">on</option><option value="false">off</option></select></label>
<label>Face-down stable<select id="setting_stable"><option value="training_only">training only</option><option value="always">always</option><option value="off">off</option></select></label>
</div>
<button onclick="saveSettings()" style="margin-top:8px">Save</button>
<pre id="settingsResult" style="margin-top:8px">Settings not loaded.</pre>
</section>

<section class="dex-card">
<h2>Calibration</h2>
<pre>{last_calibration_text}</pre>
</section>

<section class="dex-card">
<h2>Last Command / Event</h2>
<pre>{last_command_text}</pre>
<p style="font-size:12px;margin:8px 0 0">Last error: <span class="bad">{last_error_text}</span></p>
</section>

<section class="dex-card wide">
<h2>Command Registry</h2>
<p class="muted" style="font-size:12px;margin:0 0 10px">The Mac owns all actions. The phone sends command IDs only.</p>
<table><thead><tr><th>Command ID</th><th>Label</th><th>Type</th><th>Target</th><th>Enabled</th><th>Actions</th></tr></thead><tbody>{command_rows}</tbody></table>
</section>

<section class="dex-card wide">
<h2>Add / Edit Command</h2>
<div class="formgrid">
<label>Command ID<input id="cmd_id" placeholder="snake_case_id"></label>
<label>Label<input id="cmd_label" placeholder="Human label"></label>
<label>Type<select id="cmd_type"><option>open_url</option><option>open_app</option><option>notification</option><option>key_press</option><option>hid_middle_click</option></select></label>
<label>Target / URL / App / Key<input id="cmd_target" placeholder="https://... or AppName or enter"></label>
<label>Notification title<input id="cmd_title" placeholder="DexTilt"></label>
<label>Notification message<input id="cmd_message" placeholder="Message"></label>
<label>Success message<input id="cmd_success" placeholder="Action triggered"></label>
<label>Enabled<select id="cmd_enabled"><option value="true">yes</option><option value="false">no</option></select></label>
</div>
<label>Description<textarea id="cmd_description" rows="2"></textarea></label>
<button onclick="saveCommand()" style="margin-top:6px">Save command</button>
<button class="secondary" onclick="clearCommandForm()">Clear</button>
<pre id="commandResult" style="margin-top:8px">No command edit yet.</pre>
</section>

<section class="dex-card wide">
<details open>
  <summary>Recent Logs</summary>
  <div style="padding:6px 0">
    <button class="log-filter-btn active" onclick="setLogFilter(event,'all')">All</button>
    <button class="log-filter-btn" onclick="setLogFilter(event,'command')">Commands</button>
    <button class="log-filter-btn" onclick="setLogFilter(event,'error')">Errors</button>
    <button class="log-filter-btn" onclick="setLogFilter(event,'phone_control')">Phone Control</button>
    <button class="log-filter-btn" onclick="setLogFilter(event,'gesture')">Gesture</button>
  </div>
  <div id="logs-container" style="font-size:11px;font-family:'Space Mono',monospace;max-height:300px;overflow-y:auto;padding:4px 0;color:var(--text-lo)"></div>
</details>
</section>

</div>
</main>

<script>
var commandMap = {json.dumps(command_map, sort_keys=True)};

async function api(path, payload) {{
  var opts = payload === undefined ? {{}} : {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }};
  var res = await fetch(path, opts);
  var data = await res.json();
  if (!res.ok) throw new Error(data.user_message || data.detail || JSON.stringify(data));
  return data;
}}

function safeNumber(v, fallback, min, max) {{
  var n = parseFloat(v);
  if (!isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, n));
}}

function setVal(id, text) {{
  var el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.classList.remove('flash');
  void el.offsetWidth;
  el.classList.add('flash');
}}

function createScene(containerId) {{
  if (typeof THREE === 'undefined') return null;
  var el = document.getElementById(containerId);
  if (!el) return null;
  var W = el.clientWidth || 340, H = 220;
  var renderer = new THREE.WebGLRenderer({{ antialias: true }});
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(W, H);
  renderer.setClearColor(0x0a0f1e, 1);
  el.appendChild(renderer.domElement);
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
  camera.position.set(0, 1.5, 5);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.GridHelper(10, 20, 0x0d4060, 0x102040));
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  var dir = new THREE.DirectionalLight(0xffffff, 1.5);
  dir.position.set(2, 4, 3);
  scene.add(dir);
  return {{ renderer: renderer, camera: camera, scene: scene }};
}}

function createPhoneModel() {{
  var group = new THREE.Group();
  // Body — MeshBasicMaterial so it stays bright red regardless of scene lighting
  group.add(new THREE.Mesh(
    new THREE.BoxGeometry(1.5, 2.7, 0.16),
    new THREE.MeshBasicMaterial({{ color: 0xff1744 }})
  ));
  // Edge outline — makes the slab pop against the dark background
  group.add(new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(1.5, 2.7, 0.16)),
    new THREE.LineBasicMaterial({{ color: 0xff6688 }})
  ));
  // Screen face — electric cyan, always bright, slightly in front of body face
  var screen = new THREE.Mesh(
    new THREE.PlaneGeometry(1.32, 2.44),
    new THREE.MeshBasicMaterial({{ color: 0x00e5ff, side: THREE.FrontSide }})
  );
  screen.position.set(0, 0, 0.082);
  group.add(screen);
  // Top notch — dark pill so screen top/bottom orientation is obvious
  var notch = new THREE.Mesh(
    new THREE.BoxGeometry(0.22, 0.07, 0.01),
    new THREE.MeshBasicMaterial({{ color: 0x0a0f1e }})
  );
  notch.position.set(0, 1.06, 0.085);
  group.add(notch);
  return group;
}}

function setPhoneTransform(phoneGroup, state) {{
  if (!state || !phoneGroup) return;
  var qw = safeNumber(state.qw, 1, -1, 1);
  var qx = safeNumber(state.qx, 0, -1, 1);
  var qy = safeNumber(state.qy, 0, -1, 1);
  var qz = safeNumber(state.qz, 0, -1, 1);
  var mag = Math.sqrt(qw*qw + qx*qx + qy*qy + qz*qz);
  if (mag > 0.1) {{
    phoneGroup.quaternion.set(qx, qy, qz, qw).normalize();
  }} else {{
    phoneGroup.rotation.set(
      safeNumber(state.roll, 0, -12.57, 12.57),
      safeNumber(state.yaw,  0, -12.57, 12.57),
      safeNumber(state.pitch,0, -12.57, 12.57)
    );
  }}
  if (state.x !== undefined) {{
    phoneGroup.position.set(
      safeNumber(state.x, 0, -5, 5),
      safeNumber(state.y, 0, -5, 5),
      safeNumber(state.z, 0, -5, 5)
    );
  }}
}}

// Live phone orientation
var liveSceneObj = null, livePhone = null;

function initLivePhoneScene() {{
  if (typeof THREE === 'undefined') {{
    var err = document.getElementById('threejs-live-err');
    if (err) err.style.display = 'block';
    return;
  }}
  liveSceneObj = createScene('live-phone-canvas');
  if (!liveSceneObj) return;
  livePhone = createPhoneModel();
  liveSceneObj.scene.add(livePhone);
  (function animate() {{
    requestAnimationFrame(animate);
    liveSceneObj.renderer.render(liveSceneObj.scene, liveSceneObj.camera);
  }})();
}}

function updateLivePhoneState() {{
  fetch('/phone-state').then(function(r) {{ return r.json(); }}).then(function(d) {{
    var state = d.state;
    var noData = document.getElementById('live-no-data');
    var liveData = document.getElementById('live-data');
    if (!state) {{
      if (noData) noData.style.display = 'block';
      if (liveData) liveData.style.display = 'none';
      return;
    }}
    if (noData) noData.style.display = 'none';
    if (liveData) liveData.style.display = 'block';
    setPhoneTransform(livePhone, state);
    var ageMs = Date.now() - safeNumber(state.timestamp_ms, Date.now(), 0, 9e15);
    var dotEl = document.getElementById('live-status-dot');
    if (dotEl) dotEl.className = 'status-dot' + (ageMs < 700 ? ' live' : '');
    setVal('lv-phase', state.phase || '—');
    setVal('lv-face', state.face_down_stable ? 'YES' : 'NO');
    setVal('lv-ax', safeNumber(state.ax,0,-50,50).toFixed(3));
    setVal('lv-ay', safeNumber(state.ay,0,-50,50).toFixed(3));
    setVal('lv-az', safeNumber(state.az,0,-50,50).toFixed(3));
    setVal('lv-gx', safeNumber(state.gx,0,-50,50).toFixed(3));
    setVal('lv-gy', safeNumber(state.gy,0,-50,50).toFixed(3));
    setVal('lv-gz', safeNumber(state.gz,0,-50,50).toFixed(3));
    setVal('lv-roll',  (safeNumber(state.roll, 0,-12.57,12.57)*57.296).toFixed(1));
    setVal('lv-pitch', (safeNumber(state.pitch,0,-12.57,12.57)*57.296).toFixed(1));
    setVal('lv-yaw',   (safeNumber(state.yaw,  0,-12.57,12.57)*57.296).toFixed(1));
    setVal('lv-quat', [state.qw,state.qx,state.qy,state.qz]
      .map(function(v) {{ return safeNumber(v,0,-1,1).toFixed(3); }}).join(' '));
    setVal('lv-src', state.orientation_source || '—');
    setVal('lv-age', ageMs < 2000 ? ageMs+'ms ago' : (ageMs/1000).toFixed(1)+'s ago');
    var stripPhase = document.getElementById('strip-phase');
    if (stripPhase) stripPhase.textContent = state.phase || '—';
    var stripLive = document.getElementById('strip-live-wrap');
    if (stripLive) stripLive.style.display = ageMs < 700 ? 'flex' : 'none';
  }}).catch(function() {{}});
}}

// Gesture preview
var gestureSceneObj = null, gesturePhone = null, gestureLine = null;
var gesturePoints = [], gesturePlaying = false, gestureFrameIdx = 0, lastGestureId = null;

function initGesturePreviewScene(preview) {{
  if (typeof THREE === 'undefined') return;
  if (!gestureSceneObj) {{
    gestureSceneObj = createScene('gesture-preview-canvas');
    if (!gestureSceneObj) return;
    gesturePhone = createPhoneModel();
    gestureSceneObj.scene.add(gesturePhone);
    (function animate() {{
      requestAnimationFrame(animate);
      if (gesturePlaying && gesturePoints.length) advanceGestureFrame();
      gestureSceneObj.renderer.render(gestureSceneObj.scene, gestureSceneObj.camera);
    }})();
  }}
  if (!preview || !Array.isArray(preview.points) || !preview.points.length) return;
  if (gestureLine) {{
    gestureSceneObj.scene.remove(gestureLine);
    gestureLine.geometry.dispose();
    gestureLine.material.dispose();
    gestureLine = null;
  }}
  gesturePoints = preview.points;
  try {{
    var vecs = gesturePoints.map(function(p) {{
      return new THREE.Vector3(safeNumber(p.x,0,-5,5), safeNumber(p.y,0,-5,5), safeNumber(p.z,0,-5,5));
    }});
    var geo = new THREE.BufferGeometry().setFromPoints(vecs);
    var mat = new THREE.LineBasicMaterial({{ color: 0x00e5ff, opacity: 0.4, transparent: true }});
    gestureLine = new THREE.Line(geo, mat);
    gestureSceneObj.scene.add(gestureLine);
  }} catch(e) {{ gesturePoints = []; return; }}
  setVal('gp-name', preview.name || preview.gesture_id || '—');
  setVal('gp-dur', preview.duration_ms ? (preview.duration_ms/1000).toFixed(2)+'s' : '—');
  setVal('gp-pts', String(gesturePoints.length));
  setVal('gp-conf', preview.confidence != null ? preview.confidence+'%' : '—');
  var slider = document.getElementById('gp-slider');
  if (slider) slider.max = Math.max(0, gesturePoints.length - 1);
  var noData = document.getElementById('gp-no-data');
  var gpData = document.getElementById('gp-data');
  if (noData) noData.style.display = 'none';
  if (gpData) gpData.style.display = 'block';
  gestureFrameIdx = 0; gesturePlaying = false;
  updateGestureFrame(0);
}}

function advanceGestureFrame() {{
  if (!gesturePoints.length) return;
  // Wrap back to frame 0 after the last frame — continuous loop while Play is active
  gestureFrameIdx = (gestureFrameIdx + 1) % gesturePoints.length;
  var slider = document.getElementById('gp-slider');
  if (slider) slider.value = gestureFrameIdx;
  updateGestureFrame(gestureFrameIdx);
}}

function updateGestureFrame(index) {{
  if (!gesturePoints.length) return;
  setPhoneTransform(gesturePhone, gesturePoints[Math.max(0, Math.min(index, gesturePoints.length-1))]);
}}

function playGesture()  {{ gesturePlaying = true; }}
function pauseGesture() {{ gesturePlaying = false; }}
function restartGesture() {{
  gestureFrameIdx = 0;
  gesturePlaying = true;
  var slider = document.getElementById('gp-slider');
  if (slider) slider.value = 0;
  updateGestureFrame(0);
}}

function checkGesturePreview() {{
  fetch('/gesture-preview').then(function(r) {{ return r.json(); }}).then(function(d) {{
    if (d.preview && d.preview.gesture_id !== lastGestureId) {{
      lastGestureId = d.preview.gesture_id;
      initGesturePreviewScene(d.preview);
    }} else if (!d.preview) {{
      var noData = document.getElementById('gp-no-data');
      var gpData = document.getElementById('gp-data');
      if (noData) noData.style.display = 'block';
      if (gpData) gpData.style.display = 'none';
    }}
  }}).catch(function() {{}});
}}

// Queue panel
function renderQueuePanel(queue) {{
  var empty = document.getElementById('queue-empty');
  var item  = document.getElementById('queue-item');
  var sq    = document.getElementById('strip-queue');
  if (!queue || !queue.length) {{
    if (empty) empty.style.display = 'block';
    if (item)  item.style.display  = 'none';
    if (sq)    sq.textContent = 'empty';
    return;
  }}
  var q = queue[0];
  if (empty) empty.style.display = 'none';
  if (item)  item.style.display  = 'block';
  setVal('q-action', q.action || '—');
  setVal('q-device', q.target_device_id || 'any');
  var createdEl = document.getElementById('q-created');
  if (createdEl && q.created_at_ms) createdEl.textContent = new Date(q.created_at_ms).toLocaleTimeString();
  var ttl       = q.ttl_ms || 30000;
  var elapsed   = Date.now() - (q.created_at_ms || Date.now());
  var remaining = Math.max(0, ttl - elapsed);
  setVal('q-expires', (remaining/1000).toFixed(0)+'s');
  var fill = document.getElementById('q-bar-fill');
  if (fill) fill.style.width = Math.round((remaining/ttl)*100)+'%';
  if (sq)   sq.textContent = (q.action||'—')+' ('+(remaining/1000).toFixed(0)+'s)';
}}

function clearQueueConfirm() {{
  if (!confirm('Clear the phone control queue?')) return;
  api('/phone-control/queue', {{ action: 'clear' }}).then(function() {{
    refreshQueue();
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = 'Queue cleared.';
  }}).catch(function(err) {{
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = err.message;
  }});
}}

function resetPairingConfirm() {{
  if (!confirm('Reset all pairings? The phone will need to re-pair.')) return;
  api('/api/reset-pairing', {{}}).then(function(d) {{
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = d.user_message || 'Pairings reset.';
    refreshSystemStrip();
  }}).catch(function(err) {{
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = err.message;
  }});
}}

// System strip + targeted refreshes
function refreshSystemStrip() {{
  fetch('/api/status').then(function(r) {{ return r.json(); }}).then(function(d) {{
    var devices = d.paired_devices || [];
    var dot     = document.getElementById('strip-phone-dot');
    var phoneEl = document.getElementById('strip-phone');
    if (devices.length) {{
      if (dot)     dot.className     = 'status-dot live';
      if (phoneEl) phoneEl.textContent = devices[0].device_id || 'Connected';
    }} else {{
      if (dot)     dot.className     = 'status-dot red';
      if (phoneEl) phoneEl.textContent = 'Not connected';
    }}
    if (d.last_command) {{
      var lc   = d.last_command;
      var lcEl = document.getElementById('strip-last-cmd');
      if (lcEl) lcEl.textContent = (lc.command_id||lc.event_id||'—') + (lc.confidence ? ' ('+lc.confidence+'%)' : '');
    }}
  }}).catch(function() {{}});
}}

function refreshQueue() {{
  fetch('/api/queue-status').then(function(r) {{ return r.json(); }}).then(function(d) {{
    renderQueuePanel(d.queue || []);
  }}).catch(function() {{}});
}}

function refreshLogs() {{
  fetch('/logs').then(function(r) {{ return r.json(); }}).then(function(d) {{
    var el = document.getElementById('logs-container');
    if (!el) return;
    while (el.firstChild) el.removeChild(el.firstChild);
    (d.events || []).forEach(function(ev) {{
      var line  = document.createElement('div');
      var evStr = typeof ev === 'string' ? ev : JSON.stringify(ev);
      line.textContent = evStr.substring(0, 200);
      line.title = evStr;
      var evType = typeof ev === 'object' ? (ev.event || '') : evStr;
      if      (evType.indexOf('command')      >= 0) line.dataset.ltype = 'command';
      else if (evType.indexOf('error')        >= 0 || evType.indexOf('rejected') >= 0) line.dataset.ltype = 'error';
      else if (evType.indexOf('phone_control')>= 0 || evType.indexOf('queue')    >= 0) line.dataset.ltype = 'phone_control';
      else if (evType.indexOf('gesture')      >= 0 || evType.indexOf('training') >= 0) line.dataset.ltype = 'gesture';
      else line.dataset.ltype = 'other';
      applyLogFilter(line);
      el.appendChild(line);
    }});
  }}).catch(function() {{}});
}}

var currentLogFilter = 'all';
function setLogFilter(evt, filter) {{
  currentLogFilter = filter;
  document.querySelectorAll('.log-filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  if (evt && evt.target) evt.target.classList.add('active');
  document.querySelectorAll('#logs-container div').forEach(applyLogFilter);
}}
function applyLogFilter(line) {{
  line.style.display = (currentLogFilter === 'all' || line.dataset.ltype === currentLogFilter) ? '' : 'none';
}}

// Pairing, Settings, Commands
async function loadPairing() {{
  var el = document.getElementById('pairing');
  try {{
    var data = await api('/pairing');
    while (el.firstChild) el.removeChild(el.firstChild);
    var img = document.createElement('img');
    img.className = 'qr';
    img.alt = 'DexTilt pairing QR';
    img.src = data.qr_data_url;
    el.appendChild(img);
    var pre = document.createElement('pre');
    pre.textContent = JSON.stringify(data.payload, null, 2);
    el.appendChild(pre);
  }} catch (err) {{
    while (el.firstChild) el.removeChild(el.firstChild);
    var p = document.createElement('p');
    p.className = 'bad';
    p.textContent = err.message;
    el.appendChild(p);
  }}
}}

async function loadSettings() {{
  try {{
    var data = await api('/settings');
    var s = data.settings || {{}};
    document.getElementById('setting_training').value = String(s.training_notifications !== false);
    document.getElementById('setting_runtime').value  = String(s.runtime_notifications  !== false);
    document.getElementById('setting_localtest').value= String(s.local_test_notifications!== false);
    document.getElementById('setting_command').value  = String(s.command_result_notifications !== false);
    document.getElementById('setting_stable').value   = String(s.face_down_stable || 'training_only');
    document.getElementById('settingsResult').textContent = JSON.stringify(s, null, 2);
  }} catch (err) {{
    document.getElementById('settingsResult').textContent = err.message;
  }}
}}

async function saveSettings() {{
  try {{
    var payload = {{
      training_notifications:         document.getElementById('setting_training').value === 'true',
      runtime_notifications:          document.getElementById('setting_runtime').value  === 'true',
      local_test_notifications:       document.getElementById('setting_localtest').value=== 'true',
      command_result_notifications:   document.getElementById('setting_command').value  === 'true',
      face_down_stable:               document.getElementById('setting_stable').value
    }};
    var data = await api('/settings', payload);
    document.getElementById('settingsResult').textContent = JSON.stringify(data.settings, null, 2);
  }} catch (err) {{
    document.getElementById('settingsResult').textContent = err.message;
  }}
}}

function fillCommand(id) {{
  var a = commandMap[id] || {{}};
  document.getElementById('cmd_id').value          = id;
  document.getElementById('cmd_label').value       = a.label || id;
  document.getElementById('cmd_type').value        = a.type  || 'open_url';
  document.getElementById('cmd_target').value      = a.url || a.app || a.key || a.target || '';
  document.getElementById('cmd_title').value       = a.title   || 'DexTilt';
  document.getElementById('cmd_message').value     = a.message || '';
  document.getElementById('cmd_success').value     = a.success_message || '';
  document.getElementById('cmd_enabled').value     = String(a.enabled !== false);
  document.getElementById('cmd_description').value = a.description || '';
  window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
}}

function clearCommandForm() {{
  ['cmd_id','cmd_label','cmd_target','cmd_title','cmd_message','cmd_success','cmd_description']
    .forEach(function(id) {{ document.getElementById(id).value = ''; }});
  document.getElementById('cmd_type').value    = 'open_url';
  document.getElementById('cmd_enabled').value = 'true';
}}

async function saveCommand() {{
  try {{
    var payload = {{
      command_id:      document.getElementById('cmd_id').value,
      label:           document.getElementById('cmd_label').value,
      type:            document.getElementById('cmd_type').value,
      target:          document.getElementById('cmd_target').value,
      title:           document.getElementById('cmd_title').value,
      message:         document.getElementById('cmd_message').value,
      success_message: document.getElementById('cmd_success').value,
      enabled:         document.getElementById('cmd_enabled').value === 'true',
      description:     document.getElementById('cmd_description').value
    }};
    var data = await api('/api/commands/upsert', payload);
    document.getElementById('commandResult').textContent = JSON.stringify(data, null, 2);
    setTimeout(function() {{ location.reload(); }}, 700);
  }} catch (err) {{
    document.getElementById('commandResult').textContent = err.message;
  }}
}}

async function deleteCommand(id) {{
  if (!confirm('Delete command ' + id + '?')) return;
  try {{
    var data = await api('/api/commands/delete', {{ command_id: id }});
    document.getElementById('commandResult').textContent = JSON.stringify(data, null, 2);
    setTimeout(function() {{ location.reload(); }}, 700);
  }} catch (err) {{
    document.getElementById('commandResult').textContent = err.message;
  }}
}}

async function testCommand(id) {{
  try {{
    var data = await api('/api/commands/test', {{ command_id: id }});
    document.getElementById('commandResult').textContent = JSON.stringify(data, null, 2);
  }} catch (err) {{
    document.getElementById('commandResult').textContent = err.message;
  }}
}}

async function queuePhoneControl(action) {{
  try {{
    var data = await api('/phone-control/queue', {{ action: action }});
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = JSON.stringify(data, null, 2);
    refreshQueue();
  }} catch (err) {{
    var el = document.getElementById('phoneControlResult');
    if (el) el.textContent = err.message;
  }}
}}

// ── Display themes ────────────────────────────────────────────
var THEMES = {{
  cockpit: {{
    name: 'Cockpit', accent: '#00e5ff', bg: '#070d1a',
    vars: {{'--bg':'#070d1a','--panel-bg':'rgba(8,20,45,.95)','--border':'rgba(0,200,230,.18)',
            '--accent':'#00e5ff','--accent-dim':'rgba(0,229,255,.35)','--amber':'#ff9100',
            '--green':'#00e676','--red':'#ff1744','--text-hi':'#e8f4f8','--text-lo':'rgba(160,200,220,.6)'}}
  }},
  terminal: {{
    name: 'Terminal', accent: '#00ff41', bg: '#080d08',
    vars: {{'--bg':'#080d08','--panel-bg':'rgba(4,12,4,.97)','--border':'rgba(0,220,60,.18)',
            '--accent':'#00ff41','--accent-dim':'rgba(0,255,65,.25)','--amber':'#ffee00',
            '--green':'#00ff41','--red':'#ff3333','--text-hi':'#d0ffd0','--text-lo':'rgba(80,180,80,.7)'}}
  }},
  ember: {{
    name: 'Ember', accent: '#ff7400', bg: '#100800',
    vars: {{'--bg':'#100800','--panel-bg':'rgba(22,10,0,.97)','--border':'rgba(255,110,0,.2)',
            '--accent':'#ff7400','--accent-dim':'rgba(255,116,0,.3)','--amber':'#ffcc00',
            '--green':'#aaff00','--red':'#ff2020','--text-hi':'#fff5e0','--text-lo':'rgba(220,160,80,.65)'}}
  }},
  arctic: {{
    name: 'Arctic', accent: '#7dd3fc', bg: '#0a1120',
    vars: {{'--bg':'#0a1120','--panel-bg':'rgba(10,20,38,.97)','--border':'rgba(130,200,255,.2)',
            '--accent':'#7dd3fc','--accent-dim':'rgba(125,211,252,.25)','--amber':'#fbbf24',
            '--green':'#4ade80','--red':'#f87171','--text-hi':'#f0f9ff','--text-lo':'rgba(148,163,184,.75)'}}
  }}
}};

function applyTheme(id) {{
  var theme = THEMES[id];
  if (!theme) return;
  var root = document.documentElement;
  Object.keys(theme.vars).forEach(function(k) {{ root.style.setProperty(k, theme.vars[k]); }});
  root.setAttribute('data-theme', id);
  localStorage.setItem('dextilt_theme', id);
  document.querySelectorAll('.theme-swatch').forEach(function(s) {{
    s.classList.toggle('active', s.dataset.theme === id);
    s.style.borderColor = s.dataset.theme === id ? theme.vars['--accent'] : 'rgba(255,255,255,.1)';
  }});
}}

function setFontSize(size) {{
  document.documentElement.setAttribute('data-font-size', size);
  localStorage.setItem('dextilt_font_size', size);
  ['compact','normal','comfortable','large'].forEach(function(s) {{
    var btn = document.getElementById('fs-btn-'+s);
    if (btn) btn.classList.toggle('active', s === size);
  }});
}}

function toggleThemePanel() {{
  var panel = document.getElementById('theme-panel');
  if (panel) panel.classList.toggle('open');
}}

function buildThemeSwatches() {{
  var container = document.getElementById('theme-swatches');
  if (!container) return;
  Object.keys(THEMES).forEach(function(id) {{
    var t = THEMES[id];
    var btn = document.createElement('button');
    btn.className = 'theme-swatch';
    btn.dataset.theme = id;
    btn.onclick = function() {{ applyTheme(id); }};
    btn.style.background = t.bg;
    var name = document.createElement('div');
    name.className = 'theme-swatch-name';
    name.style.color = t.accent;
    name.textContent = t.name;
    var dots = document.createElement('div');
    dots.className = 'theme-swatch-dots';
    [t.accent, t.vars['--amber'], t.vars['--green'], t.vars['--red']].forEach(function(c) {{
      var dot = document.createElement('div');
      dot.className = 'theme-swatch-dot';
      dot.style.background = c;
      dots.appendChild(dot);
    }});
    btn.appendChild(name);
    btn.appendChild(dots);
    container.appendChild(btn);
  }});
}}

window.addEventListener('DOMContentLoaded', function() {{
  // Restore display preferences from localStorage
  buildThemeSwatches();
  applyTheme(localStorage.getItem('dextilt_theme') || 'cockpit');
  setFontSize(localStorage.getItem('dextilt_font_size') || 'normal');

  initLivePhoneScene();
  initGesturePreviewScene(null);
  checkGesturePreview();
  loadPairing();
  loadSettings();
  refreshSystemStrip();
  refreshLogs();
  refreshQueue();
  setInterval(updateLivePhoneState,  250);
  setInterval(checkGesturePreview,  2000);
  setInterval(refreshSystemStrip,   4000);
  setInterval(refreshLogs,          8000);
  setInterval(refreshQueue,         2000);
}});
</script>
</body>
</html>"""
