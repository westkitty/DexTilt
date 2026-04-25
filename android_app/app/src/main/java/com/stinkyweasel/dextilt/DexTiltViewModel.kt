package com.stinkyweasel.dextilt

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.stinkyweasel.dextilt.gesture.FaceDownDetector
import com.stinkyweasel.dextilt.gesture.GestureMatcher
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
                    } else {
                        ui = ui.copy(phase = DexTiltPhase.CommandRejected, lastResult = result.userMessage, lastError = result.userMessage, armed = false)
                        feedback.failure()
                        log("Command rejected: ${result.errorCode ?: "unknown"} ${result.userMessage}")
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
        ui = ui.copy(armed = false, phase = if (ui.pairing != null) DexTiltPhase.Disarmed else DexTiltPhase.Disconnected)
        log("Sensors stopped.")
    }

    fun startRecording() {
        recordingSamples.clear()
        recording = true
        localTesting = false
        faceDownDetector.reset()
        sensorRepository.start()
        ui = ui.copy(phase = DexTiltPhase.Recording, recordingCount = 0, lastResult = "Recording. Start face down and perform the gesture.")
        feedback.tick()
    }

    fun saveRecording(name: String = "Open GPT Gesture") {
        recording = false
        val sources = buildList {
            add("accelerometer")
            if (ui.sensorAvailability.hasGyroscope) add("gyroscope")
            if (ui.sensorAvailability.hasRotationVector) add("rotation_vector")
        }
        if (recordingSamples.size < 8) {
            error("Not enough motion samples captured. Record again with a clear face-down start.")
            return
        }
        val template = gestures.buildTemplate(name, recordingSamples.toList(), sources, ui.sensitivity)
        gestures.save(template)
        ui = ui.copy(activeGesture = template, phase = DexTiltPhase.Disarmed, lastResult = "Saved gesture ${template.name} (${template.durationMs} ms).")
        feedback.success()
        log("Gesture saved: ${template.gestureId} duration=${template.durationMs}ms")
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
        faceDownDetector.reset()
        sensorRepository.start()
        ui = ui.copy(armed = true, phase = DexTiltPhase.BaselineDetecting, lastResult = "Armed. Place phone face down and stable.", lastConfidence = null, confirmationRequired = false)
        feedback.tick()
    }

    fun disarm() {
        armedSamples.clear()
        collectingArmedGesture = false
        ui = ui.copy(armed = false, phase = DexTiltPhase.Disarmed, lastResult = "Disarmed.")
        feedback.tick()
    }

    fun confirmMediumConfidence() {
        val pending = mediumConfidenceCommand ?: return
        mediumConfidenceCommand = null
        ui = ui.copy(confirmationRequired = false)
        sendCommand(pending.first, "primary_open_gpt", pending.second)
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
        if (recording || localTesting) recordingSamples.add(sample)
        if (recordingSamples.size > 200) recordingSamples.removeAt(0)

        if (ui.armed) handleArmedSample(sample, stable)
        ui = ui.copy(sensorSnapshot = snapshot, faceDownStable = stable, recordingCount = recordingSamples.size)
    }

    private fun handleArmedSample(sample: SensorSample, stable: Boolean) {
        if (!stable && !collectingArmedGesture) {
            ui = ui.copy(phase = DexTiltPhase.BaselineDetecting, lastResult = "Waiting for face-down stable start.")
            return
        }
        if (stable && !collectingArmedGesture) {
            ui = ui.copy(phase = DexTiltPhase.ReadyForGesture, lastResult = "Baseline ready. Perform gesture.")
            if (movementStarted(sample)) {
                collectingArmedGesture = true
                armedSamples.clear()
            }
            return
        }
        if (collectingArmedGesture) {
            armedSamples.add(sample)
            val durationMs = if (armedSamples.size > 1) (armedSamples.last().timestampNs - armedSamples.first().timestampNs) / 1_000_000L else 0L
            if (durationMs >= 1400 || armedSamples.size >= 125) finishArmedGesture()
        }
    }

    private fun finishArmedGesture() {
        collectingArmedGesture = false
        val template = ui.activeGesture ?: return
        val match = matcher.match(template, armedSamples.toList(), faceDownStable = true)
        ui = ui.copy(phase = DexTiltPhase.Matching, lastConfidence = match.confidence, lastResult = "Gesture confidence ${match.confidence}: ${match.label}")
        when {
            match.shouldTrigger -> sendCommand("open_gpt_default_browser", template.gestureId, match.confidence)
            match.requiresConfirmation -> {
                mediumConfidenceCommand = "open_gpt_default_browser" to match.confidence
                ui = ui.copy(phase = DexTiltPhase.AwaitingConfirmation, confirmationRequired = true, armed = false, lastResult = "Medium confidence (${match.confidence}). Confirm to open GPT.")
                feedback.tick()
            }
            else -> {
                ui = ui.copy(phase = DexTiltPhase.LowConfidence, armed = false, lastResult = "Unknown gesture. Confidence ${match.confidence}. No command sent.")
                feedback.failure()
            }
        }
    }

    private fun movementStarted(sample: SensorSample): Boolean {
        val gyro = kotlin.math.abs(sample.gx) + kotlin.math.abs(sample.gy) + kotlin.math.abs(sample.gz)
        val tilt = kotlin.math.abs(sample.ax) + kotlin.math.abs(sample.ay)
        return gyro > 0.65f || tilt > 4.0f
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
        sensorRepository.stop()
        super.onCleared()
    }
}
