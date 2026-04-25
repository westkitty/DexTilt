package com.stinkyweasel.dextilt.gesture

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class GestureMatcherTest {
    private fun samples(rotationScale: Float = 1f, count: Int = 60): List<SensorSample> {
        val start = 1_000_000_000L
        return (0 until count).map { i ->
            SensorSample(
                timestampNs = start + i * 20_000_000L,
                ax = 0.4f,
                ay = 0.3f,
                az = -9.4f,
                gx = 0.0f,
                gy = 1.0f * rotationScale,
                gz = 0.1f,
                hasGyro = true
            )
        }
    }

    private fun template(): GestureTemplate {
        val source = samples()
        return GestureTemplate(
            gestureId = "primary_open_gpt",
            name = "Open GPT Gesture",
            createdAt = "2026-01-01T00:00:00Z",
            sampleRateHz = 50,
            durationMs = (source.last().timestampNs - source.first().timestampNs) / 1_000_000L,
            sensorSources = listOf("accelerometer", "gyroscope"),
            features = GestureFeatureExtractor.extract(source, 500),
            tolerance = "normal"
        )
    }

    @Test fun highConfidenceMatchTriggers() {
        val match = GestureMatcher().match(template(), samples(), faceDownStable = true)
        assertTrue(match.confidence >= 85)
        assertTrue(match.shouldTrigger)
    }

    @Test fun wrongStartPostureDoesNotTrigger() {
        val match = GestureMatcher().match(template(), samples(), faceDownStable = false)
        assertFalse(match.shouldTrigger)
        assertFalse(match.requiresConfirmation)
    }

    @Test fun lowConfidenceUnknownDoesNotTrigger() {
        val match = GestureMatcher().match(template(), samples(rotationScale = -1.2f), faceDownStable = true)
        assertFalse(match.shouldTrigger)
    }
}
