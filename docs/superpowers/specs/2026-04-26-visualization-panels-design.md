# DexTilt Visualization Panels — Design Spec
**Date:** 2026-04-26  
**Scope:** Live Phone Orientation panel + Gesture Preview panel + Android live sync + Android orientation UI + Dashboard cockpit redesign  
**Approach:** Approach B — new panels with targeted fetches, 30-second full-page reload removed

---

## Design Philosophy

**DexTilt is a control cockpit, not a toy demo.**

- The Mac dashboard is the **operator console** — calm, scannable, status-first.
- The Android app is the **sensor wand** — usable while tired, large targets, no ambiguous states.
- Every screen must immediately answer: *What state is DexTilt in? What should I do next? What just happened?*

---

## Context

Andrew needs to see what his phone is doing while it is face-down, without looking at the phone screen. DexTilt already captures sensor data (accelerometer, gyroscope, rotation vector) and performs two-pass gesture training. This spec adds:

1. A live phone orientation feed from Android → Mac → browser (250ms polling)
2. A gesture preview feed sent automatically after successful two-pass training
3. Two Three.js panels on the Mac dashboard rendering a 3D phone/tablet slab
4. A System State strip at the top of the dashboard (always-visible status bar)
5. Redesigned action hierarchy — primary / secondary / dangerous control zones
6. Queue panel with expiration countdown
7. Android UI additions: orientation readout + live sync indicator + clearer state text
8. Removal of the existing 30-second full-page reload, replaced with targeted panel fetches

**Scope constraint:** Do not break pairing, command registry, phone-control polling, gesture training, DexDictate toggle, Enter command, notifications, or Android build. Preserve all working pipeline behavior.

---

## Aesthetic Direction

### Web Dashboard — "Precision Sensor Monitor"

A dark instrument-panel aesthetic. Feels like mission control, not a generic web app. Every data point is a reading from a sensor; the UI should honour that.

**Typography (via Google Fonts CDN):**
- `Orbitron` — panel headers, labels, button text
- `Space Mono` — all numeric sensor values, phase text, status indicators

**Color palette (CSS variables):**
```css
--bg:          #070d1a;   /* very dark navy */
--panel-bg:    rgba(8, 20, 45, 0.95);
--border:      rgba(0, 200, 230, 0.18);
--accent:      #00e5ff;   /* electric cyan — active data, screen face */
--accent-dim:  rgba(0, 229, 255, 0.35);
--amber:       #ff9100;   /* face_down_stable = true warning */
--green:       #00e676;   /* accepted/ready states */
--red:         #ff1744;   /* error */
--text-hi:     #e8f4f8;
--text-lo:     rgba(160, 200, 220, 0.6);
--phone-back:  #8b0000;   /* deep crimson */
--phone-screen: #00e5ff;  /* matches accent */
```

**3D scene:**
- Canvas background: `#0a0f1e`
- GridHelper colors: primary `#0d4060`, secondary `#102040`
- Ambient light: `0x223366`; directional: `0x4488cc`
- Trail line: `#00e5ff` at 40% opacity

**Panel components:**
- Each panel: `border: 1px solid var(--border)`, `border-radius: 8px`, subtle `box-shadow: 0 0 24px rgba(0,200,230,0.06)`
- Status dot (pulsing CSS keyframe) when live data age < 500ms
- Sensor value rows: monospace, `font-variant-numeric: tabular-nums`
- Values flash `#00e5ff` for 200ms on update via a CSS class toggle
- Play/Pause/Restart: `background: transparent; border: 1px solid var(--border); color: var(--accent)`; hover brightens border to full cyan

**What makes it unforgettable:** The phone's screen face in 3D is the same `#00e5ff` electric cyan as every active indicator on the dashboard. The moment you see roll/pitch change, the glowing screen tells you which side is up at a glance.

---

### Android App — "Sensor Preview Card" additions

The existing dark Material 3 theme (`#0B0D10` bg, `#D7E3FF` primary) is kept. New additions blend in:

**Orientation Card** (new Composable, added to Train tab and Debug tab):
- Shows roll, pitch, yaw in degrees (converted from radians) — three rows, monospace font
- Shows `face_down_stable` as a colour-coded indicator dot (green = stable, amber = moving)
- Shows quaternion (qw, qx, qy, qz) if rotation vector available

**Live Sync Indicator** (small, non-intrusive):
- A pulsing dot in `Color(0xFF00E5FF)` with text "Live → Mac" when actively sending
- Shown in the StatusCard when `liveSyncActive = true` in UiState
- Disappears when not paired or no sensor stream active

---

## System Architecture

```
Android (Kotlin/Compose)
  SensorRepository → onSampleCallback
    ↓ throttled 250ms
  DexTiltViewModel.sendLiveState() [coroutine, fire-and-forget]
    ↓
  DexTiltClient.sendLivePhoneState(pairing, secret, payload)
    POST /phone-state (signed envelope + sensor fields)
    ↓
Mac receiver (FastAPI/Python)
  POST /phone-state → validate_signed_envelope → clamp → StateStore.set_last_phone_state()
  GET  /phone-state → StateStore.get_last_phone_state()
    ↑ fetched every 250ms
  Browser dashboard (Three.js)
    initLivePhoneScene() → requestAnimationFrame render loop
    setInterval(updateLivePhoneState, 250) → setPhoneTransform()

Android (on training save, line ~506)
  DexTiltViewModel.sendGesturePreviewIfPaired(template, trainingFirstPassSamples)
    → downsample to ≤120 pts → clamp → normalize
  DexTiltClient.sendGesturePreview(pairing, secret, payload)
    POST /gesture-preview
    ↓
Mac receiver
  POST /gesture-preview → validate → StateStore.set_last_gesture_preview()
  GET  /gesture-preview → StateStore.get_last_gesture_preview()
    ↑ polled every 2000ms
  Browser dashboard
    setInterval(checkGesturePreview, 2000)
    initGesturePreviewScene(preview) → BufferGeometry trail + requestAnimationFrame replay
```

---

## Files Changed

### Mac receiver

| File | Change |
|------|--------|
| `mac_receiver/src/dextilt_receiver/models.py` | Add `LivePhoneStateEnvelope`, `GesturePreviewPoint`, `GesturePreviewEnvelope` |
| `mac_receiver/src/dextilt_receiver/state.py` | Add `last_phone_state`, `last_gesture_preview` to data; add 4 getter/setter methods |
| `mac_receiver/src/dextilt_receiver/app.py` | Add 5 routes: POST+GET /phone-state, POST+GET /gesture-preview, GET /api/queue-status |
| `mac_receiver/src/dextilt_receiver/dashboard.py` | Add Two Three.js panels; add Google Fonts CDN; apply instrument-panel CSS; replace 30s reload with targeted fetch intervals |

