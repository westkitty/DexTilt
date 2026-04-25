package com.stinkyweasel.dextilt.model

data class CommandMessage(
    val protocol: String = "dextilt.v1",
    val deviceId: String,
    val receiverId: String,
    val commandId: String,
    val gestureId: String,
    val timestampMs: Long,
    val nonce: String,
    val confidence: Int,
    val signature: String = ""
)

data class CommandResult(
    val ok: Boolean,
    val accepted: Boolean,
    val userMessage: String,
    val errorCode: String? = null
)

data class CalibrationStep(
    val stepId: String,
    val label: String,
    val instruction: String
)
