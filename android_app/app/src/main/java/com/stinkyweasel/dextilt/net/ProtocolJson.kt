package com.stinkyweasel.dextilt.net

import com.stinkyweasel.dextilt.model.CommandMessage
import com.stinkyweasel.dextilt.model.CommandResult
import com.stinkyweasel.dextilt.model.PairResponse
import org.json.JSONObject

object ProtocolJson {
    fun commandJson(message: CommandMessage): JSONObject = JSONObject()
        .put("protocol", message.protocol)
        .put("device_id", message.deviceId)
        .put("receiver_id", message.receiverId)
        .put("command_id", message.commandId)
        .put("gesture_id", message.gestureId)
        .put("timestamp_ms", message.timestampMs)
        .put("nonce", message.nonce)
        .put("confidence", message.confidence)
        .put("signature", message.signature)

    fun pairResponse(raw: String): PairResponse {
        val obj = JSONObject(raw)
        return PairResponse(
            ok = obj.optBoolean("ok", false),
            receiverId = obj.optString("receiver_id"),
            deviceId = obj.optString("device_id"),
            sharedSecret = obj.optString("shared_secret"),
            userMessage = obj.optString("user_message", "Pairing response received.")
        )
    }

    fun commandResult(raw: String, httpCode: Int): CommandResult {
        val obj = runCatching { JSONObject(raw) }.getOrNull()
        if (obj == null) {
            return CommandResult(false, false, "DexTilt could not read the Mac response. HTTP $httpCode", "bad_response")
        }
        val ok = obj.optBoolean("ok", httpCode in 200..299)
        return CommandResult(
            ok = ok,
            accepted = obj.optBoolean("accepted", ok),
            userMessage = obj.optString("user_message", obj.optString("detail", "DexTilt response HTTP $httpCode")),
            errorCode = obj.optString("error_code").takeIf { it.isNotBlank() }
        )
    }
}
