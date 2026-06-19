package com.example.smssync.network

import org.json.JSONObject

/**
 * JSON message protocol for Android <-> PC WebSocket communication.
 *
 * All messages are UTF-8 JSON with a required "type" field.
 */

/** Message types sent from Android to PC. */
object OutgoingMessage {
    const val PAIR = "pair"
    const val SMS_CODE = "sms_code"
    const val PONG = "pong"
    const val DISCONNECT = "disconnect"

    fun pair(token: String): String =
        JSONObject().apply {
            put("type", PAIR)
            put("token", token)
        }.toString()

    fun smsCode(code: String, sender: String, body: String, timestamp: Long): String =
        JSONObject().apply {
            put("type", SMS_CODE)
            put("code", code)
            put("sender", sender)
            put("body", body)
            put("timestamp", timestamp)
        }.toString()

    val pong: String
        get() = """{"type":"$PONG"}"""

    val disconnect: String
        get() = """{"type":"$DISCONNECT"}"""
}

/** Message types sent from PC to Android. */
object IncomingMessage {
    const val PAIRED = "paired"
    const val ACK = "ack"
    const val PING = "ping"

    fun parseStatus(raw: String): PairedStatus? {
        return try {
            val obj = JSONObject(raw)
            if (obj.getString("type") != PAIRED) return null
            PairedStatus(
                status = obj.getString("status"),
                reason = obj.optString("reason", ""),
                pcName = obj.optString("pc_name", ""),
            )
        } catch (_: Exception) {
            null
        }
    }

    fun parseAck(raw: String): AckResult? {
        return try {
            val obj = JSONObject(raw)
            if (obj.getString("type") != ACK) return null
            AckResult(
                code = obj.getString("code"),
                status = obj.getString("status"),
            )
        } catch (_: Exception) {
            null
        }
    }

    fun isPing(raw: String): Boolean {
        return try {
            val obj = JSONObject(raw)
            obj.getString("type") == PING
        } catch (_: Exception) {
            false
        }
    }
}

data class PairedStatus(
    val status: String,   // "ok" or "error"
    val reason: String = "",
    val pcName: String = "",
) {
    val isSuccess: Boolean get() = status == "ok"
}

data class AckResult(
    val code: String,
    val status: String,
)
