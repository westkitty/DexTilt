package com.stinkyweasel.dextilt.net

import com.stinkyweasel.dextilt.model.CommandMessage
import com.stinkyweasel.dextilt.model.CommandResult
import com.stinkyweasel.dextilt.model.PairResponse
import com.stinkyweasel.dextilt.model.PairingPayload
import com.stinkyweasel.dextilt.model.PairingState
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import java.util.Base64

class DexTiltClient(private val timeoutMs: Int = 3000) {
    fun health(baseUrl: String): String {
        val response = request("GET", "$baseUrl/health")
        if (response.code !in 200..299) return "DexTilt Mac health check failed. HTTP ${response.code}: ${response.body}"
        val obj = JSONObject(response.body)
        return "Receiver OK. Protocol ${obj.optString("protocol")}. Paired devices: ${obj.optInt("paired_device_count")}."
    }

    fun pair(payload: PairingPayload, deviceId: String, deviceName: String): PairResponse {
        val body = JSONObject()
            .put("protocol", "dextilt.pairing.v1")
            .put("receiver_id", payload.receiverId)
            .put("pairing_token", payload.pairingToken)
            .put("device_id", deviceId)
            .put("device_name", deviceName)
        val response = request("POST", "http://${payload.host}:${payload.port}/pair", body.toString())
        if (response.code !in 200..299) {
            val result = ProtocolJson.commandResult(response.body, response.code)
            throw IllegalStateException(result.userMessage)
        }
        return ProtocolJson.pairResponse(response.body)
    }

    fun sendCommand(pairing: PairingState, sharedSecret: String, commandId: String, gestureId: String, confidence: Int): CommandResult {
        val unsigned = CommandMessage(
            deviceId = pairing.deviceId,
            receiverId = pairing.receiverId,
            commandId = commandId,
            gestureId = gestureId,
            timestampMs = System.currentTimeMillis(),
            nonce = nonce(),
            confidence = confidence.coerceIn(0, 100)
        )
        val signed = unsigned.copy(signature = DexTiltSigner.sign(unsigned, sharedSecret))
        val response = request("POST", "${pairing.baseUrl()}/command", ProtocolJson.commandJson(signed).toString())
        return ProtocolJson.commandResult(response.body, response.code)
    }

    fun sendCalibration(pairing: PairingState, sharedSecret: String, stepId: String, stepLabel: String, status: String, detail: String): CommandResult {
        val unsigned = CommandMessage(
            deviceId = pairing.deviceId,
            receiverId = pairing.receiverId,
            commandId = "calibration_update",
            gestureId = "calibration",
            timestampMs = System.currentTimeMillis(),
            nonce = nonce(),
            confidence = 100
        )
        val signed = unsigned.copy(signature = DexTiltSigner.sign(unsigned, sharedSecret))
        val body = ProtocolJson.commandJson(signed)
            .put("step_id", stepId)
            .put("step_label", stepLabel)
            .put("status", status)
            .put("detail", detail.take(500))
        val response = request("POST", "${pairing.baseUrl()}/calibration", body.toString())
        return ProtocolJson.commandResult(response.body, response.code)
    }

    private fun request(method: String, url: String, body: String? = null): HttpResponse {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            setRequestProperty("Accept", "application/json")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
            }
        }
        if (body != null) conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
        val stream = if (conn.responseCode in 200..299) conn.inputStream else conn.errorStream
        val text = stream?.use { BufferedReader(InputStreamReader(it)).readText() }.orEmpty()
        return HttpResponse(conn.responseCode, text)
    }

    private fun nonce(): String {
        val bytes = ByteArray(24)
        SecureRandom().nextBytes(bytes)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }

    private data class HttpResponse(val code: Int, val body: String)
}
