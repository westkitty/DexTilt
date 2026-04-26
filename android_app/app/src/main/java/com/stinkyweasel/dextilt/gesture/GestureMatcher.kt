package com.stinkyweasel.dextilt.gesture

import kotlin.math.abs
import kotlin.math.max

class GestureMatcher(
    private val highThreshold: Int = 70,
    private val mediumThreshold: Int = 55
) {
    fun match(template: GestureTemplate, samples: List<SensorSample>, faceDownStable: Boolean): GestureMatch {
        if (!faceDownStable || template.startPosture != "face_down") {
            return GestureMatch(0, "Wrong start posture", shouldTrigger = false, requiresConfirmation = false)
        }
        if (samples.size < 8) {
            return GestureMatch(0, "Too few samples", shouldTrigger = false, requiresConfirmation = false)
        }
        val durationMs = ((samples.last().timestampNs - samples.first().timestampNs) / 1_000_000L).coerceAtLeast(0)
        if (durationMs < 300) return GestureMatch(20, "Too short", false, false)
        if (durationMs > 3500) return GestureMatch(20, "Too long", false, false)

        val candidate = GestureFeatureExtractor.extract(samples)
        val toleranceMultiplier = when (template.tolerance) {
            "strict" -> 0.75f
            "relaxed" -> 1.35f
            else -> 1.0f
        }
        var score = 100f
        score -= normalizedPenalty(abs(durationMs - template.durationMs).toFloat(), 900f * toleranceMultiplier, 30f)
        score -= normalizedPenalty(abs(candidate.rotationTotalX - template.features.rotationTotalX), 1.4f * toleranceMultiplier, 18f)
        score -= normalizedPenalty(abs(candidate.rotationTotalY - template.features.rotationTotalY), 1.4f * toleranceMultiplier, 18f)
        score -= normalizedPenalty(abs(candidate.rotationTotalZ - template.features.rotationTotalZ), 1.4f * toleranceMultiplier, 18f)
        if (candidate.majorAxis != template.features.majorAxis) score -= 12f
        score -= normalizedPenalty(abs(candidate.accelerationPeak - template.features.accelerationPeak), 8f * toleranceMultiplier, 10f)
        val confidence = score.toInt().coerceIn(0, 100)
        return when {
            confidence >= highThreshold -> GestureMatch(confidence, "High confidence", shouldTrigger = true, requiresConfirmation = false)
            confidence >= mediumThreshold -> GestureMatch(confidence, "Medium confidence", shouldTrigger = false, requiresConfirmation = true)
            else -> GestureMatch(confidence, "Unknown gesture", shouldTrigger = false, requiresConfirmation = false)
        }
    }

    private fun normalizedPenalty(delta: Float, allowed: Float, maxPenalty: Float): Float {
        if (allowed <= 0f) return maxPenalty
        return max(0f, delta / allowed).coerceAtMost(1.5f) / 1.5f * maxPenalty
    }
}