### Android

| File | Change |
|------|--------|
| `android_app/.../net/DexTiltClient.kt` | Add `sendLivePhoneState()` and `sendGesturePreview()` methods |
| `android_app/.../DexTiltViewModel.kt` | Add throttled live sender, gesture preview generator, orientation UiState fields |
| `android_app/.../model/DexTiltUiState.kt` | Add `roll`, `pitch`, `yaw`, `qw`, `qx`, `qy`, `qz`, `liveSyncActive` fields |
| `android_app/.../MainActivity.kt` | Add `OrientationCard` composable, `LiveSyncIndicator` to StatusCard |

---

## Detailed Implementation

### 1. models.py — New Models

```python
# Extra='ignore' so standard CommandMessage fields + extra fields coexist in one POST body
class LivePhoneStateEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    # standard signed envelope fields (same 8 as CommandMessage)
    protocol: str; device_id: str; receiver_id: str; command_id: str
    gesture_id: str; timestamp_ms: int; nonce: str; confidence: int; signature: str
    # extra sensor data (not signed, validated/clamped separately)
    face_down_stable: bool = False
    phase: str = Field(default="", max_length=32)
    ax: float = 0.0; ay: float = 0.0; az: float = 0.0
    gx: float = 0.0; gy: float = 0.0; gz: float = 0.0
    roll: float = 0.0; pitch: float = 0.0; yaw: float = 0.0
    qw: float = 1.0; qx: float = 0.0; qy: float = 0.0; qz: float = 0.0
    orientation_source: str = Field(default="accelerometer", max_length=32)
    device_id_extra: str = Field(default="", alias="device_id", max_length=128)  # from envelope

class GesturePreviewPoint(BaseModel):
    model_config = ConfigDict(extra='ignore')
    t_ms: int = 0
    x: float = 0.0; y: float = 0.0; z: float = 0.0
    rx: float = 0.0; ry: float = 0.0; rz: float = 0.0
    qw: float = 1.0; qx: float = 0.0; qy: float = 0.0; qz: float = 0.0

class GesturePreviewEnvelope(BaseModel):
    model_config = ConfigDict(extra='ignore')
    # standard signed envelope
    protocol: str; device_id: str; receiver_id: str; command_id: str
    gesture_id: str; timestamp_ms: int; nonce: str; confidence: int; signature: str
    # extra preview data
    name: str = Field(default="", max_length=128)
    duration_ms: int = 0
    created_at_ms: int = 0
    points: list[GesturePreviewPoint] = []
```

**Clamping helpers** (added to models.py or app.py):
```python
def clamp(v, lo, hi): return max(lo, min(hi, v))
def clamp_phone_state(d: dict) -> dict:
    for k in ("ax","ay","az","gx","gy","gz"): d[k] = clamp(d.get(k,0), -50, 50)
    for k in ("roll","pitch","yaw"): d[k] = clamp(d.get(k,0), -12.57, 12.57)
    for k in ("qw","qx","qy","qz"): d[k] = clamp(d.get(k,0 if k!="qw" else 1), -1.0, 1.0)
    d["phase"] = str(d.get("phase",""))[:32]
    d["orientation_source"] = str(d.get("orientation_source",""))[:32]
    d["device_id"] = str(d.get("device_id",""))[:128]
    return d

def clamp_preview_point(p: dict) -> dict:
    p["t_ms"] = clamp(p.get("t_ms",0), 0, 60000)
    for k in ("x","y","z"): p[k] = clamp(p.get(k,0), -10, 10)
    for k in ("rx","ry","rz"): p[k] = clamp(p.get(k,0), -12.57, 12.57)
    for k in ("qw","qx","qy","qz"): p[k] = clamp(p.get(k,0 if k!="qw" else 1), -1.0, 1.0)
    return p
```

---

### 2. state.py — StateStore Additions

Add to `state.data` initializer:
```python
"last_phone_state": None,
"last_gesture_preview": None,
```

Add methods:
```python
def set_last_phone_state(self, state: dict):
    with self._lock: self.data["last_phone_state"] = state

def get_last_phone_state(self) -> dict | None:
    with self._lock: return self.data.get("last_phone_state")

def set_last_gesture_preview(self, preview: dict):
    with self._lock: self.data["last_gesture_preview"] = preview

def get_last_gesture_preview(self) -> dict | None:
    with self._lock: return self.data.get("last_gesture_preview")
```

---

### 3. app.py — 4 New Routes

```python
@app.post("/phone-state")
async def post_phone_state(request: Request):
    body = await request.json()
    ok, code, msg, _ = validate_signed_envelope(body, require_known_command=False)
    if not ok:
        return JSONResponse({"ok": False, "error": msg}, status_code=401)
    sanitized = clamp_phone_state(dict(body))
    store.set_last_phone_state(sanitized)
    # No EventLogger call — silent update to avoid log spam
    return {"ok": True, "accepted": True, "user_message": "Phone state received."}

@app.get("/phone-state")
async def get_phone_state():
    return {"ok": True, "state": store.get_last_phone_state()}

@app.post("/gesture-preview")
async def post_gesture_preview(request: Request):
    body = await request.json()
    ok, code, msg, _ = validate_signed_envelope(body, require_known_command=False)
    if not ok:
        return JSONResponse({"ok": False, "error": msg}, status_code=401)
    preview = dict(body)
    preview["name"] = str(preview.get("name", ""))[:128]
    preview["gesture_id"] = str(preview.get("gesture_id", ""))[:64]
    pts = preview.get("points", [])[:200]
    preview["points"] = [clamp_preview_point(dict(p)) for p in pts]
    store.set_last_gesture_preview(preview)
    event_logger.log({"event": "gesture_preview_received",
                      "gesture_id": preview.get("gesture_id",""),
                      "point_count": len(preview["points"])})
    return {"ok": True, "accepted": True, "user_message": "Gesture preview received."}

@app.get("/gesture-preview")
async def get_gesture_preview():
    return {"ok": True, "preview": store.get_last_gesture_preview()}
```

---

### 4. DexTiltClient.kt — New Methods

Pattern matches `sendCalibration`. Build a full map, sign the 8 canonical fields as a CommandMessage, merge extra fields, POST:

