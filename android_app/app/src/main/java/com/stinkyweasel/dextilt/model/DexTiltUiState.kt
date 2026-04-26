package com.stinkyweasel.dextilt.model

import com.stinkyweasel.dextilt.gesture.GestureTemplate
import com.stinkyweasel.dextilt.sensor.SensorAvailability
import com.stinkyweasel.dextilt.sensor.SensorSnapshot

data class DexTiltUiState(
    val phase: DexTiltPhase = DexTiltPhase.Disconnected,
    val pairing: PairingState? = null,
    val healthText: String = "Not tested yet.",
    val lastResult: String = "No command sent yet.",
    val lastError: String? = null,
    val logs: List<String> = emptyList(),
    val sensorAvailability: SensorAvailability = SensorAvailability(),
    val sensorSnapshot: SensorSnapshot = SensorSnapshot.empty(),
    val faceDownStable: Boolean = false,
    val activeGesture: GestureTemplate? = null,
    val lastConfidence: Int? = null,
    val confirmationRequired: Boolean = false,
    val sensitivity: String = "normal",
    val armed: Boolean = false,
    val recordingCount: Int = 0,
    val calibrationStepIndex: Int = 0,
    val calibrationComplete: Boolean = false,
    val manualHost: String = "",
    val manualPort: String = "47391",
    val manualToken: String = "",
    val manualReceiverId: String = "",
    val roll: Float = 0f,
    val pitch: Float = 0f,
    val yaw: Float = 0f,
    val qw: Float = 1f,
    val qx: Float = 0f,
    val qy: Float = 0f,
    val qz: Float = 0f,
    val liveSyncActive: Boolean = false
)
