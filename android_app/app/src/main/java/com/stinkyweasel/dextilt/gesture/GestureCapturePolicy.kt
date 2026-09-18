package com.stinkyweasel.dextilt.gesture

enum class GestureCaptureDecision {
    CONTINUE,
    COMPLETE,
    TIMEOUT_REJECT
}

object GestureCapturePolicy {
    fun decide(
        durationMs: Long,
        faceDownStable: Boolean,
        stableEndHeldMs: Long,
        minDurationMs: Long,
        maxDurationMs: Long,
        stableEndHoldMs: Long
    ): GestureCaptureDecision {
        require(minDurationMs >= 0L)
        require(maxDurationMs > minDurationMs)
        require(stableEndHoldMs >= 0L)

        val stableEndComplete = faceDownStable &&
            durationMs >= minDurationMs &&
            stableEndHeldMs >= stableEndHoldMs

        return when {
            stableEndComplete -> GestureCaptureDecision.COMPLETE
            durationMs >= maxDurationMs -> GestureCaptureDecision.TIMEOUT_REJECT
            else -> GestureCaptureDecision.CONTINUE
        }
    }
}