```kotlin
fun sendLivePhoneState(
    pairing: PairingState,
    sharedSecret: String,
    payload: Map<String, Any>   // must include all 8 CommandMessage fields + sensor data
): CommandResult {
    // payload already contains command_id="live_phone_state", gesture_id="live", confidence=100
    // plus ax, ay, az, gx, gy, gz, roll, pitch, yaw, qw, qx, qy, qz, face_down_stable, phase, orientation_source
    val json = ProtocolJson.mapToJson(payload) // serialize full map including extra fields
    return postJson(pairing.baseUrl() + "/phone-state", json)
}

fun sendGesturePreview(
    pairing: PairingState,
    sharedSecret: String,
    payload: Map<String, Any>   // command_id="gesture_preview" + name, duration_ms, points, etc.
): CommandResult {
    val json = ProtocolJson.mapToJson(payload)
    return postJson(pairing.baseUrl() + "/gesture-preview", json)
}
```

`ProtocolJson.mapToJson()` may need to be added if it doesn't exist — falls back to kotlinx.serialization or a Gson/Moshi call matching existing JSON serialization in the file.

The signature is computed over the 8 canonical fields using `DexTiltSigner.sign()` before building the full map, then the `signature` field is added to the map.

---

### 5. DexTiltViewModel.kt — Live Sender + Gesture Preview

**New UiState fields** (in `DexTiltUiState.kt`):
```kotlin
val roll: Float = 0f,
val pitch: Float = 0f,
val yaw: Float = 0f,
val qw: Float = 1f,
val qx: Float = 0f,
val qy: Float = 0f,
val qz: Float = 0f,
val liveSyncActive: Boolean = false,
```

**In DexTiltViewModel:**

```kotlin
private var lastLiveSendMs = 0L

// Call this from handleTrainingSample() and handleArmedSample() after processing:
private fun maybeSendLiveState(sample: SensorSample) {
    val now = System.currentTimeMillis()
    if (now - lastLiveSendMs < 250) return
    val pairing = ui.pairing ?: return
    val secret = getSharedSecret(pairing) ?: return
    lastLiveSendMs = now

    // Derive orientation
    val (qw, qx, qy, qz, roll, pitch, yaw) = deriveOrientation(sample)

    // Update UiState orientation fields
    _uiState.update { it.copy(roll=roll, pitch=pitch, yaw=yaw, qw=qw, qx=qx, qy=qy, qz=qz, liveSyncActive=true) }

    // Fire-and-forget coroutine
    viewModelScope.launch(Dispatchers.IO) {
        val payload = buildLivePayload(sample, qw, qx, qy, qz, roll, pitch, yaw, pairing, secret)
        client.sendLivePhoneState(pairing, secret, payload)
    }
}

private fun deriveOrientation(sample: SensorSample): OrientationResult {
    val rv = sample.rotationVector
    return if (rv != null && rv.size >= 4) {
        val q = FloatArray(4)
        SensorManager.getQuaternionFromVector(q, rv)
        // q = [w, x, y, z] in Android
        val rm = FloatArray(9)
        SensorManager.getRotationMatrixFromVector(rm, rv)
        val angles = FloatArray(3)
        SensorManager.getOrientation(rm, angles)
        OrientationResult(q[0], q[1], q[2], q[3], angles[1], angles[2], angles[0])
        // SensorManager.getOrientation: [0]=azimuth/yaw, [1]=pitch, [2]=roll
    } else {
        val roll = atan2(sample.ay.toDouble(), sample.az.toDouble()).toFloat()
        val pitch = atan2(-sample.ax.toDouble(),
            sqrt(sample.ay.toDouble().pow(2) + sample.az.toDouble().pow(2))).toFloat()
        OrientationResult(1f, 0f, 0f, 0f, roll, pitch, 0f)
    }
}
```

**Gesture preview after training save:**
```kotlin
// Right after gestures.save(template) at line ~506:
sendGesturePreviewIfPaired(template, trainingFirstPassSamples.toList())

private fun sendGesturePreviewIfPaired(template: GestureTemplate, samples: List<SensorSample>) {
    val pairing = ui.pairing ?: return
    val secret = getSharedSecret(pairing) ?: return
    viewModelScope.launch(Dispatchers.IO) {
        val preview = buildGesturePreview(template, samples, pairing, secret)
        client.sendGesturePreview(pairing, secret, preview)
    }
}

private fun buildGesturePreview(
    template: GestureTemplate,
    samples: List<SensorSample>,
    pairing: PairingState,
    secret: String
): Map<String, Any> {
    // Downsample to ≤120 points
    val step = maxOf(1, samples.size / 120)
    val downsampled = samples.filterIndexed { i, _ -> i % step == 0 }.take(120)

    val t0 = downsampled.firstOrNull()?.timestampNs ?: 0L
    var px = 0.0; var py = 0.0; var pz = 0.0
    var vx = 0.0; var vy = 0.0; var vz = 0.0
    var prevNs = t0

    val points = downsampled.mapIndexed { _, s ->
        val dt = (s.timestampNs - prevNs) / 1e9  // seconds
        prevNs = s.timestampNs
        // Simple integration (gravity-biased, visualization only)
        vx += s.ax * dt; vy += s.ay * dt; vz += (s.az + 9.8) * dt
        px += vx * dt; py += vy * dt; pz += vz * dt

        val tMs = ((s.timestampNs - t0) / 1_000_000).toInt()
        val rv = s.rotationVector
        val q = if (rv != null && rv.size >= 4) {
            FloatArray(4).also { SensorManager.getQuaternionFromVector(it, rv) }
        } else null
        mapOf(
            "t_ms" to tMs.coerceIn(0, 60000),
            "x" to px.coerceIn(-10.0, 10.0),
            "y" to py.coerceIn(-10.0, 10.0),
            "z" to pz.coerceIn(-10.0, 10.0),
            "rx" to (s.gx * dt).coerceIn(-12.57, 12.57),  // accumulated gyro rotation
            "ry" to (s.gy * dt).coerceIn(-12.57, 12.57),
            "rz" to (s.gz * dt).coerceIn(-12.57, 12.57),
            "qw" to (q?.get(0)?.toDouble() ?: 1.0).coerceIn(-1.0, 1.0),
            "qx" to (q?.get(1)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0),
            "qy" to (q?.get(2)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0),
            "qz" to (q?.get(3)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0),
        )
    }

    // Normalize x/y/z to [-2.5, 2.5]
    val maxVal = points.maxOf { p ->
        listOf(p["x"] as Double, p["y"] as Double, p["z"] as Double).maxOf { abs(it) }
    }.coerceAtLeast(0.001)
    val scale = 2.5 / maxVal
    val normalizedPoints = points.map { p ->
        p.toMutableMap().also { m ->
            m["x"] = ((m["x"] as Double) * scale).coerceIn(-2.5, 2.5)
            m["y"] = ((m["y"] as Double) * scale).coerceIn(-2.5, 2.5)
            m["z"] = ((m["z"] as Double) * scale).coerceIn(-2.5, 2.5)
        }
    }

    // Build signed envelope payload
    // buildSignedEnvelopeFields() is a private helper in DexTiltViewModel:
    //   returns Map<String,Any> with protocol, device_id, receiver_id, command_id,
    //   gesture_id, timestamp_ms, nonce, confidence — the 8 canonical signed fields.
    //   Signs using DexTiltSigner.sign(canonicalJson, sharedSecret).
    val unsigned = buildSignedEnvelopeFields(
        commandId = "gesture_preview",
        gestureId = template.gestureId,
        confidence = 100,
        pairing = pairing
    )
    val sig = DexTiltSigner.sign(unsigned, secret)
    return unsigned + mapOf(
        "signature" to sig,
        "name" to template.name,
        "duration_ms" to template.durationMs,
        "created_at_ms" to System.currentTimeMillis(),
        "points" to normalizedPoints
    )
}
```

