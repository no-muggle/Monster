package com.example.smssync.service

import android.Manifest
import android.app.*
import android.app.AppOpsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.example.smssync.data.ConnectionState
import com.example.smssync.data.ConnectionStateHolder
import com.example.smssync.data.PairingInfo
import com.example.smssync.data.PreferencesManager
import com.example.smssync.network.WebSocketClient
import com.example.smssync.sms.SmsObserver
import kotlinx.coroutines.*
import kotlinx.coroutines.Dispatchers

/**
 * Foreground service that maintains the WebSocket connection to the PC
 * and listens for SMS messages via the User Consent API (no SMS permission needed).
 */
class WebSocketService : Service() {

    companion object {
        private const val TAG = "WebSocketService"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "sms_sync_channel"

        // Intent actions
        const val ACTION_SMS_RECEIVED = "com.example.smssync.SMS_RECEIVED"   // deprecated
        const val ACTION_CODE_EXTRACTED = "com.example.smssync.CODE_EXTRACTED" // from consent activity
        const val ACTION_CONNECT = "com.example.smssync.CONNECT"
        const val ACTION_RELAY_CONNECT = "com.example.smssync.RELAY_CONNECT"
        const val ACTION_DISCONNECT = "com.example.smssync.DISCONNECT"
        const val ACTION_STOP = "com.example.smssync.STOP"

        // Intent extras
        const val EXTRA_CODE = "code"
        const val EXTRA_SENDER = "sender"
        const val EXTRA_BODY = "body"
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_RELAY_URL = "relay_url"
        const val EXTRA_ROOM_CODE = "room_code"
    }

    private lateinit var webSocketClient: WebSocketClient
    private lateinit var preferencesManager: PreferencesManager
    private var serviceScope: CoroutineScope? = null
    private var connectionJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Service created")
        webSocketClient = WebSocketClient()
        preferencesManager = PreferencesManager(this)
        createNotificationChannel()

        // Smart SMS mode: use RECEIVE_SMS if granted (seamless),
        // otherwise fall back to SMS Consent API (requires tap per message)
        // Primary: SMS Consent API (works on all devices incl Xiaomi)
        // Secondary: Notification listener (if user enables in system settings)
        // RECEIVE_SMS + Accessibility handle everything — no consent API needed
        if (hasSmsPermission()) {
            Log.i(TAG, "RECEIVE_SMS granted — seamless SMS via broadcast")
        }

        // ContentObserver as backup (needs READ_SMS permission)
        if (hasReadSmsPermission()) {
            Log.i(TAG, "READ_SMS granted — ContentObserver active")
            contentResolver.registerContentObserver(
                android.net.Uri.parse("content://sms/inbox"),
                true,
                SmsObserver(this),
            )
        }

