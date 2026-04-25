package com.stinkyweasel.dextilt.sensor

data class SensorAvailability(
    val hasAccelerometer: Boolean = false,
    val hasGyroscope: Boolean = false,
    val hasRotationVector: Boolean = false,
    val hasGravity: Boolean = false
) {
    fun userText(): String = buildString {
        append("Accelerometer: ").append(if (hasAccelerometer) "available" else "missing")
        append("\nGyroscope: ").append(if (hasGyroscope) "available" else "missing")
        append("\nRotation vector: ").append(if (hasRotationVector) "available" else "missing")
        append("\nGravity: ").append(if (hasGravity) "available" else "missing")
        if (!hasAccelerometer) append("\nGesture mode cannot work without an accelerometer. Manual buttons still work.")
        else if (!hasGyroscope) append("\nGyroscope missing. DexTilt will use simple tilt-only mode.")
    }
}

data class SensorSnapshot(
    val ax: Float = 0f,
    val ay: Float = 0f,
    val az: Float = 0f,
    val gx: Float = 0f,
    val gy: Float = 0f,
    val gz: Float = 0f,
    val timestampNs: Long = 0L
) {
    companion object { fun empty() = SensorSnapshot() }
}
