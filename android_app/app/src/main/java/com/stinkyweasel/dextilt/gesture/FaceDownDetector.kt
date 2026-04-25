package com.stinkyweasel.dextilt.gesture

import kotlin.math.abs

class FaceDownDetector(
    private val stableWindowMs: Long = 500,
    private val maxTiltComponent: Float = 3.3f,
    private val faceDownZMax: Float = -7.8f
) {
    private var stableSinceNs: Long? = null

    fun update(sample: SensorSample): Boolean {
        val faceDown = sample.az < faceDownZMax && abs(sample.ax) < maxTiltComponent && abs(sample.ay) < maxTiltComponent
        if (!faceDown) {
            stableSinceNs = null
            return false
        }
        val since = stableSinceNs ?: sample.timestampNs.also { stableSinceNs = it }
        val stableMs = (sample.timestampNs - since) / 1_000_000L
        return stableMs >= stableWindowMs
    }

    fun reset() {
        stableSinceNs = null
    }
}
