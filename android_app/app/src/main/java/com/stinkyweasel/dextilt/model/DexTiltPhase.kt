package com.stinkyweasel.dextilt.model

enum class DexTiltPhase(val label: String) {
    Disconnected("Disconnected"),
    Connected("Connected"),
    Paired("Paired"),
    Disarmed("Disarmed"),
    Armed("Armed"),
    BaselineDetecting("Baseline detecting"),
    ReadyForGesture("Ready for gesture"),
    Recording("Recording"),
    Matching("Matching"),
    LowConfidence("Low confidence"),
    AwaitingConfirmation("Awaiting confirmation"),
    CommandSending("Command sending"),
    CommandAccepted("Command accepted"),
    CommandRejected("Command rejected"),
    Error("Error")
}
