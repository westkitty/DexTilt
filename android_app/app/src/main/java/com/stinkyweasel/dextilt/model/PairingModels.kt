package com.stinkyweasel.dextilt.model

import org.json.JSONObject

data class PairingPayload(
    val protocol: String,
    val host: String,
    val port: Int,
    val receiverId: String,
    val pairingToken: String,
    val expiresAtMs: Long
) {
    companion object {
        fun fromJson(raw: String): PairingPayload {
            val obj = JSONObject(raw.trim())
            return PairingPayload(
                protocol = obj.getString("protocol"),
                host = obj.getString("host"),
                port = obj.getInt("port"),
                receiverId = obj.getString("receiver_id"),
                pairingToken = obj.getString("pairing_token"),
                expiresAtMs = obj.getLong("expires_at_ms")
            )
        }
    }
}

data class PairingState(
    val host: String,
    val port: Int,
    val receiverId: String,
    val deviceId: String,
    val deviceName: String,
    val pairedAtMs: Long
) {
    fun baseUrl(): String = "http://$host:$port"
}

data class PairResponse(
    val ok: Boolean,
    val receiverId: String,
    val deviceId: String,
    val sharedSecret: String,
    val userMessage: String
)
