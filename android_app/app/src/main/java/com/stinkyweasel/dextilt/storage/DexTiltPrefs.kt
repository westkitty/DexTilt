package com.stinkyweasel.dextilt.storage

import android.content.Context
import com.stinkyweasel.dextilt.model.PairingState
import java.util.UUID

class DexTiltPrefs(context: Context) {
    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences("dextilt_prefs", Context.MODE_PRIVATE)
    private val secure = SecurePrefs(appContext)

    fun getOrCreateDeviceId(): String {
        val existing = prefs.getString("device_id", null)
        if (!existing.isNullOrBlank()) return existing
        val created = "android_" + UUID.randomUUID().toString()
        prefs.edit().putString("device_id", created).apply()
        return created
    }

    fun deviceName(): String = android.os.Build.MODEL?.takeIf { it.isNotBlank() } ?: "Android DexTilt"

    fun savePairing(state: PairingState, sharedSecret: String) {
        prefs.edit()
            .putString("host", state.host)
            .putInt("port", state.port)
            .putString("receiver_id", state.receiverId)
            .putString("device_id", state.deviceId)
            .putString("device_name", state.deviceName)
            .putLong("paired_at_ms", state.pairedAtMs)
            .apply()
        secure.putSecret("shared_secret", sharedSecret)
    }

    fun pairingState(): PairingState? {
        val host = prefs.getString("host", null) ?: return null
        val receiverId = prefs.getString("receiver_id", null) ?: return null
        val deviceId = prefs.getString("device_id", null) ?: return null
        val deviceName = prefs.getString("device_name", "Android DexTilt") ?: "Android DexTilt"
        val port = prefs.getInt("port", 47391)
        val pairedAt = prefs.getLong("paired_at_ms", 0L)
        return PairingState(host, port, receiverId, deviceId, deviceName, pairedAt)
    }

    fun sharedSecret(): String? = secure.getSecret("shared_secret")

    fun resetPairing() {
        val deviceId = getOrCreateDeviceId()
        prefs.edit().clear().putString("device_id", deviceId).apply()
        secure.clear()
    }
}
