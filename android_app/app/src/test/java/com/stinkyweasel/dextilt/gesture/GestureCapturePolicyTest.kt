package com.stinkyweasel.dextilt.gesture

import org.junit.Assert.assertEquals
import org.junit.Test

class GestureCapturePolicyTest {
    private fun decide(durationMs: Long, stable: Boolean, heldMs: Long): GestureCaptureDecision {
        return GestureCapturePolicy.decide(
            durationMs = durationMs,
            faceDownStable = stable,
            stableEndHeldMs = heldMs,
            minDurationMs = 400L,
            maxDurationMs = 5000L,
            stableEndHoldMs = 600L
        )
    }

    @Test
    fun ordinaryCaptureContinuesBeforeTimeout() {
        assertEquals(GestureCaptureDecision.CONTINUE, decide(1200L, stable = false, heldMs = 0L))
    }

    @Test
    fun stableFaceDownEndCompletesCapture() {
        assertEquals(GestureCaptureDecision.COMPLETE, decide(1800L, stable = true, heldMs = 600L))
    }

    @Test
    fun timeoutWithoutStableFaceDownEndRejects() {
        assertEquals(GestureCaptureDecision.TIMEOUT_REJECT, decide(5000L, stable = false, heldMs = 0L))
    }

    @Test
    fun timeoutWithInsufficientStableHoldRejects() {
        assertEquals(GestureCaptureDecision.TIMEOUT_REJECT, decide(5000L, stable = true, heldMs = 599L))
    }

    @Test
    fun validStableEndAtDurationLimitStillCompletes() {
        assertEquals(GestureCaptureDecision.COMPLETE, decide(5000L, stable = true, heldMs = 600L))
    }
}
