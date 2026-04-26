package com.stinkyweasel.dextilt.gesture

import android.content.Context
import java.time.Instant

class GestureTemplateStore(context: Context) {
    private val prefs = context.getSharedPreferences("dextilt_gestures", Context.MODE_PRIVATE)

    fun save(template: GestureTemplate) {
        prefs.edit().putString("gesture_${template.gestureId}", template.toJsonString()).putString("active_gesture_id", template.gestureId).apply()
    }

    fun active(): GestureTemplate? {
        val id = prefs.getString("active_gesture_id", null) ?: return null
        val raw = prefs.getString("gesture_$id", null) ?: return null
        return runCatching { GestureTemplate.fromJsonString(raw) }.getOrNull()
    }

    fun deleteAll() {
        prefs.edit().clear().apply()
    }

    fun buildTemplate(name: String, samples: List<SensorSample>, sensorSources: List<String>, tolerance: String): GestureTemplate {
        val id = "primary_dexdictate_toggle"
        val durationMs = if (samples.size >= 2) (samples.last().timestampNs - samples.first().timestampNs) / 1_000_000L else 0L
        return GestureTemplate(
            gestureId = id,
            name = name.ifBlank { "DexDictate Toggle Gesture" },
            createdAt = Instant.now().toString(),
            sampleRateHz = 50,
            durationMs = durationMs,
            startPosture = "face_down",
            sensorSources = sensorSources,
            features = GestureFeatureExtractor.extract(samples, stableStartMs = 500),
            tolerance = tolerance
        )
    }
}
