package com.stinkyweasel.dextilt.gesture

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs

data class GestureFeatures(
    val rotationTotalX: Float = 0f,
    val rotationTotalY: Float = 0f,
    val rotationTotalZ: Float = 0f,
    val accelerationPeak: Float = 0f,
    val accelerationMean: Float = 0f,
    val stableStartMs: Long = 0,
    val majorAxis: String = "unknown"
) {
    fun toJson(): JSONObject = JSONObject()
        .put("rotation_total_x", rotationTotalX.toDouble())
        .put("rotation_total_y", rotationTotalY.toDouble())
        .put("rotation_total_z", rotationTotalZ.toDouble())
        .put("acceleration_peak", accelerationPeak.toDouble())
        .put("acceleration_mean", accelerationMean.toDouble())
        .put("stable_start_ms", stableStartMs)
        .put("major_axis", majorAxis)
        .put("orientation_delta", JSONObject())
        .put("acceleration_summary", JSONObject().put("peak", accelerationPeak.toDouble()).put("mean", accelerationMean.toDouble()))
        .put("stability_summary", JSONObject().put("stable_start_ms", stableStartMs))

    companion object {
        fun fromJson(obj: JSONObject): GestureFeatures = GestureFeatures(
            rotationTotalX = obj.optDouble("rotation_total_x", 0.0).toFloat(),
            rotationTotalY = obj.optDouble("rotation_total_y", 0.0).toFloat(),
            rotationTotalZ = obj.optDouble("rotation_total_z", 0.0).toFloat(),
            accelerationPeak = obj.optDouble("acceleration_peak", 0.0).toFloat(),
            accelerationMean = obj.optDouble("acceleration_mean", 0.0).toFloat(),
            stableStartMs = obj.optLong("stable_start_ms", 0),
            majorAxis = obj.optString("major_axis", "unknown")
        )
    }
}

data class GestureTemplate(
    val schemaVersion: String = "dextilt.gesture.v1",
    val gestureId: String,
    val name: String,
    val createdAt: String,
    val sampleRateHz: Int,
    val durationMs: Long,
    val startPosture: String = "face_down",
    val sensorSources: List<String>,
    val features: GestureFeatures,
    val tolerance: String = "normal"
) {
    fun toJsonString(): String {
        val sources = JSONArray()
        sensorSources.forEach { sources.put(it) }
        return JSONObject()
            .put("schema_version", schemaVersion)
            .put("gesture_id", gestureId)
            .put("name", name)
            .put("created_at", createdAt)
            .put("sample_rate_hz", sampleRateHz)
            .put("duration_ms", durationMs)
            .put("start_posture", startPosture)
            .put("sensor_sources", sources)
            .put("features", features.toJson())
            .put("tolerance", tolerance)
            .toString()
    }

    companion object {
        fun fromJsonString(raw: String): GestureTemplate {
            val obj = JSONObject(raw)
            val schema = obj.getString("schema_version")
            require(schema == "dextilt.gesture.v1") { "Unsupported gesture schema: $schema. Retrain this gesture." }
            val sourcesJson = obj.optJSONArray("sensor_sources") ?: JSONArray()
            val sources = buildList {
                for (i in 0 until sourcesJson.length()) add(sourcesJson.getString(i))
            }
            return GestureTemplate(
                schemaVersion = schema,
                gestureId = obj.getString("gesture_id"),
                name = obj.getString("name"),
                createdAt = obj.getString("created_at"),
                sampleRateHz = obj.optInt("sample_rate_hz", 50),
                durationMs = obj.optLong("duration_ms", 0),
                startPosture = obj.optString("start_posture", "face_down"),
                sensorSources = sources,
                features = GestureFeatures.fromJson(obj.getJSONObject("features")),
                tolerance = obj.optString("tolerance", "normal")
            )
        }
    }
}

data class GestureMatch(val confidence: Int, val label: String, val shouldTrigger: Boolean, val requiresConfirmation: Boolean)

object GestureFeatureExtractor {
    fun extract(samples: List<SensorSample>, stableStartMs: Long = 0): GestureFeatures {
        if (samples.size < 2) return GestureFeatures(stableStartMs = stableStartMs)
        var rx = 0f
        var ry = 0f
        var rz = 0f
        var accSum = 0f
        var accPeak = 0f
        var last = samples.first()
        samples.drop(1).forEach { sample ->
            val dt = ((sample.timestampNs - last.timestampNs).coerceAtLeast(0L) / 1_000_000_000f).coerceIn(0f, 0.2f)
            if (sample.hasGyro) {
                rx += sample.gx * dt
                ry += sample.gy * dt
                rz += sample.gz * dt
            }
            val centered = kotlin.math.sqrt(sample.ax * sample.ax + sample.ay * sample.ay + sample.az * sample.az)
            accSum += centered
            if (centered > accPeak) accPeak = centered
            last = sample
        }
        val absX = abs(rx)
        val absY = abs(ry)
        val absZ = abs(rz)
        val major = when {
            absX >= absY && absX >= absZ -> "x"
            absY >= absX && absY >= absZ -> "y"
            absZ >= absX && absZ >= absY -> "z"
            else -> "unknown"
        }
        return GestureFeatures(
            rotationTotalX = rx,
            rotationTotalY = ry,
            rotationTotalZ = rz,
            accelerationPeak = accPeak,
            accelerationMean = accSum / (samples.size - 1).coerceAtLeast(1),
            stableStartMs = stableStartMs,
            majorAxis = major
        )
    }
}