---

### 6. MainActivity.kt — New Composables

**OrientationCard** (shown in Train tab and Debug tab):
```kotlin
@Composable
fun OrientationCard(uiState: DexTiltUiState) {
    DexCard {
        Text("Orientation", style = MaterialTheme.typography.titleSmall)
        // Three rows: Roll, Pitch, Yaw with degree values
        // One row: face_down_stable indicator dot
        // If qw/qx/qy/qz non-zero: quaternion row in smaller text
        // Uses monospace font + tabular numbers
    }
}
```

**LiveSyncIndicator** (added to StatusCard):
```kotlin
if (uiState.liveSyncActive) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        // Pulsing dot in Color(0xFF00E5FF)
        // Text("Live → Mac", fontFamily = monoFamily, fontSize = 11.sp)
    }
}
```

The pulsing dot uses an `infiniteTransition` alpha animation between 1f and 0.3f.

---

### 7. dashboard.py — Three.js Panels + Aesthetic

**Remove:**
```javascript
setInterval(() => location.reload(), 30000)
```

**Add targeted refresh loops:**
```javascript
setInterval(refreshStatus, 5000)      // paired device count
setInterval(refreshLogs, 8000)        // recent logs JSON
setInterval(refreshLastCommand, 3000) // last command/error
```

**Add Google Fonts CDN** to `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
```

**Add Three.js CDN:**
```html
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"
        onerror="document.getElementById('threejs-fallback').style.display='block'"></script>
```

**New CSS variables** added to existing `<style>`:
```css
:root {
  --bg: #070d1a; --panel-bg: rgba(8,20,45,.95);
  --border: rgba(0,200,230,.18); --accent: #00e5ff;
  --accent-dim: rgba(0,229,255,.35); --amber: #ff9100;
  --green: #00e676; --red: #ff1744;
  --text-hi: #e8f4f8; --text-lo: rgba(160,200,220,.6);
}
.panel-header { font-family: 'Orbitron', monospace; letter-spacing: .08em; }
.sensor-value { font-family: 'Space Mono', monospace; font-variant-numeric: tabular-nums; color: var(--accent); }
.sensor-value.updated { animation: flash 200ms ease-out; }
@keyframes flash { from { color: #ffffff; } to { color: var(--accent); } }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
.status-dot.live { animation: pulse 1s ease-in-out infinite; background: var(--accent); }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.3; } }
```

**Three.js helpers (inline JS, instrument-panel style):**

```javascript
function safeNumber(v, fallback=0, min=-Infinity, max=Infinity) {
    const n = parseFloat(v);
    return (isFinite(n)) ? Math.max(min, Math.min(max, n)) : fallback;
}

function createScene(containerId) {
    const el = document.getElementById(containerId);
    const W = el.clientWidth || 320, H = el.clientHeight || 220;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(W, H);
    renderer.setClearColor(0x0a0f1e, 1);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, W / H, 0.1, 100);
    camera.position.set(0, 3, 6); camera.lookAt(0, 0, 0);

    const grid = new THREE.GridHelper(10, 20, 0x0d4060, 0x102040);
    scene.add(grid);
    scene.add(new THREE.AmbientLight(0x223366, 1.5));
    const dir = new THREE.DirectionalLight(0x4488cc, 2);
    dir.position.set(3, 6, 4); scene.add(dir);

    return { renderer, camera, scene };
}

function createPhoneModel() {
    const group = new THREE.Group();
    // Body — deep crimson slab
    const body = new THREE.Mesh(
        new THREE.BoxGeometry(1.2, 2.2, 0.12),
        new THREE.MeshPhongMaterial({ color: 0x8b0000, shininess: 40 })
    );
    group.add(body);
    // Screen — electric cyan plane, offset +0.061 on Z
    const screen = new THREE.Mesh(
        new THREE.PlaneGeometry(1.05, 1.9),
        new THREE.MeshBasicMaterial({ color: 0x00e5ff, side: THREE.FrontSide })
    );
    screen.position.set(0, 0, 0.062);
    group.add(screen);
    // Notch — small dark box top-center of screen face
    const notch = new THREE.Mesh(
        new THREE.BoxGeometry(0.18, 0.04, 0.005),
        new THREE.MeshBasicMaterial({ color: 0x0a0f1e })
    );
    notch.position.set(0, 0.88, 0.065);
    group.add(notch);
    return group;
}

function setPhoneTransform(phoneGroup, state) {
    if (!state) return;
    const qw = safeNumber(state.qw, 1, -1, 1);
    const qx = safeNumber(state.qx, 0, -1, 1);
    const qy = safeNumber(state.qy, 0, -1, 1);
    const qz = safeNumber(state.qz, 0, -1, 1);
    const mag = Math.sqrt(qw*qw + qx*qx + qy*qy + qz*qz);
    if (mag > 0.1) {
        phoneGroup.quaternion.set(qx, qy, qz, qw).normalize();
    } else {
        // Fall back to roll/pitch/yaw Euler
        phoneGroup.rotation.set(
            safeNumber(state.roll, 0, -12.57, 12.57),
            safeNumber(state.yaw,  0, -12.57, 12.57),
            safeNumber(state.pitch,0, -12.57, 12.57)
        );
    }
    if (state.x !== undefined) {
        phoneGroup.position.set(
            safeNumber(state.x, 0, -5, 5),
            safeNumber(state.y, 0, -5, 5),
            safeNumber(state.z, 0, -5, 5)
        );
    }
}
```

