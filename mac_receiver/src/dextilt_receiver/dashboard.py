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


def render_dashboard(status: dict[str, Any], commands: list[str], log_events: list[dict[str, Any]]) -> str:
    last_command = status.get("last_command")
    last_error = status.get("last_error")
    last_calibration = status.get("last_calibration")
    device_rows = "".join(
        f"<tr><td>{escape(str(d.get('device_name') or 'Android DexTilt'))}</td><td><code>{escape(str(d.get('device_id')))}</code></td><td>{escape(str(d.get('last_source_ip') or '-'))}</td></tr>"
        for d in status.get("paired_devices", [])
    ) or "<tr><td colspan='3'>No paired Android device yet.</td></tr>"
    command_items = "".join(f"<li><code>{escape(cmd)}</code></li>" for cmd in commands)
    logs = "\n".join(escape(json.dumps(event, sort_keys=True)) for event in log_events[-12:]) or "No logs yet."
    last_command_text = escape(json.dumps(last_command, indent=2, sort_keys=True)) if last_command else "None"
    last_calibration_text = escape(json.dumps(last_calibration, indent=2, sort_keys=True)) if last_calibration else "None"
    last_error_text = escape(str(last_error or "None"))
    receiver_id = escape(str(status.get("receiver_id")))
    port = escape(str(status.get("port")))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DexTilt Mac Receiver</title>
<style>
:root {{ color-scheme: dark; --bg:#0b0d10; --panel:#151922; --panel2:#10131a; --text:#edf2ff; --muted:#94a3b8; --ok:#8ee99a; --warn:#ffd166; --bad:#ff6b6b; --line:#293042; }}
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:radial-gradient(circle at top left,#172033,#0b0d10 42%); color:var(--text); }}
main {{ max-width:1100px; margin:0 auto; padding:28px; }}
h1 {{ margin:0 0 8px; font-size:34px; letter-spacing:-0.04em; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px; }}
.card {{ background:linear-gradient(180deg,var(--panel),var(--panel2)); border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 18px 60px rgba(0,0,0,.28); }}
.status-dot {{ display:inline-block; width:12px; height:12px; border-radius:999px; background:var(--ok); box-shadow:0 0 16px var(--ok); margin-right:8px; }}
.muted {{ color:var(--muted); }}
code, pre {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#07090d; border:1px solid var(--line); border-radius:12px; padding:12px; color:#d7e3ff; }}
button {{ background:#d7e3ff; color:#111827; border:0; border-radius:12px; padding:10px 14px; font-weight:700; cursor:pointer; }}
img.qr {{ background:#fff; border-radius:12px; padding:12px; max-width:260px; }}
table {{ width:100%; border-collapse:collapse; }}
td, th {{ border-bottom:1px solid var(--line); padding:8px; text-align:left; }}
.warn {{ color:var(--warn); }}
.bad {{ color:var(--bad); }}
</style>
</head>
<body>
<main>
<h1>DexTilt Mac Receiver</h1>
<p><span class="status-dot"></span>Running on port <code>{port}</code>. Receiver ID <code>{receiver_id}</code>.</p>
<div class="grid">
<section class="card">
<h2>Pair Android</h2>
<p class="muted">Scan this QR from the DexTilt Android app. Pairing tokens are one-time and expire.</p>
<div id="pairing">Loading local QR...</div>
<p class="muted">For security, the QR token endpoint only serves local Mac requests. Open this dashboard on the Mac at <code>http://127.0.0.1:{port}/status</code>.</p>
</section>
<section class="card">
<h2>Paired devices</h2>
<table><thead><tr><th>Name</th><th>Device ID</th><th>Last IP</th></tr></thead><tbody>{device_rows}</tbody></table>
</section>
<section class="card">
<h2>Commands</h2>
<ul>{command_items}</ul>
<p class="muted">Phone sends command IDs only. The Mac runs allowlisted local actions.</p>
</section>
<section class="card">
<h2>Calibration</h2>
<p class="muted">Android calibration progress appears here after pairing.</p>
<pre>{last_calibration_text}</pre>
</section>
<section class="card">
<h2>Last command</h2>
<pre>{last_command_text}</pre>
<p>Last error: <span class="bad">{last_error_text}</span></p>
</section>
<section class="card">
<h2>Recent logs</h2>
<pre>{logs}</pre>
</section>
</div>
</main>
<script>
async function loadPairing() {{
  const el = document.getElementById('pairing');
  try {{
    const res = await fetch('/pairing');
    const data = await res.json();
    if (!res.ok) throw new Error(data.user_message || data.detail || 'Pairing QR failed');
    el.innerHTML = `<img class="qr" alt="DexTilt pairing QR" src="${{data.qr_data_url}}"><pre>${{JSON.stringify(data.payload, null, 2)}}</pre>`;
  }} catch (err) {{
    el.innerHTML = `<p class="bad">${{err.message}}</p>`;
  }}
}}
loadPairing();
setInterval(() => location.reload(), 15000);
</script>
</body>
</html>"""
