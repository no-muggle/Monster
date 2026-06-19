package com.example.smssync.data

/** Connection state for the UI. */
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
}

/** Parsed SMS message containing a verification code. */
data class SmsMessage(
    val code: String,
    val sender: String,
    val body: String,
    val timestamp: Long = System.currentTimeMillis(),
) {
    val shortSender: String
        get() = sender.take(20)
}

/** QR code pairing data decoded from the scanned QR. */
data class PairingInfo(
    val host: String,
    val port: Int,
    val token: String,
    val name: String = "",
) {
    val wsUrl: String
        get() = "ws://$host:$port"
}