**Panel 1 — Live Phone Orientation JS:**
```javascript
let liveScene = null, livePhone = null, liveRafId = null;

function initLivePhoneScene() {
    if (typeof THREE === 'undefined') return;
    const { renderer, camera, scene } = createScene('live-phone-canvas');
    livePhone = createPhoneModel();
    scene.add(livePhone);
    liveScene = { renderer, camera, scene };
    function animate() {
        liveRafId = requestAnimationFrame(animate);
        liveScene.renderer.render(liveScene.scene, liveScene.camera);
    }
    animate();
    setInterval(updateLivePhoneState, 250);
}

async function updateLivePhoneState() {
    try {
        const r = await fetch('/phone-state');
        const d = await r.json();
        const state = d.state;
        const noDataEl = document.getElementById('live-no-data');
        const dataEl = document.getElementById('live-data');
        if (!state) {
            noDataEl.style.display = 'block'; dataEl.style.display = 'none'; return;
        }
        noDataEl.style.display = 'none'; dataEl.style.display = 'block';
        setPhoneTransform(livePhone, state);
        // Update text readouts (using textContent for XSS safety)
        const ageMs = Date.now() - safeNumber(state.timestamp_ms, Date.now(), 0, 9e15);
        setVal('live-phase', state.phase || '—');
        setVal('live-face-down', state.face_down_stable ? 'YES' : 'NO');
        setVal('live-ax', safeNumber(state.ax,0).toFixed(3));
        setVal('live-ay', safeNumber(state.ay,0).toFixed(3));
        setVal('live-az', safeNumber(state.az,0).toFixed(3));
        setVal('live-gx', safeNumber(state.gx,0).toFixed(3));
        setVal('live-gy', safeNumber(state.gy,0).toFixed(3));
        setVal('live-gz', safeNumber(state.gz,0).toFixed(3));
        setVal('live-roll', (safeNumber(state.roll,0)*57.296).toFixed(1)+'°');
        setVal('live-pitch', (safeNumber(state.pitch,0)*57.296).toFixed(1)+'°');
        setVal('live-yaw', (safeNumber(state.yaw,0)*57.296).toFixed(1)+'°');
        setVal('live-quat', `${safeNumber(state.qw,1).toFixed(3)} ${safeNumber(state.qx,0).toFixed(3)} ${safeNumber(state.qy,0).toFixed(3)} ${safeNumber(state.qz,0).toFixed(3)}`);
        setVal('live-age', ageMs < 2000 ? ageMs+'ms ago' : (ageMs/1000).toFixed(1)+'s ago');
        document.getElementById('live-status-dot').className = 'status-dot' + (ageMs < 600 ? ' live' : '');
    } catch(e) { /* ignore fetch errors */ }
}

function setVal(id, text) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.classList.remove('updated');
    void el.offsetWidth; // reflow to restart animation
    el.classList.add('updated');
}
```

**Panel 2 — Gesture Preview JS:**
```javascript
let gestureScene = null, gesturePhone = null, gestureLine = null;
let gesturePoints = [], gestureRafId = null;
let gesturePlaying = false, gestureFrameIdx = 0;
let lastGestureId = null;

function initGesturePreviewScene(preview) {
    if (typeof THREE === 'undefined') return;
    if (!gestureScene) {
        const { renderer, camera, scene } = createScene('gesture-preview-canvas');
        gesturePhone = createPhoneModel();
        scene.add(gesturePhone);
        gestureScene = { renderer, camera, scene };
        function animate() {
            gestureRafId = requestAnimationFrame(animate);
            if (gesturePlaying && gesturePoints.length) advanceGestureFrame();
            gestureScene.renderer.render(gestureScene.scene, gestureScene.camera);
        }
        animate();
    }
    if (!preview || !preview.points || !preview.points.length) return;

    // Rebuild trail
    if (gestureLine) { gestureScene.scene.remove(gestureLine); gestureLine = null; }
    gesturePoints = preview.points;
    const vecs = gesturePoints.map(p =>
        new THREE.Vector3(safeNumber(p.x,0,-5,5), safeNumber(p.y,0,-5,5), safeNumber(p.z,0,-5,5)));
    const geo = new THREE.BufferGeometry().setFromPoints(vecs);
    gestureLine = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0x00e5ff, opacity: 0.4, transparent: true }));
    gestureScene.scene.add(gestureLine);

    // Update info display
    document.getElementById('gesture-name').textContent = preview.name || preview.gesture_id || '—';
    document.getElementById('gesture-duration').textContent = preview.duration_ms ? (preview.duration_ms/1000).toFixed(2)+'s' : '—';
    document.getElementById('gesture-points').textContent = gesturePoints.length;
    document.getElementById('gesture-confidence').textContent = preview.confidence != null ? preview.confidence+'%' : '—';
    document.getElementById('gesture-slider').max = Math.max(0, gesturePoints.length - 1);
    document.getElementById('gesture-no-data').style.display = 'none';
    document.getElementById('gesture-data').style.display = 'block';

    gestureFrameIdx = 0;
    updateGestureFrame(0);
}

function advanceGestureFrame() {
    if (gestureFrameIdx >= gesturePoints.length - 1) {
        gesturePlaying = false; return;
    }
    const cur = gesturePoints[gestureFrameIdx];
    const next = gesturePoints[gestureFrameIdx + 1];
    // Simple time-based advancement: advance 1 frame per ~16ms (rAF ~60fps)
    // For v1: nearest-frame sampling, advance when t_ms crosses wall clock
    gestureFrameIdx = Math.min(gestureFrameIdx + 1, gesturePoints.length - 1);
    document.getElementById('gesture-slider').value = gestureFrameIdx;
    updateGestureFrame(gestureFrameIdx);
}

function updateGestureFrame(index) {
    if (!gesturePoints.length) return;
    const pt = gesturePoints[Math.max(0, Math.min(index, gesturePoints.length-1))];
    setPhoneTransform(gesturePhone, { ...pt, qw: pt.qw, qx: pt.qx, qy: pt.qy, qz: pt.qz });
}

function playGesture()    { gesturePlaying = true; }
function pauseGesture()   { gesturePlaying = false; }
function restartGesture() { gestureFrameIdx = 0; gesturePlaying = true; updateGestureFrame(0); }

// Poll for new gesture previews every 2s
async function checkGesturePreview() {
    try {
        const r = await fetch('/gesture-preview');
        const d = await r.json();
        if (d.preview && d.preview.gesture_id !== lastGestureId) {
            lastGestureId = d.preview.gesture_id;
            initGesturePreviewScene(d.preview);
        }
        if (!d.preview) {
            document.getElementById('gesture-no-data').style.display = 'block';
            document.getElementById('gesture-data').style.display = 'none';
        }
    } catch(e) {}
}
// Start polling
setInterval(checkGesturePreview, 2000);
```