        // Observe connection state for notification updates
        serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        connectionJob = serviceScope?.launch {
            webSocketClient.connectionState.collect { state ->
                Log.i(TAG, "State changed: $state")
                ConnectionStateHolder.updateState(state)
                val text = when (state) {
                    ConnectionState.CONNECTED -> "已连接 — 等待验证码..."
                    ConnectionState.CONNECTING -> "连接中..."
                    ConnectionState.RECONNECTING -> "重连中..."
                    ConnectionState.DISCONNECTED -> {
                        // Relay room codes are single-use — clear on disconnect
                        preferencesManager.clearIfRelay()
                        "未连接 — 请扫码配对"
                    }
                }
                updateNotification(text)
            }
            // Watchdog: check accessibility status every 5 minutes
            launch {
                while (isActive) {
                    delay(5 * 60 * 1000L)
                    if (!isAccessibilityEnabled()) {
                        Log.w(TAG, "Accessibility service was disabled!")
                        updateNotification("⚠️ 无障碍已关闭，验证码可能无法同步")
                    }
                }
            }
        }
    }

    private fun isAccessibilityEnabled(): Boolean {
        return try {
            val enabled = android.provider.Settings.Secure.getString(
                contentResolver,
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            )
            enabled?.contains("SmsAccessibilityService") == true
        } catch (_: Exception) { false }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> handleConnect(intent)
            ACTION_RELAY_CONNECT -> handleRelayConnect(intent)
            ACTION_DISCONNECT -> handleDisconnect()
            ACTION_CODE_EXTRACTED -> handleCodeExtracted(intent)
            ACTION_STOP -> handleStop()
            else -> {
                // Service started without action — auto-reconnect using saved pairing
                serviceScope?.launch(Dispatchers.IO) {
                    preferencesManager.savedPairing.collect { saved ->
                        if (!saved.isComplete || !saved.autoConnect) return@collect
                        cancel() // only try once

                        if (saved.isRelay) {
                            Log.i(TAG, "Auto-reconnecting via relay: ${saved.relayUrl} room=${saved.roomCode}")
                            webSocketClient.connectRelay(saved.relayUrl, saved.roomCode)
                        } else {
                            val info = saved.toPairingInfo() ?: return@collect
                            Log.i(TAG, "Auto-reconnecting to ${info.wsUrl}")
                            webSocketClient.connect(info)
                        }
                    }
                }
            }
        }

        val notification = buildNotification("SMS Sync 运行中")
        startForeground(NOTIFICATION_ID, notification)

        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        Log.i(TAG, "Service destroyed")
        connectionJob?.cancel()
        serviceScope?.cancel()
        webSocketClient.disconnect()
        super.onDestroy()
    }

    private fun handleConnect(intent: Intent) {
        val host = intent.getStringExtra(EXTRA_HOST) ?: return
        val port = intent.getIntExtra(EXTRA_PORT, 9876)
        val token = intent.getStringExtra(EXTRA_TOKEN) ?: return

        val info = PairingInfo(host, port, token)

        val currentState = webSocketClient.connectionState.value
        if (currentState == ConnectionState.CONNECTED) {
            Log.d(TAG, "Already connected, skipping reconnect")
            return
        }

        // Force-reset before connecting fresh
        webSocketClient.disconnect()
        webSocketClient.connect(info)

        serviceScope?.launch(Dispatchers.IO) {
            preferencesManager.savePairing(info)
        }

        // Poll for connection success and push to UI
        ConnectionStateHolder.updateState(ConnectionState.CONNECTING)
        serviceScope?.launch {
            var tries = 0
            while (tries < 15) {
                delay(500)
                tries++
                val s = webSocketClient.connectionState.value
                if (s == ConnectionState.CONNECTED) {
                    ConnectionStateHolder.updateState(ConnectionState.CONNECTED)
                    updateNotification("已连接 — 等待验证码...")
                    return@launch
                }
                if (s == ConnectionState.DISCONNECTED) {
                    ConnectionStateHolder.updateState(ConnectionState.DISCONNECTED)
                    return@launch
                }
            }
        }
    }

    private fun handleRelayConnect(intent: Intent) {
        val relayUrl = intent.getStringExtra(EXTRA_RELAY_URL) ?: return
        val roomCode = intent.getStringExtra(EXTRA_ROOM_CODE) ?: return
        webSocketClient.disconnect()
        webSocketClient.connectRelay(relayUrl, roomCode)
        ConnectionStateHolder.updateState(ConnectionState.CONNECTING)
        updateNotification("连接云服务器...")

        // Persist relay pairing for auto-reconnect
        serviceScope?.launch(Dispatchers.IO) {
            preferencesManager.saveRelayPairing(relayUrl, roomCode)
        }
    }

    private fun handleDisconnect() {
        webSocketClient.disconnect()
        updateNotification("已断开连接")
    }

    private var lastExtractedCode = ""
    private var lastExtractedTime = 0L

    private fun handleCodeExtracted(intent: Intent) {
        val code = intent.getStringExtra(EXTRA_CODE) ?: return
        val sender = intent.getStringExtra(EXTRA_SENDER) ?: "SMS"
        val body = intent.getStringExtra(EXTRA_BODY) ?: ""

        // Dedup: skip same code within 2 seconds (prevents loop, allows resend)
        val now = System.currentTimeMillis()
        if (code == lastExtractedCode && now - lastExtractedTime < 2000) {
            Log.d(TAG, "Dedup: skipping duplicate $code")
            return
        }
        lastExtractedCode = code
        lastExtractedTime = now

        Log.i(TAG, "Code extracted: $code from $sender")

        // Add to history only if new (prevent duplicates on re-send)
        if (ConnectionStateHolder.history.value.none { it.code == code }) {
            ConnectionStateHolder.updateCode(code, sender)
        }

        if (webSocketClient.connectionState.value == ConnectionState.CONNECTED) {
            webSocketClient.sendCode(code, sender, body)
            updateNotification("验证码已同步: $code")
        } else {
            Log.w(TAG, "Not connected, code not forwarded")
            // Show code locally so user can still use it
            showCodeNotification(code)
        }
    }

    private fun handleStop() {
        webSocketClient.disconnect()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun hasSmsPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            checkSelfPermission(Manifest.permission.RECEIVE_SMS) ==
                PackageManager.PERMISSION_GRANTED
        } else true
    }

    private fun hasReadSmsPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            checkSelfPermission(Manifest.permission.READ_SMS) ==
                PackageManager.PERMISSION_GRANTED
        } else true
    }

    // --- Notifications ---

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "SMS Sync 服务",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "保持与PC的连接以同步验证码"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("SMS Sync")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(text: String) {
        val notification = buildNotification(text)
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun showCodeNotification(code: String) {
        // Show a separate notification for the code (not the persistent one)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "sms_codes",
                "验证码",
                NotificationManager.IMPORTANCE_HIGH,
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, "sms_codes")
            .setContentTitle("收到验证码")
            .setContentText("验证码: $code (PC未连接)")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(2001, notification)
    }
}
