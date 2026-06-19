package com.example.smssync.network

import android.util.Log
import com.example.smssync.data.ConnectionState
import com.example.smssync.data.PairingInfo
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.*
import java.util.concurrent.TimeUnit

/**
 * WebSocket client for communicating with the PC server.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Heartbeat ping/pong handling
 * - State flow for UI binding
 * - Coroutine-based message sending
 */
class WebSocketClient {

    companion object {
        private const val TAG = "WebSocketClient"
        private const val NORMAL_CLOSURE = 1000

        // Reconnection backoff parameters
        private val BACKOFF_INITIAL_MS = 1000L
        private val BACKOFF_MAX_MS = 30_000L
        private val BACKOFF_MULTIPLIER = 2.0
    }

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // no read timeout for WS
        .pingInterval(30, TimeUnit.SECONDS)     // OkHttp-level ping
        .build()

    private var webSocket: WebSocket? = null
    private var pairingInfo: PairingInfo? = null

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState

    private val _lastMessage = MutableStateFlow<String?>(null)
    val lastMessage: StateFlow<String?> = _lastMessage

    private val _lastError = MutableStateFlow<String?>(null)
    val lastError: StateFlow<String?> = _lastError

    /** Channel for queuing messages before the connection is ready. */
    private val sendChannel = Channel<String>(Channel.BUFFERED)

    private var scope: CoroutineScope? = null
    private var reconnectJob: Job? = null
    // Track connection attempt to ignore stale callbacks
    private var connectionId = 0

    /** Callback invoked when an SMS code should be sent to the PC. */
    var onSmsCodeToSend: ((code: String, sender: String, body: String?) -> Unit)? = null

    // --- Public API ---

    fun connectRelay(relayUrl: String, roomCode: String) {
        pairingInfo = PairingInfo(relayUrl, 0, "")  // dummy info
        val s = _connectionState.value
        if (s == ConnectionState.CONNECTED || s == ConnectionState.CONNECTING) return
        reconnectJob?.cancel(); reconnectJob = null
        scope?.cancel()
        scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        doConnectRelay(relayUrl, roomCode)
    }

    fun connect(info: PairingInfo) {
        val s = _connectionState.value
        Log.i(TAG, "connect() called, currentState=$s, host=${info.host}")
        if (s == ConnectionState.CONNECTED || s == ConnectionState.CONNECTING) {
            Log.d(TAG, "Already ${s}, skipping duplicate connect()")
            return
        }

        pairingInfo = info
        connectionId++  // invalidate stale callbacks
        reconnectJob?.cancel()
        reconnectJob = null
        scope?.cancel()
        scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        doConnect()
        scope?.launch {
            for (msg in sendChannel) {
                sendImmediate(msg)
            }
        }
    }

    fun disconnect() {
        Log.i(TAG, "disconnect() called, state=$_connectionState")
        reconnectJob?.cancel()
        reconnectJob = null
        pairingInfo = null
        webSocket?.close(NORMAL_CLOSURE, "User disconnect")
        webSocket = null
        scope?.cancel()
        scope = null
        _connectionState.value = ConnectionState.DISCONNECTED
    }

    fun sendCode(code: String, sender: String, body: String) {
        val msg = OutgoingMessage.smsCode(code, sender, body, System.currentTimeMillis())
        send(msg)
    }

    fun send(msg: String) {
        if (_connectionState.value == ConnectionState.CONNECTED) {
            sendImmediate(msg)
        } else {
            // Queue for later (non-blocking)
            sendChannel.trySend(msg)
        }
    }

    // --- Internal ---