**HTML panel markup** (added to dashboard HTML string in dashboard.py):

```html
<!-- Live Phone Orientation Panel -->
<div class="panel" style="border:1px solid var(--border); border-radius:8px; background:var(--panel-bg); padding:16px; box-shadow:0 0 24px rgba(0,200,230,.06)">
  <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px">
    <span id="live-status-dot" class="status-dot"></span>
    <span class="panel-header" style="font-size:13px; color:var(--text-lo); letter-spacing:.12em; text-transform:uppercase">Live Phone Orientation</span>
  </div>
  <div id="live-phone-canvas" style="width:100%; height:220px; border-radius:6px; overflow:hidden; background:#0a0f1e"></div>
  <div id="live-no-data" style="text-align:center; padding:16px; color:var(--text-lo); font-family:'Space Mono',monospace; font-size:12px">
    No live phone data yet. Open DexTilt on Android and start sensor preview, training, or arming.
  </div>
  <div id="live-data" style="display:none">
    <div id="threejs-fallback" style="display:none; color:var(--amber); font-size:12px; padding:8px">3D preview unavailable — Three.js failed to load.</div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px 16px; margin-top:12px; font-size:12px">
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Phase</span>
      <span id="live-phase" class="sensor-value">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Face Down</span>
      <span id="live-face-down" class="sensor-value">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Accel X/Y/Z</span>
      <span><span id="live-ax" class="sensor-value">—</span> / <span id="live-ay" class="sensor-value">—</span> / <span id="live-az" class="sensor-value">—</span></span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Gyro X/Y/Z</span>
      <span><span id="live-gx" class="sensor-value">—</span> / <span id="live-gy" class="sensor-value">—</span> / <span id="live-gz" class="sensor-value">—</span></span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Roll/Pitch/Yaw</span>
      <span><span id="live-roll" class="sensor-value">—</span> / <span id="live-pitch" class="sensor-value">—</span> / <span id="live-yaw" class="sensor-value">—</span></span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Quaternion</span>
      <span id="live-quat" class="sensor-value" style="font-size:10px">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Updated</span>
      <span id="live-age" class="sensor-value">—</span>
    </div>
  </div>
</div>

<!-- Gesture Preview Panel -->
<div class="panel" style="border:1px solid var(--border); border-radius:8px; background:var(--panel-bg); padding:16px; box-shadow:0 0 24px rgba(0,200,230,.06); margin-top:16px">
  <div style="margin-bottom:12px">
    <span class="panel-header" style="font-size:13px; color:var(--text-lo); letter-spacing:.12em; text-transform:uppercase">Gesture Preview</span>
  </div>
  <div id="gesture-preview-canvas" style="width:100%; height:220px; border-radius:6px; overflow:hidden; background:#0a0f1e"></div>
  <div id="gesture-no-data" style="text-align:center; padding:16px; color:var(--text-lo); font-family:'Space Mono',monospace; font-size:12px">
    No gesture preview received yet. Train a gesture first.
  </div>
  <div id="gesture-data" style="display:none">
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:4px 16px; margin:12px 0; font-size:12px">
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Gesture</span>
      <span id="gesture-name" class="sensor-value">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Duration</span>
      <span id="gesture-duration" class="sensor-value">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Samples</span>
      <span id="gesture-points" class="sensor-value">—</span>
      <span style="color:var(--text-lo); font-family:'Orbitron',monospace">Confidence</span>
      <span id="gesture-confidence" class="sensor-value">—</span>
    </div>
    <div style="display:flex; align-items:center; gap:8px; margin-top:8px">
      <button onclick="playGesture()" style="background:transparent; border:1px solid var(--border); color:var(--accent); font-family:'Orbitron',monospace; font-size:11px; padding:4px 10px; border-radius:4px; cursor:pointer">▶ Play</button>
      <button onclick="pauseGesture()" style="background:transparent; border:1px solid var(--border); color:var(--accent); font-family:'Orbitron',monospace; font-size:11px; padding:4px 10px; border-radius:4px; cursor:pointer">⏸ Pause</button>
      <button onclick="restartGesture()" style="background:transparent; border:1px solid var(--border); color:var(--accent); font-family:'Orbitron',monospace; font-size:11px; padding:4px 10px; border-radius:4px; cursor:pointer">⟳ Restart</button>
      <input id="gesture-slider" type="range" min="0" max="100" value="0"
             oninput="gestureFrameIdx=parseInt(this.value); updateGestureFrame(gestureFrameIdx)"
             style="flex:1; accent-color:var(--accent)">
    </div>
  </div>
</div>
```

**Targeted refresh functions** (replace 30s full-page reload):
```javascript
async function refreshSystemStrip() {
    // Fetches /api/status + uses latest live phone state age for strip display
    try { const r = await fetch('/api/status'); const d = await r.json();
        setVal('strip-device-count', d.paired_count ?? '—');
        // last_phone_state age already tracked by updateLivePhoneState
    } catch(e) {}
}
async function refreshLogs() {
    try { const r = await fetch('/logs'); const d = await r.json();
        const el = document.getElementById('logs-container');
        if (el) el.textContent = (d.events || []).map(e => JSON.stringify(e)).join('\n');
    } catch(e) {}
}
async function refreshLastCommand() {
    try { const r = await fetch('/api/status'); const d = await r.json();
        if (d.last_command) setVal('last-cmd-display', JSON.stringify(d.last_command));
    } catch(e) {}
}
async function refreshQueue() {
    try { const r = await fetch('/api/queue-status'); const d = await r.json();
        renderQueuePanel(d.queue || []);
    } catch(e) {}
}
```

**Init on page load:**
```javascript
window.addEventListener('DOMContentLoaded', () => {
    initLivePhoneScene();
    if (typeof THREE !== 'undefined') initGesturePreviewScene(null);
    checkGesturePreview();
    // Targeted refresh loops (replaces 30s full-page reload)
    setInterval(refreshSystemStrip, 3000);
    setInterval(refreshLogs, 8000);
    setInterval(refreshLastCommand, 5000);
    setInterval(refreshQueue, 2000);
});
```

---

