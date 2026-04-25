package com.stinkyweasel.dextilt.gesture

data class SensorSample(
    val timestampNs: Long,
    val ax: Float = 0f,
    val ay: Float = 0f,
    val az: Float = 0f,
    val gx: Float = 0f,
    val gy: Float = 0f,
    val gz: Float = 0f,
    val hasGyro: Boolean = false,
    val rotationVector: FloatArray? = null
)