    private fun doConnectRelay(relayUrl: String, roomCode: String) {
        val myId = ++connectionId
        Log.i(TAG, "doConnectRelay() id=$myId -> $relayUrl room=$roomCode")
        _connectionState.value = ConnectionState.CONNECTING

        val request = Request.Builder().url(relayUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            private fun isCurrent() = myId == connectionId
            override fun onOpen(ws: WebSocket, response: Response) {
                if (!isCurrent()) return
                // Send room join instead of pair
                ws.send("""{"type":"client","room":"$roomCode"}""")
            }
            override fun onMessage(ws: WebSocket, text: String) {
                if (!isCurrent()) return
                _lastMessage.value = text
                if (text.contains("\"type\":\"error\"")) {
                    _lastError.value = "房间不存在或已过期"
                    _connectionState.value = ConnectionState.DISCONNECTED
                    ws.close(1000, "room not found")
                    return
                }
                // Relay mode: first message means connected
                if (_connectionState.value == ConnectionState.CONNECTING) {
                    _connectionState.value = ConnectionState.CONNECTED
                }
                handleMessage(text)
            }
            override fun onClosing(ws: WebSocket, code: Int, reason: String) { ws.close(1000, null) }
            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                if (!isCurrent()) return
                Log.i(TAG, "Relay closed: $code $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
            }
            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                if (!isCurrent()) return
                Log.e(TAG, "Relay failure: ${t.message}")
                _lastError.value = "${t.javaClass.simpleName}: ${t.message}"
                _connectionState.value = ConnectionState.DISCONNECTED
            }
        })
    }

    private fun doConnect() {
        val info = pairingInfo ?: return
        val myId = ++connectionId
        Log.i(TAG, "doConnect() id=$myId -> ${info.wsUrl}")
        _connectionState.value = ConnectionState.CONNECTING

        val request = Request.Builder()
            .url(info.wsUrl)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            private fun isCurrent(): Boolean = myId == connectionId

            override fun onOpen(ws: WebSocket, response: Response) {
                if (!isCurrent()) return
                Log.i(TAG, "Connected to ${info.wsUrl}")
                ws.send(OutgoingMessage.pair(info.token))
            }

            override fun onMessage(ws: WebSocket, text: String) {
                if (!isCurrent()) return
                Log.d(TAG, "Received: $text")
                _lastMessage.value = text
                handleMessage(text)
            }

            override fun onClosing(ws: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "Closing: $code $reason")
                ws.close(NORMAL_CLOSURE, null)
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "Closed: $code $reason (id=$myId, current=$connectionId)")
                if (!isCurrent()) return
                _connectionState.value = ConnectionState.DISCONNECTED
                scheduleReconnect()
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                val errorMsg = "${t.javaClass.simpleName}: ${t.message}"
                Log.e(TAG, "Connection failure: $errorMsg (id=$myId, current=$connectionId)")
                if (!isCurrent()) return
                _lastError.value = errorMsg
                _connectionState.value = ConnectionState.DISCONNECTED
                scheduleReconnect()
            }
        })
    }

    private fun handleMessage(text: String) {
        // Handle pairing response
        val pairedStatus = IncomingMessage.parseStatus(text)
        if (pairedStatus != null) {
            if (pairedStatus.isSuccess) {
                Log.i(TAG, "Paired with PC: ${pairedStatus.pcName}")
                _connectionState.value = ConnectionState.CONNECTED
                scope?.launch {
                    while (!sendChannel.isEmpty) {
                        val msg = sendChannel.receive()
                        sendImmediate(msg)
                    }
                }
            } else {
                Log.w(TAG, "Pairing failed: ${pairedStatus.reason}")
                _connectionState.value = ConnectionState.DISCONNECTED
                _lastError.value = "配对失败: ${pairedStatus.reason}，请重新扫码"
                // If token is invalid, stop reconnecting — user needs to re-scan
                if (pairedStatus.reason == "invalid_token") {
                    pairingInfo = null
                    reconnectJob?.cancel()
                }
            }
            return
        }

        // Handle ping
        if (IncomingMessage.isPing(text)) {
            webSocket?.send(OutgoingMessage.pong)
            return
        }

        // Handle ack
        val ack = IncomingMessage.parseAck(text)
        if (ack != null) {
            Log.d(TAG, "Code ${ack.code} acknowledged: ${ack.status}")
        }
    }

    private fun sendImmediate(msg: String) {
        val ws = webSocket
        if (ws != null) {
            val sent = ws.send(msg)
            if (!sent) {
                Log.w(TAG, "Failed to send message, queuing")
                sendChannel.trySend(msg)
            }
        } else {
            sendChannel.trySend(msg)
        }
    }

    private fun scheduleReconnect() {
        val info = pairingInfo
        Log.i(TAG, "scheduleReconnect() info=$info state=$_connectionState")
        if (info == null) {
            Log.d(TAG, "No pairing info, skipping reconnect")
            return
        }
        val s = _connectionState.value
        if (s == ConnectionState.CONNECTED) {
            Log.d(TAG, "Already connected, skipping reconnect")
            return
        }
        reconnectJob?.cancel()
        reconnectJob = scope?.launch {
            var delay = BACKOFF_INITIAL_MS
            while (isActive) {
                _connectionState.value = ConnectionState.RECONNECTING
                Log.i(TAG, "Reconnecting in ${delay}ms...")
                delay(delay)
                doConnect()
                // Wait a bit to see if connection succeeds
                delay(3000)
                if (_connectionState.value == ConnectionState.CONNECTED) break
                delay = (delay * BACKOFF_MULTIPLIER).toLong().coerceAtMost(BACKOFF_MAX_MS)
            }
        }
    }
}