## 8. Dashboard UX Redesign — Cockpit Layout

This section covers the broader dashboard improvements requested alongside the visualization panels.

### 8a. System State Strip (top of page, always visible)

A persistent horizontal strip that answers "what state is DexTilt in?" without scrolling:

```html
<div id="system-state-strip">
  <!-- Receiver status dot + "Receiver running" -->
  <!-- Phone: "Connected – android_XXXX – 2s ago" OR "No phone connected" -->
  <!-- Phase: current phone phase text, colour-coded -->
  <!-- Queue: "Queue empty" OR "1 item queued, expires in Xs" -->
  <!-- Last command: "dexdictate_toggle (98%)" OR "—" -->
  <!-- Live sensor: pulsing dot when live state < 600ms old -->
</div>
```

Color coding for phase text:
- `green` — idle / paired / ready / accepted
- `yellow` — armed / recording / matching / waiting
- `red` — error / blocked / rejected
- `blue` — live visualization active

Strip polls `/api/status` + `/phone-state` every 3 seconds via targeted fetch. No full-page reload.

### 8b. Action Hierarchy Redesign

Current dashboard mixes all phone-control buttons at the same visual weight. New layout:

**Primary controls** (large, prominent, always visible when phone connected):
```
[ Start Training ]  [ Arm ]  [ Disarm ]  [ Cancel ]
```
Style: `background: var(--accent-dim)`, border accent, `font-size: 15px`, `padding: 10px 20px`

**Secondary controls** (smaller, grouped below primary):
```
[ Start Local Test ]  [ Start Sensor Preview ]  [ Stop Sensor Preview ]
```
Style: `background: transparent`, border dim, `font-size: 12px`

**Dangerous/destructive controls** (visually separated, require `confirm()` dialog):
```
⚠ [ Clear Queue ]  [ Reset Pairing ]  [ Delete Command ]
```
Style: `border-color: var(--red)`, `color: var(--red)`, grouped in a "Danger Zone" box with `border: 1px solid rgba(255,23,68,0.3)`. Each calls `confirm("Are you sure? This cannot be undone.")` before posting.

### 8c. Queue Panel

Replace the current implicit queue display with an explicit panel:

```
┌─ Phone Control Queue ──────────────────────────────┐
│ Action:      start_training                         │
│ Created:     2026-04-26 14:32:01                    │
│ Expires in:  28s   [████████████░░░░] (countdown)   │
│ Target:      android_abc123                         │
│ Status:      Queued / Delivered / Expired           │
│                              [ Clear Queue ]        │
└────────────────────────────────────────────────────┘
```

Queue panel polls a new **`GET /api/queue-status`** endpoint added to app.py. This returns:
```json
{"ok": true, "queue": [{"action": "start_training", "created_at_ms": 1234567890, "ttl_ms": 30000, "device_id": "android_..."}]}
```
The endpoint reads `store.state.data["phone_control_queue"]` directly (no side effects). Expiration countdown: compute `(created_at_ms + ttl_ms) - Date.now()` in JS, tick every second via `setInterval`.

If queue is empty: show "Phone connected idle" (green) or "No phone connected" (gray).

### 8d. Gesture Pipeline Section

Group gesture-related information into one section:

```
┌─ Gesture Pipeline ─────────────────────────────────┐
│ Active gesture:    DexDictate Toggle                │
│ Assigned command:  dexdictate_toggle                │
│ Confidence:        High ≥80% / Medium ≥60%          │
│ Last result:       Fired @ 94% confidence           │
│ Training status:   Saved · 2 passes · 47 samples    │
│                                                     │
│ [Gesture Preview — 3D animation panel here]         │
│ [Live Phone Orientation — 3D panel here]            │
└────────────────────────────────────────────────────┘
```

Both Three.js panels live inside this section.

### 8e. Command Registry Improvements

Current display: raw JSON. New display:

| Label | Command ID | Type | Enabled | Test |
|-------|-----------|------|---------|------|
| DexDictate Toggle | `dexdictate_toggle` | shell | ✓ | [Test] |

- `Label` = `description` field if present, else `command_id` formatted
- `command_id` shown in smaller monospace text below label
- Test result appears inline as `✓ OK` or `✗ failed: ...` for 3 seconds
- Edit/Delete buttons shown on hover or in a small dropdown
- Full JSON shown in expandable `<details>` block only

### 8f. Logs

- Move logs to bottom of page or a collapsible `<details>` panel
- `<details open>` by default but can be collapsed
- Add filter buttons: `All | Events | Commands | Errors | Phone Control | Gesture`
- Filter is JS-only (hide/show rows by class), no server round-trip
- Log lines: monospace, `font-size: 11px`, truncated to 120 chars with `title` for full text

---

## 9. Android UX Improvements

### 9a. State Text Clarity

Replace vague phase strings with explicit human-readable status. The big status text in `StatusCard` should show:

| DexTiltPhase | Display text |
|---|---|
| Disconnected | "Not connected to Mac" |
| Connected (idle) | "Connected idle — no action pending" |
| WaitingForBaseline | "Waiting for face-down stable baseline" |
| BaselineReady | "Baseline ready — perform gesture" |
| Recording (pass 1) | "Recording — Pass 1 of 2" |
| Recording (pass 2) | "Recording — Pass 2 of 2" |
| Matching | "Matching gesture…" |
| GestureSaved | "Gesture saved ✓" |
| Armed | "Armed — waiting for gesture" |
| CommandFired | "Command fired ✓" |
| CommandBlocked | "Command blocked — try again" |

These are display strings only; underlying phase enum is unchanged.

### 9b. OrientationCard Composable

Added to both **Train** tab and **Debug** tab:

```kotlin
@Composable
fun OrientationCard(uiState: DexTiltUiState) {
    DexCard {
        Text("Orientation", style = MaterialTheme.typography.titleSmall)
        Spacer(8.dp)
        // Face-down indicator row: dot (green if stable, amber if not) + text
        Row { FaceDownDot(uiState.faceDownStable); Text(if(uiState.faceDownStable) "Face-down stable" else "Not face-down") }
        Spacer(4.dp)
        // Roll / Pitch / Yaw rows (converted to degrees)
        MonoRow("Roll",  "${(uiState.roll * 57.296).format(1)}°")
        MonoRow("Pitch", "${(uiState.pitch * 57.296).format(1)}°")
        MonoRow("Yaw",   "${(uiState.yaw  * 57.296).format(1)}°")
        if (uiState.qw != 1f || uiState.qx != 0f) {
            Spacer(4.dp)
            MonoRow("Q", "${uiState.qw.format(3)} ${uiState.qx.format(3)} ${uiState.qy.format(3)} ${uiState.qz.format(3)}")
        }
    }
}
```

