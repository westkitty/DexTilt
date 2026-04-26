package com.stinkyweasel.dextilt

import android.app.Application
import android.hardware.SensorManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.stinkyweasel.dextilt.gesture.FaceDownDetector
import com.stinkyweasel.dextilt.gesture.GestureMatcher
import com.stinkyweasel.dextilt.gesture.GestureTemplate
import com.stinkyweasel.dextilt.gesture.GestureTemplateStore
import com.stinkyweasel.dextilt.gesture.SensorSample
import com.stinkyweasel.dextilt.model.CalibrationStep
import com.stinkyweasel.dextilt.model.DexTiltPhase
import com.stinkyweasel.dextilt.model.DexTiltUiState
import com.stinkyweasel.dextilt.model.PairingPayload
import com.stinkyweasel.dextilt.model.PairingState
import com.stinkyweasel.dextilt.net.DexTiltClient
import com.stinkyweasel.dextilt.sensor.SensorRepository
import com.stinkyweasel.dextilt.sensor.SensorSnapshot
import com.stinkyweasel.dextilt.storage.DexTiltPrefs
import com.stinkyweasel.dextilt.ui.Feedback
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class DexTiltViewModel(application: Application) : AndroidViewModel(application) {
    private val prefs = DexTiltPrefs(application)
    private val client = DexTiltClient()
    private val gestures = GestureTemplateStore(application)
    private val faceDownDetector = FaceDownDetector()
    private val matcher = GestureMatcher()
    private val feedback = Feedback(application)
    private val sensorRepository = SensorRepository(application) { sample, snapshot -> onSensorSample(sample, snapshot) }

    private val recordingSamples = mutableListOf<SensorSample>()
    private val armedSamples = mutableListOf<SensorSample>()
    private var recording = false
    private var localTesting = false
    private var collectingArmedGesture = false
    private var mediumConfidenceCommand: Pair<String, Int>? = null
    private var phoneControlPollJob: Job? = null
    private var phoneControlReadySinceMs: Long = 0L

    private val trainingFirstPassSamples = mutableListOf<SensorSample>()
    private var trainingPass = 0
    private var trainingCollectingMotion = false
    private var trainingBaselineReady = false
    private var trainingStableEndSinceNs: Long? = null
    private var trainingBlockedUntilNs: Long = 0L

    private var armedBaselineReady = false
    private var armedStableEndSinceNs: Long? = null
    private var lastStableState = false

    // Live phone state sync — observational only, never triggers state transitions
    private var lastLiveSendMs = 0L
    private var prevLiveRoll = 0f
    private var prevLivePitch = 0f
    private var prevLiveYaw = 0f
    private var prevFaceDownStable = false
    private var prevLivePhase = ""
    private val LIVE_CHANGE_THRESHOLD = 0.01f
    private val LIVE_HEARTBEAT_MS = 2000L
    private val LIVE_MIN_INTERVAL_MS = 250L

    // How long after polling starts to drain ALL controls before executing any,
    // regardless of their created_at_ms. Guards against clock skew and race conditions.
    private val PHONE_CONTROL_DRAIN_WINDOW_MS = 3000L

    private val minGestureDurationMs = 400L
    private val maxGestureDurationMs = 5000L
    private val stableEndHoldMs = 600L

    val calibrationSteps = listOf(
        CalibrationStep("face_down", "Face down", "Place the phone face down and keep it stable."),
        CalibrationStep("tilt_up", "Tilt up", "Tilt the top edge up."),
        CalibrationStep("tilt_down", "Tilt down", "Tilt the top edge down."),
        CalibrationStep("tilt_left", "Tilt left", "Tilt the phone to the left."),
        CalibrationStep("tilt_right", "Tilt right", "Tilt the phone to the right."),
        CalibrationStep("rotate_cw", "Rotate clockwise", "Rotate the phone clockwise while face down."),
        CalibrationStep("rotate_ccw", "Rotate counterclockwise", "Rotate the phone counterclockwise while face down.")
    )

    var ui by mutableStateOf(DexTiltUiState())
        private set

    init {
        val pairing = prefs.pairingState()
        val activeGesture = gestures.active()
        ui = ui.copy(
            pairing = pairing,
            phase = if (pairing != null) DexTiltPhase.Disarmed else DexTiltPhase.Disconnected,
            activeGesture = activeGesture,
            sensorAvailability = sensorRepository.availability(),
            manualHost = pairing?.host ?: "",
            manualPort = pairing?.port?.toString() ?: "47391",
            manualReceiverId = pairing?.receiverId ?: ""
        )
        log("DexTilt started. ${if (pairing != null) "Paired receiver loaded." else "No receiver paired."}")
        if (pairing != null) startPhoneControlPolling()
    }

    fun updateManualHost(value: String) { ui = ui.copy(manualHost = value.trim()) }
    fun updateManualPort(value: String) { ui = ui.copy(manualPort = value.filter { it.isDigit() }.take(5)) }
    fun updateManualToken(value: String) { ui = ui.copy(manualToken = value.trim()) }
    fun updateManualReceiverId(value: String) { ui = ui.copy(manualReceiverId = value.trim()) }
    fun setSensitivity(value: String) { ui = ui.copy(sensitivity = value) }

    fun handleQr(raw: String) {
        runCatching { PairingPayload.fromJson(raw) }
            .onSuccess { pairWithPayload(it) }
            .onFailure { error("That QR code was not a DexTilt pairing code. Open the Mac dashboard and scan the current QR.") }
    }

    fun pairManual() {
        val port = ui.manualPort.toIntOrNull() ?: 47391
        val payload = PairingPayload(
            protocol = "dextilt.pairing.v1",
            host = ui.manualHost,
            port = port,
            receiverId = ui.manualReceiverId,
            pairingToken = ui.manualToken,
            expiresAtMs = System.currentTimeMillis() + 300_000
        )
        if (payload.host.isBlank() || payload.receiverId.isBlank() || payload.pairingToken.isBlank()) {
            error("Enter host, port, receiver ID, and token from the Mac dashboard.")
            return
        }
        pairWithPayload(payload)
    }

    private fun pairWithPayload(payload: PairingPayload) {
        ui = ui.copy(phase = DexTiltPhase.Connected, lastError = null, lastResult = "Pairing with ${payload.host}:${payload.port}...")
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val deviceId = prefs.getOrCreateDeviceId()
                    client.pair(payload, deviceId, prefs.deviceName())
                }
            }.onSuccess { response ->
                if (!response.ok || response.sharedSecret.isBlank()) {
                    error(response.userMessage.ifBlank { "Pairing failed. Refresh the Mac dashboard and scan again." })
                    return@onSuccess
                }
                val state = PairingState(payload.host, payload.port, response.receiverId, response.deviceId, prefs.deviceName(), System.currentTimeMillis())
                prefs.savePairing(state, response.sharedSecret)
                ui = ui.copy(pairing = state, phase = DexTiltPhase.Disarmed, lastResult = response.userMessage, manualHost = state.host, manualPort = state.port.toString(), manualReceiverId = state.receiverId)
                feedback.success()
                log("Paired with receiver ${state.receiverId} at ${state.host}:${state.port}")
                phoneControlReadySinceMs = System.currentTimeMillis()
                startPhoneControlPolling()
            }.onFailure {
                error(it.message ?: "Pairing failed. Check the Mac receiver address and token.")
            }
        }
    }

    fun testHealth() {
        val base = ui.pairing?.baseUrl() ?: manualBaseUrlOrNull() ?: run {
            error("Pair or enter a Mac receiver host and port first.")
            return
        }
        ui = ui.copy(healthText = "Checking $base...", phase = DexTiltPhase.Connected)
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { client.health(base) } }
                .onSuccess { ui = ui.copy(healthText = it, phase = if (ui.pairing != null) DexTiltPhase.Disarmed else DexTiltPhase.Connected); log("Health check: $it") }
                .onFailure { error("DexTilt could not reach the Mac receiver. Check Wi-Fi, host, port, and firewall.") }
        }
    }

    fun sendManual(commandId: String) = sendCommand(commandId, "manual", 100)

    private fun sendCommand(commandId: String, gestureId: String, confidence: Int) {
        val pairing = ui.pairing ?: run { error("Pair the phone with the Mac before sending commands."); return }
        val secret = prefs.sharedSecret() ?: run { error("Missing pairing secret. Re-pair the phone with the Mac."); return }
        ui = ui.copy(phase = DexTiltPhase.CommandSending, lastResult = "Sending $commandId...")
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { client.sendCommand(pairing, secret, commandId, gestureId, confidence) } }
                .onSuccess { result ->
                    if (result.ok && result.accepted) {
                        ui = ui.copy(phase = DexTiltPhase.CommandAccepted, lastResult = result.userMessage, lastError = null, armed = false)
                        feedback.success()
                        log("Command accepted: $commandId confidence=$confidence")
                        notifyMac("command_fired", "Command fired: $commandId")
                    } else {
                        ui = ui.copy(phase = DexTiltPhase.CommandRejected, lastResult = result.userMessage, lastError = result.userMessage, armed = false)
                        feedback.failure()
                        log("Command rejected: ${result.errorCode ?: "unknown"} ${result.userMessage}")
                        notifyMac("command_blocked", "Command blocked: ${result.userMessage}")
                    }
                }
                .onFailure { error(it.message ?: "DexTilt could not send the command to the Mac.") }
        }
    }

    fun startSensors() {
        sensorRepository.start()
        log("Sensors started.")
    }

    fun stopSensors() {
        sensorRepository.stop()
        recording = false
        localTesting = false
        collectingArmedGesture = false
        trainingPass = 0
        trainingCollectingMotion = false
        trainingBaselineReady = false
        trainingStableEndSinceNs = null
        trainingBlockedUntilNs = 0L
        armedBaselineReady = false
        armedStableEndSinceNs = null
        ui = ui.copy(armed = false, phase = if (ui.pairing != null) DexTiltPhase.Disarmed else DexTiltPhase.Disconnected)
        log("Sensors stopped.")
    }

    fun startRecording() {
        recordingSamples.clear()
        trainingFirstPassSamples.clear()
        recording = true
        localTesting = false
        trainingPass = 1
        trainingCollectingMotion = false
        trainingBaselineReady = false
        trainingStableEndSinceNs = null
        trainingBlockedUntilNs = 0L
        lastStableState = false
        faceDownDetector.reset()
        sensorRepository.start()
        ui = ui.copy(
            phase = DexTiltPhase.BaselineDetecting,
            recordingCount = 0,
            lastResult = "Training started. Pass 1: place phone face down and stable."
        )
        notifyMac("training_started", "Training started. Pass 1: place phone face down and stable.")
        feedback.tick()
    }

    fun saveRecording(name: String = "Open GPT Gesture") {
        ui = ui.copy(lastResult = "Training now saves automatically after two matching face-down-to-face-down passes.")
        notifyMac("training_save_info", "Training saves automatically after two matching passes.")
        feedback.tick()
    }

    fun startLocalGestureTest() {
        recordingSamples.clear()
        localTesting = true
        recording = false
        faceDownDetector.reset()
        sensorRepository.start()
        ui = ui.copy(phase = DexTiltPhase.Matching, lastResult = "Testing gesture locally. No Mac command will fire.", lastConfidence = null)
        feedback.tick()
    }

    fun finishLocalGestureTest() {
        localTesting = false
        val template = ui.activeGesture ?: run { error("Train a gesture before testing."); return }
        val match = matcher.match(template, recordingSamples.toList(), ui.faceDownStable)
        ui = ui.copy(
            phase = if (match.requiresConfirmation) DexTiltPhase.AwaitingConfirmation else if (match.shouldTrigger) DexTiltPhase.ReadyForGesture else DexTiltPhase.LowConfidence,
            lastConfidence = match.confidence,
            lastResult = "Local test: ${match.label}. Confidence ${match.confidence}. ${if (match.shouldTrigger) "Would trigger." else if (match.requiresConfirmation) "Would ask for confirmation." else "Would ignore."}",
            confirmationRequired = match.requiresConfirmation
        )
        log("Local gesture test confidence=${match.confidence} label=${match.label}")
    }

    fun arm() {
        if (ui.pairing == null) { error("Pair with the Mac before arming DexTilt."); return }
        if (ui.activeGesture == null) { error("Train a gesture before arming DexTilt."); return }
        armedSamples.clear()
        collectingArmedGesture = false
        armedBaselineReady = false
        armedStableEndSinceNs = null
        lastStableState = false
        faceDownDetector.reset()
        sensorRepository.start()
        ui = ui.copy(armed = true, phase = DexTiltPhase.BaselineDetecting, lastResult = "Armed. Place phone face down and stable.", lastConfidence = null, confirmationRequired = false)
        notifyMac("armed_started", "DexTilt armed. Place phone face down and stable.")
        feedback.tick()
    }

    fun disarm() {
        armedSamples.clear()
        collectingArmedGesture = false
        armedBaselineReady = false
        armedStableEndSinceNs = null
        ui = ui.copy(armed = false, phase = DexTiltPhase.Disarmed, lastResult = "Disarmed.")
        feedback.tick()
    }

    fun confirmMediumConfidence() {
        val pending = mediumConfidenceCommand ?: return
        mediumConfidenceCommand = null
        ui = ui.copy(confirmationRequired = false)
        sendCommand(pending.first, "primary_dexdictate_toggle", pending.second)
    }

    fun runCalibrationStep() {
        val pairing = ui.pairing ?: run { error("Pair before calibration."); return }
        val secret = prefs.sharedSecret() ?: run { error("Missing pairing secret. Re-pair first."); return }
        val step = calibrationSteps.getOrNull(ui.calibrationStepIndex) ?: return
        sensorRepository.start()
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { client.sendCalibration(pairing, secret, step.stepId, step.label, "detected", "Phone-side calibration step marked detected.") } }
                .onSuccess {
                    val next = ui.calibrationStepIndex + 1
                    val complete = next >= calibrationSteps.size
                    ui = ui.copy(
                        calibrationStepIndex = next.coerceAtMost(calibrationSteps.lastIndex),
                        calibrationComplete = complete,
                        phase = if (complete) DexTiltPhase.Disarmed else DexTiltPhase.Connected,
                        lastResult = if (complete) "Calibration complete." else "Calibration step sent: ${step.label}."
                    )
                    feedback.success()
                    log("Calibration step sent: ${step.stepId}")
                }
                .onFailure { error("Calibration update did not reach the Mac. Check pairing and network.") }
        }
    }

    fun resetPairing() {
        prefs.resetPairing()
        gestures.deleteAll()
        ui = DexTiltUiState(sensorAvailability = sensorRepository.availability())
        feedback.tick()
        log("Local pairing and gestures reset on Android.")
    }

    private fun onSensorSample(sample: SensorSample, snapshot: SensorSnapshot) {
        val stable = faceDownDetector.update(sample)

        if (stable && !lastStableState && (recording || ui.armed)) {
            notifyMac("face_down_stable", "Face-down stable.")
        }

        when {
            recording -> handleTrainingSample(sample, stable)
            localTesting -> {
                recordingSamples.add(sample)
                if (recordingSamples.size > 200) recordingSamples.removeAt(0)
            }
        }

        if (ui.armed) handleArmedSample(sample, stable)
        maybeSendLiveState(sample, stable)
        lastStableState = stable
        ui = ui.copy(sensorSnapshot = snapshot, faceDownStable = stable, recordingCount = recordingSamples.size)
    }

    private fun handleArmedSample(sample: SensorSample, stable: Boolean) {
        if (!collectingArmedGesture) {
            if (stable) {
                if (!armedBaselineReady) {
                    armedBaselineReady = true
                    ui = ui.copy(phase = DexTiltPhase.ReadyForGesture, lastResult = "Baseline ready. Perform gesture.")
                    notifyMac("baseline_ready", "Baseline ready. Perform gesture.")
                }
                return
            }

            if (armedBaselineReady && movementStarted(sample)) {
                collectingArmedGesture = true
                armedStableEndSinceNs = null
                armedSamples.clear()
                armedSamples.add(sample)
                ui = ui.copy(phase = DexTiltPhase.Recording, lastResult = "Recording gesture. Return phone face down to finish.")
                notifyMac("armed_recording_started", "Recording gesture. Return phone face down to finish.")
                return
            }

            ui = ui.copy(phase = DexTiltPhase.BaselineDetecting, lastResult = "Waiting for face-down stable start.")
            return
        }

        armedSamples.add(sample)
        val durationMs = gestureDurationMs(armedSamples)

        if (stable && durationMs >= minGestureDurationMs) {
            val since = armedStableEndSinceNs ?: sample.timestampNs.also { armedStableEndSinceNs = it }
            val heldMs = (sample.timestampNs - since) / 1_000_000L
            if (heldMs >= stableEndHoldMs) {
                notifyMac("gesture_captured", "Gesture captured. Matching now.")
                finishArmedGesture()
                return
            }
        } else {
            armedStableEndSinceNs = null
        }

        if (durationMs >= maxGestureDurationMs) {
            notifyMac("gesture_timeout", "Gesture timed out. Return face down faster.")
            finishArmedGesture()
        }
    }

    private fun finishArmedGesture() {
        collectingArmedGesture = false
        armedBaselineReady = false
        armedStableEndSinceNs = null
        val template = ui.activeGesture ?: return
        val match = matcher.match(template, armedSamples.toList(), faceDownStable = true)
        ui = ui.copy(phase = DexTiltPhase.Matching, lastConfidence = match.confidence, lastResult = "Gesture confidence ${match.confidence}: ${match.label}")
        notifyMac("gesture_match", "Gesture ${match.label}. Confidence ${match.confidence}.")
        when {
            match.shouldTrigger -> sendCommand("dex_dictate_toggle_listen", template.gestureId, match.confidence)
            match.requiresConfirmation -> {
                mediumConfidenceCommand = "dex_dictate_toggle_listen" to match.confidence
                ui = ui.copy(phase = DexTiltPhase.AwaitingConfirmation, confirmationRequired = true, armed = false, lastResult = "Medium confidence (${match.confidence}). Confirm to open GPT.")
                notifyMac("command_blocked", "Command blocked: medium confidence ${match.confidence}. Confirmation required.")
                feedback.tick()
            }
            else -> {
                ui = ui.copy(phase = DexTiltPhase.LowConfidence, armed = false, lastResult = "Unknown gesture. Confidence ${match.confidence}. No command sent.")
                notifyMac("command_blocked", "Command blocked: low confidence ${match.confidence}.")
                feedback.failure()
            }
        }
    }


    private fun handleTrainingSample(sample: SensorSample, stable: Boolean) {
        if (trainingPass == 0) return

        if (sample.timestampNs < trainingBlockedUntilNs) {
            ui = ui.copy(phase = DexTiltPhase.Recording, lastResult = "Second recording starts in 3 seconds. Keep phone face down.")
            return
        }

        if (!trainingCollectingMotion) {
            if (stable) {
                if (!trainingBaselineReady) {
                    trainingBaselineReady = true
                    ui = ui.copy(phase = DexTiltPhase.ReadyForGesture, lastResult = "Baseline ready. Perform gesture pass $trainingPass.")
                    notifyMac("baseline_ready", "Baseline ready. Perform gesture pass $trainingPass.")
                }
                return
            }

            if (trainingBaselineReady && movementStarted(sample)) {
                trainingCollectingMotion = true
                trainingStableEndSinceNs = null
                recordingSamples.clear()
                recordingSamples.add(sample)
                ui = ui.copy(phase = DexTiltPhase.Recording, lastResult = "Recording $trainingPass started. Return phone face down to finish.")
                notifyMac("recording_started", "Recording $trainingPass started. Return phone face down to finish.")
                return
            }

            ui = ui.copy(phase = DexTiltPhase.BaselineDetecting, lastResult = "Waiting for face-down stable baseline.")
            return
        }

        recordingSamples.add(sample)
        val durationMs = gestureDurationMs(recordingSamples)

        if (stable && durationMs >= minGestureDurationMs) {
            val since = trainingStableEndSinceNs ?: sample.timestampNs.also { trainingStableEndSinceNs = it }
            val heldMs = (sample.timestampNs - since) / 1_000_000L
            if (heldMs >= stableEndHoldMs) {
                finishTrainingPass(sample.timestampNs)
                return
            }
        } else {
            trainingStableEndSinceNs = null
        }

        if (durationMs >= maxGestureDurationMs) {
            notifyMac("training_timeout", "Recording $trainingPass timed out. Return face down faster.")
            finishTrainingPass(sample.timestampNs)
        }
    }

    private fun finishTrainingPass(nowNs: Long) {
        val captured = recordingSamples.toList()
        if (captured.size < 8) {
            recording = false
            trainingPass = 0
            trainingCollectingMotion = false
            trainingBaselineReady = false
            trainingStableEndSinceNs = null
            error("Not enough samples captured. Record again with a clear face-down start and end.")
            notifyMac("training_failed", "Training failed: too few samples.")
            return
        }

        if (trainingPass == 1) {
            trainingFirstPassSamples.clear()
            trainingFirstPassSamples.addAll(captured)
            recordingSamples.clear()
            trainingPass = 2
            trainingCollectingMotion = false
            trainingBaselineReady = false
            trainingStableEndSinceNs = null
            trainingBlockedUntilNs = nowNs + 3_000_000_000L
            faceDownDetector.reset()
            ui = ui.copy(phase = DexTiltPhase.Recording, lastResult = "Recording 1 captured. Second recording starts in 3 seconds.")
            notifyMac("recording_captured", "Recording 1 captured. Second recording starts in 3 seconds.")
            feedback.success()
            return
        }

        val validationTemplate = gestures.buildTemplate("Validation", trainingFirstPassSamples.toList(), sensorSources(), ui.sensitivity)
        val match = matcher.match(validationTemplate, captured, faceDownStable = true)

        if (match.confidence < 60) {
            recording = false
            trainingPass = 0
            trainingCollectingMotion = false
            trainingBaselineReady = false
            trainingStableEndSinceNs = null
            ui = ui.copy(phase = DexTiltPhase.LowConfidence, lastConfidence = match.confidence, lastResult = "Training failed. Recordings did not match. Confidence ${match.confidence}.")
            notifyMac("training_failed", "Training failed. Recordings did not match. Confidence ${match.confidence}.")
            feedback.failure()
            return
        }

        val template = gestures.buildTemplate("Open GPT Gesture", trainingFirstPassSamples.toList(), sensorSources(), ui.sensitivity)
        gestures.save(template)
        sendGesturePreviewIfPaired(template, trainingFirstPassSamples.toList())
        recording = false
        trainingPass = 0
        trainingCollectingMotion = false
        trainingBaselineReady = false
        trainingStableEndSinceNs = null
        ui = ui.copy(activeGesture = template, phase = DexTiltPhase.Disarmed, lastConfidence = match.confidence, lastResult = "Gesture saved. Two recordings matched with confidence ${match.confidence}.")
        notifyMac("gesture_saved", "Gesture saved. Two recordings matched with confidence ${match.confidence}.")
        feedback.success()
        log("Gesture saved: ${template.gestureId} duration=${template.durationMs}ms validation_confidence=${match.confidence}")
    }

    private fun gestureDurationMs(samples: List<SensorSample>): Long {
        return if (samples.size > 1) ((samples.last().timestampNs - samples.first().timestampNs) / 1_000_000L).coerceAtLeast(0L) else 0L
    }

    private fun sensorSources(): List<String> {
        return buildList {
            add("accelerometer")
            if (ui.sensorAvailability.hasGyroscope) add("gyroscope")
            if (ui.sensorAvailability.hasRotationVector) add("rotation_vector")
        }
    }

    private fun movementStarted(sample: SensorSample): Boolean {
        val gyro = kotlin.math.abs(sample.gx) + kotlin.math.abs(sample.gy) + kotlin.math.abs(sample.gz)
        val tilt = kotlin.math.abs(sample.ax) + kotlin.math.abs(sample.ay)
        return gyro > 0.65f || tilt > 4.0f
    }


    private data class OrientationResult(
        val qw: Float, val qx: Float, val qy: Float, val qz: Float,
        val roll: Float, val pitch: Float, val yaw: Float
    )

    private fun deriveOrientation(sample: SensorSample): OrientationResult {
        val rv = sample.rotationVector
        return if (rv != null && rv.size >= 4) {
            val q = FloatArray(4)
            SensorManager.getQuaternionFromVector(q, rv)
            val rm = FloatArray(9)
            SensorManager.getRotationMatrixFromVector(rm, rv)
            val angles = FloatArray(3)
            SensorManager.getOrientation(rm, angles)
            // getOrientation returns [azimuth(yaw), pitch, roll]
            OrientationResult(q[0], q[1], q[2], q[3], angles[2], angles[1], angles[0])
        } else {
            val roll = kotlin.math.atan2(sample.ay.toDouble(), sample.az.toDouble()).toFloat()
            val pitch = kotlin.math.atan2(
                -sample.ax.toDouble(),
                kotlin.math.sqrt(sample.ay.toDouble() * sample.ay + sample.az.toDouble() * sample.az)
            ).toFloat()
            OrientationResult(1f, 0f, 0f, 0f, roll, pitch, 0f)
        }
    }

    /** Observational live-state sender. MUST NOT call haptics, notifications, or state transitions. */
    private fun maybeSendLiveState(sample: SensorSample, stable: Boolean) {
        val pairing = ui.pairing ?: return
        val secret = prefs.sharedSecret() ?: return

        val now = System.currentTimeMillis()
        val orientation = deriveOrientation(sample)

        // Always update UI orientation fields at no network cost
        ui = ui.copy(
            roll = orientation.roll, pitch = orientation.pitch, yaw = orientation.yaw,
            qw = orientation.qw, qx = orientation.qx, qy = orientation.qy, qz = orientation.qz,
            liveSyncActive = true
        )

        val changed = kotlin.math.abs(orientation.roll  - prevLiveRoll)  > LIVE_CHANGE_THRESHOLD
                   || kotlin.math.abs(orientation.pitch - prevLivePitch) > LIVE_CHANGE_THRESHOLD
                   || kotlin.math.abs(orientation.yaw   - prevLiveYaw)   > LIVE_CHANGE_THRESHOLD
                   || stable != prevFaceDownStable
                   || ui.phase.name != prevLivePhase
        val heartbeat = (now - lastLiveSendMs) >= LIVE_HEARTBEAT_MS
        if (!changed && !heartbeat) return
        if (now - lastLiveSendMs < LIVE_MIN_INTERVAL_MS) return

        lastLiveSendMs = now
        prevLiveRoll = orientation.roll; prevLivePitch = orientation.pitch; prevLiveYaw = orientation.yaw
        prevFaceDownStable = stable; prevLivePhase = ui.phase.name

        val sensorData = mapOf<String, Any>(
            "face_down_stable" to stable,
            "phase"            to ui.phase.name,
            "ax" to sample.ax.toDouble(), "ay" to sample.ay.toDouble(), "az" to sample.az.toDouble(),
            "gx" to if (sample.hasGyro) sample.gx.toDouble() else 0.0,
            "gy" to if (sample.hasGyro) sample.gy.toDouble() else 0.0,
            "gz" to if (sample.hasGyro) sample.gz.toDouble() else 0.0,
            "roll"  to orientation.roll.toDouble(),
            "pitch" to orientation.pitch.toDouble(),
            "yaw"   to orientation.yaw.toDouble(),
            "qw" to orientation.qw.toDouble(), "qx" to orientation.qx.toDouble(),
            "qy" to orientation.qy.toDouble(), "qz" to orientation.qz.toDouble(),
            "orientation_source" to if (sample.rotationVector != null) "rotation_vector" else "accelerometer",
            "timestamp_ms" to now
        )
        viewModelScope.launch(Dispatchers.IO) {
            try { client.sendLivePhoneState(pairing, secret, sensorData) } catch (_: Exception) {}
        }
    }

    private fun sendGesturePreviewIfPaired(template: GestureTemplate, samples: List<SensorSample>) {
        val pairing = ui.pairing ?: return
        val secret = prefs.sharedSecret() ?: return
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val preview = buildGesturePreviewPayload(template, samples)
                client.sendGesturePreview(pairing, secret, preview)
            } catch (_: Exception) {}
        }
    }

    private fun buildGesturePreviewPayload(template: GestureTemplate, samples: List<SensorSample>): Map<String, Any> {
        val step = maxOf(1, samples.size / 120)
        val downsampled = samples.filterIndexed { i, _ -> i % step == 0 }.take(120)
        val t0 = downsampled.firstOrNull()?.timestampNs ?: 0L
        var px = 0.0; var py = 0.0; var pz = 0.0
        var vx = 0.0; var vy = 0.0; var vz = 0.0
        var prevNs = t0
        val points = downsampled.map { s ->
            val dt = ((s.timestampNs - prevNs) / 1_000_000_000.0).coerceIn(0.0, 0.1)
            prevNs = s.timestampNs
            vx += s.ax * dt; vy += s.ay * dt; vz += (s.az.toDouble() + 9.8) * dt
            px += vx * dt; py += vy * dt; pz += vz * dt
            val tMs = ((s.timestampNs - t0) / 1_000_000L).toInt().coerceIn(0, 60000)
            val rv = s.rotationVector
            val q = if (rv != null && rv.size >= 4) FloatArray(4).also { SensorManager.getQuaternionFromVector(it, rv) } else null
            mutableMapOf<String, Any>(
                "t_ms" to tMs,
                "x" to px.coerceIn(-10.0, 10.0), "y" to py.coerceIn(-10.0, 10.0), "z" to pz.coerceIn(-10.0, 10.0),
                "rx" to (s.gx * dt).coerceIn(-12.57, 12.57),
                "ry" to (s.gy * dt).coerceIn(-12.57, 12.57),
                "rz" to (s.gz * dt).coerceIn(-12.57, 12.57),
                "qw" to (q?.get(0)?.toDouble() ?: 1.0).coerceIn(-1.0, 1.0),
                "qx" to (q?.get(1)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0),
                "qy" to (q?.get(2)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0),
                "qz" to (q?.get(3)?.toDouble() ?: 0.0).coerceIn(-1.0, 1.0)
            )
        }
        // Normalize x/y/z to fit in [-2.5, 2.5]
        val maxPos = points.maxOfOrNull { p ->
            listOf(p["x"] as Double, p["y"] as Double, p["z"] as Double).maxOf { kotlin.math.abs(it) }
        }?.coerceAtLeast(0.001) ?: 0.001
        val scale = 2.5 / maxPos
        points.forEach { p ->
            p["x"] = ((p["x"] as Double) * scale).coerceIn(-2.5, 2.5)
            p["y"] = ((p["y"] as Double) * scale).coerceIn(-2.5, 2.5)
            p["z"] = ((p["z"] as Double) * scale).coerceIn(-2.5, 2.5)
        }
        return mapOf(
            "gesture_id"   to template.gestureId,
            "name"         to template.name,
            "duration_ms"  to template.durationMs,
            "created_at_ms" to System.currentTimeMillis(),
            "confidence"   to 100,
            "points"       to points
        )
    }

    private fun notifyMac(eventId: String, detail: String) {
        val pairing = ui.pairing ?: return
        val secret = prefs.sharedSecret() ?: return
        log("Notify Mac: $detail")
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    client.sendEvent(pairing, secret, eventId, detail)
                }
            }.onFailure {
                log("Mac notification event failed: ${it.message ?: "unknown"}")
            }
        }
    }


    private fun startPhoneControlPolling() {
        if (phoneControlPollJob?.isActive == true) return

        // Safety rule: connecting must never auto-start training/arming.
        // Only dashboard controls created after this app session becomes ready are allowed.
        phoneControlReadySinceMs = System.currentTimeMillis()

        phoneControlPollJob = viewModelScope.launch {
            while (true) {
                val pairing = ui.pairing
                if (pairing != null) {
                    runCatching {
                        withContext(Dispatchers.IO) {
                            client.pollPhoneControl(pairing)
                        }
                    }.onSuccess { control ->
                        if (control != null) {
                            val now = System.currentTimeMillis()
                            val isStale = control.createdAtMs == 0L || control.createdAtMs <= phoneControlReadySinceMs
                            val inDrainWindow = (now - phoneControlReadySinceMs) < PHONE_CONTROL_DRAIN_WINDOW_MS
                            if (isStale || inDrainWindow) {
                                val reason = if (isStale) "stale" else "drain window"
                                log("Ignored dashboard control [$reason]: ${control.action} created=${control.createdAtMs} ready=$phoneControlReadySinceMs")
                                if (isStale) notifyMac("phone_control_ignored", "Ignored stale dashboard control: ${control.action}. Phone connected idle.")
                            } else {
                                handlePhoneControl(control.action)
                            }
                        }
                    }.onFailure {
                        log("Phone control poll failed: ${it.message ?: "unknown"}")
                    }
                }
                delay(1000L)
            }
        }
        log("Phone control polling started. Phone connected idle.")
        notifyMac("phone_control_ready", "Phone connected. Waiting idle for fresh dashboard control.")
    }

    private fun handlePhoneControl(action: String) {
        when (action) {
            "start_training" -> {
                notifyMac("phone_control_received", "Dashboard control received: start training.")
                startRecording()
            }
            "start_local_test" -> {
                notifyMac("phone_control_received", "Dashboard control received: start local test.")
                startLocalGestureTest()
            }
            "arm" -> {
                notifyMac("phone_control_received", "Dashboard control received: arm.")
                arm()
            }
            "disarm" -> {
                notifyMac("phone_control_received", "Dashboard control received: disarm.")
                disarm()
            }
            "cancel" -> {
                notifyMac("phone_control_received", "Dashboard control received: cancel.")
                stopSensors()
                ui = ui.copy(lastResult = "Cancelled. Connected idle.")
            }
            "start_sensors" -> {
                notifyMac("phone_control_received", "Dashboard control received: start sensors.")
                startSensors()
            }
            "stop_sensors" -> {
                notifyMac("phone_control_received", "Dashboard control received: stop sensors.")
                stopSensors()
            }
            else -> log("Unknown phone control action ignored: $action")
        }
    }

    private fun manualBaseUrlOrNull(): String? {
        val host = ui.manualHost.takeIf { it.isNotBlank() } ?: return null
        val port = ui.manualPort.toIntOrNull() ?: return null
        return "http://$host:$port"
    }

    private fun error(message: String) {
        ui = ui.copy(phase = DexTiltPhase.Error, lastError = message, lastResult = message, armed = false)
        feedback.failure()
        log("ERROR: $message")
    }

    private fun log(message: String) {
        val redacted = message.replace(Regex("(?i)(secret|token|signature)=\\S+"), "\$1=[redacted]")
        ui = ui.copy(logs = (listOf(redacted) + ui.logs).take(80))
    }

    override fun onCleared() {
        phoneControlPollJob?.cancel()
        sensorRepository.stop()
        super.onCleared()
    }
}
