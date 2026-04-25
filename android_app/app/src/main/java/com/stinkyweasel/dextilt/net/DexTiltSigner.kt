package com.stinkyweasel.dextilt.net

import com.stinkyweasel.dextilt.model.CommandMessage
import org.json.JSONObject
import java.util.Base64
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

object DexTiltSigner {
    private val signingFields = listOf(
        "command_id",
        "confidence",
        "device_id",
        "gesture_id",
        "nonce",
        "protocol",
        "receiver_id",
        "timestamp_ms"
    )

    fun sign(message: CommandMessage, sharedSecretB64Url: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(b64UrlDecode(sharedSecretB64Url), "HmacSHA256"))
        return b64UrlEncode(mac.doFinal(canonical(message).toByteArray(Charsets.UTF_8)))
    }

    fun canonical(message: CommandMessage): String {
        val values = mapOf(
            "protocol" to JSONObject.quote(message.protocol),
            "device_id" to JSONObject.quote(message.deviceId),
            "receiver_id" to JSONObject.quote(message.receiverId),
            "command_id" to JSONObject.quote(message.commandId),
            "gesture_id" to JSONObject.quote(message.gestureId),
            "timestamp_ms" to message.timestampMs.toString(),
            "nonce" to JSONObject.quote(message.nonce),
            "confidence" to message.confidence.toString()
        )
        return signingFields.joinToString(prefix = "{", postfix = "}", separator = ",") { key ->
            JSONObject.quote(key) + ":" + values.getValue(key)
        }
    }

    private fun b64UrlDecode(value: String): ByteArray = Base64.getUrlDecoder().decode(value.padEnd(value.length + ((4 - value.length % 4) % 4), '='))
    private fun b64UrlEncode(bytes: ByteArray): String = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
}