### 9c. LiveSyncIndicator

Added to `StatusCard`, visible only when `uiState.liveSyncActive == true`:

```kotlin
if (uiState.liveSyncActive) {
    val alpha by rememberInfiniteTransition().animateFloat(
        initialValue = 1f, targetValue = 0.3f,
        animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse)
    )
    Row(Modifier.alpha(alpha)) {
        Box(Modifier.size(8.dp).background(Color(0xFF00E5FF), CircleShape))
        Spacer(4.dp)
        Text("Live → Mac", fontFamily = monoFamily, fontSize = 11.sp, color = Color(0xFF00E5FF))
    }
}
```

### 9d. Training Flow Text

In the Train tab, add instructional text that updates with phase:

- Before baseline: "Place phone face-down and hold still"
- Baseline ready: "Baseline set — perform your gesture now"
- After pass 1: "Pass 1 recorded — place face-down and hold still for pass 2"
- Pass 2 ready: "Perform the same gesture again"
- After pass 2: show confidence + "Gesture saved" or "Recordings didn't match — try again"

### 9e. Haptics Constraints (no new code needed, just don't add new ones)

Existing haptic calls are preserved. New rule: the live phone state sender (`maybeSendLiveState()`) must **not** call any haptic feedback. Sending live data is a background observation, not a state transition.

### 9f. Safety Invariants

These must be verified in code review:
- `maybeSendLiveState()` does not call `trainStart()`, `arm()`, `disarm()`, or any haptic
- `sendGesturePreviewIfPaired()` does not modify training state or trigger UI transitions
- Both new coroutines catch exceptions silently and do not propagate errors to UiState

---

## 10. Critical Performance Constraints

### 10a. Volatile phone state — no disk hammering

`StateStore.set_last_phone_state()` must NOT call `save()`. Live phone state is volatile (4 Hz from Android). Disk writes at 4 Hz will hammer the SSD.

**Solution:** Store `last_phone_state` as `self._live_phone_state` — a plain instance attribute outside `self.data`. Since `save()` only persists `self.data`, the live state is never written to disk.

`last_gesture_preview` IS stored in `self.data` and saved to disk (one write per training save — acceptable).

### 10b. Change-aware Android sender

Do not send `/phone-state` on every sample if values haven't changed.

**Threshold:** Skip send if `abs(roll - prevRoll) < 0.01 && abs(pitch - prevPitch) < 0.01 && abs(yaw - prevYaw) < 0.01 && face_down_stable == prevFaceDown && phase == prevPhase`. Only send when any of these exceed threshold, or when 2000ms have passed since last send (heartbeat).

**Never send** while sensors are stopped or while no sensor stream is active.

### 10c. Three.js geometry disposal

When replacing the gesture trail, dispose old objects before creating new:
```javascript
if (gestureLine) {
    gestureScene.scene.remove(gestureLine);
    gestureLine.geometry.dispose();
    gestureLine.material.dispose();
    gestureLine = null;
}
```
Similarly dispose renderer and scene objects if a scene is torn down.

---

## Security Checklist

- All data from fetch responses rendered via `.textContent` only
- Preview/state JSON never embedded in `<script>` tags or `innerHTML`
- `safeNumber()` guards all numeric values before use
- String fields truncated to max lengths before storage and before display
- `json.dumps()` used safely in Python for any embedded data
- Route `/phone-state` and `/gesture-preview` POST require valid HMAC signature

---

## Verification

```bash
# 1. Python syntax check
cd /Users/andrew/Projects/DexTilt/DexTilt
PYTHONPATH=mac_receiver/src python3 -m py_compile \
  mac_receiver/src/dextilt_receiver/app.py \
  mac_receiver/src/dextilt_receiver/dashboard.py \
  mac_receiver/src/dextilt_receiver/state.py \
  mac_receiver/src/dextilt_receiver/actions.py

# 2. Android build
export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"
./scripts/build_android_debug_apk.sh
cp android_app/app/build/outputs/apk/debug/app-debug.apk release/DexTilt-debug.apk

# 3. Install (if device connected)
adb install -r release/DexTilt-debug.apk

# 4. Restart receiver
cd mac_receiver && source .venv/bin/activate && PYTHONPATH=src python -m dextilt_receiver

# 5. Dashboard
open http://127.0.0.1:47391/status
```

**Manual validation checklist:**
- [ ] Phone connects idle — System State strip shows "Connected idle"
- [ ] Arm or start training explicitly → Live panel updates within ~500ms
- [ ] Phone slab rotates in 3D as phone is moved; cyan screen face visible
- [ ] `face_down_stable` = YES → amber indicator; NO → neutral
- [ ] All sensor values updating without full-page reload
- [ ] Train a gesture → Gesture Preview panel appears automatically (within 2s poll)
- [ ] Play/Pause/Restart/slider all work
- [ ] No 30-second full-page reload (watch Network tab in browser DevTools)
- [ ] Status, logs, last command panels still update via targeted fetches
- [ ] System State strip stays current (phase, last command, live dot)
- [ ] Primary controls (Train/Arm/Disarm/Cancel) are larger than secondary controls
- [ ] Dangerous controls (Clear Queue, Reset Pairing, Delete Command) require confirm()
- [ ] Queue panel shows expiration countdown when action is queued
- [ ] Command registry shows human label, not just raw command_id
- [ ] Logs are at bottom / collapsible; filter buttons work client-side
- [ ] Android OrientationCard shows roll/pitch/yaw in Train + Debug tabs
- [ ] Android LiveSyncIndicator pulses cyan in StatusCard when sensor active
- [ ] Android state text is explicit (e.g. "Recording — Pass 1 of 2")
- [ ] Android training flow shows instructional text per phase
- [ ] `maybeSendLiveState()` does not trigger haptics or state transitions

---

## Not In This Spec (Deferred)

- WebSocket or SSE — future upgrade path for lower latency
- 3D orbit controls for camera — future nice-to-have
- Full physics-accurate inertial tracking — explicitly out of scope
- Local test flow redesign (face-down-to-score) — significant ViewModel changes, separate spec
- Gesture assignment UI (per-gesture command + thresholds) — separate spec
- Full command registry CRUD redesign — out of scope for this pass (display improvements only)

---

## Bible Update

Append at completion — see Bible update instructions in command args. Include Python syntax check result, Android build result, APK install result, live testing results (be explicit about what was and was not tested).
