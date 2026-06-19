package com.example.smssync

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.*
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.example.smssync.data.ConnectionState
import kotlinx.coroutines.launch
import com.example.smssync.data.ConnectionStateHolder
import com.example.smssync.data.PairingInfo
import com.example.smssync.data.PreferencesManager
import com.example.smssync.service.WebSocketService
import com.example.smssync.ui.MainScreen
import com.example.smssync.ui.QrScannerScreen
import com.example.smssync.ui.RelayConnectScreen
import com.example.smssync.ui.theme.SmsSyncTheme

/**
 * Main (and only) Activity for the SMS Sync app.
 *
 * Manages navigation between the main status screen and the
 * QR scanner screen. Starts the background WebSocket service.
 */
class MainActivity : ComponentActivity() {

    // Navigation + theme
    private var showScanner by mutableStateOf(false)
    private var showRelay by mutableStateOf(false)
    private var isDarkTheme by mutableStateOf(false)
    private val preferencesManager by lazy { PreferencesManager(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Init history persistence
        ConnectionStateHolder.init(this)

        // Load saved theme
        lifecycleScope.launch {
            preferencesManager.savedPairing.collect { saved ->
                isDarkTheme = saved.darkTheme
            }
        }

        // Auto-start the background service (keeps WebSocket + SMS listener alive)
        val serviceIntent = Intent(this, WebSocketService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent)
        } else {
            startService(serviceIntent)
        }

        // Request SMS permission for seamless background receiving
        requestSmsPermission()
        // Request notification permission (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestNotificationPermission()
        }

        setContent {
            SmsSyncTheme(darkTheme = isDarkTheme) {
                val connState by ConnectionStateHolder.state.collectAsState()
                val code by ConnectionStateHolder.lastCode.collectAsState()
                val sender by ConnectionStateHolder.lastSender.collectAsState()

                if (showScanner) {
                    QrScannerScreen(
                        onQrScanned = { info -> onQrScanned(info) },
                        onBack = { showScanner = false },
                    )
                } else if (showRelay) {
                    RelayConnectScreen(
                        connectionState = connState,
                        onConnect = { url, code -> onRelayConnect(url, code) },
                        onBack = { showRelay = false },
                    )
                } else {
                    MainScreen(
                        connectionState = connState,
                        lastCode = code,
                        lastSender = sender,
                        isDarkTheme = isDarkTheme,
                        onScanQrClick = { showScanner = true },
                        onRelayClick = { showRelay = true },
                        onDisconnectClick = { disconnectFromPc() },
                        onToggleTheme = {
                            isDarkTheme = !isDarkTheme
                            lifecycleScope.launch { preferencesManager.setDarkTheme(isDarkTheme) }
                        },
                    )
                }
            }
        }
    }

    private fun onQrScanned(info: PairingInfo) {
        Log.i(TAG, "QR scanned: ${info.wsUrl}")

        // Connect to PC via WebSocketService
        val intent = Intent(this, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_CONNECT
            putExtra(WebSocketService.EXTRA_HOST, info.host)
            putExtra(WebSocketService.EXTRA_PORT, info.port)
            putExtra(WebSocketService.EXTRA_TOKEN, info.token)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        ConnectionStateHolder.updateState(ConnectionState.CONNECTING)
        showScanner = false
    }

    private fun onRelayConnect(relayUrl: String, roomCode: String) {
        val intent = Intent(this, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_RELAY_CONNECT
            putExtra(WebSocketService.EXTRA_RELAY_URL, relayUrl)
            putExtra(WebSocketService.EXTRA_ROOM_CODE, roomCode)
        }
        startService(intent)
        ConnectionStateHolder.updateState(ConnectionState.CONNECTING)
        // RelayConnectScreen observes state and navigates back on success
    }

    private fun disconnectFromPc() {
        val intent = Intent(this, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_DISCONNECT
        }
        startService(intent)
        ConnectionStateHolder.updateState(ConnectionState.DISCONNECTED)
    }

    private fun requestSmsPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECEIVE_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(
                arrayOf(Manifest.permission.RECEIVE_SMS),
                REQUEST_SMS_PERMISSION,
            )
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                requestPermissions(
                    arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                    REQUEST_NOTIFICATION_PERMISSION,
                )
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        when (requestCode) {
            REQUEST_SMS_PERMISSION -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED
                ) {
                    Log.i(TAG, "SMS permission granted — seamless mode")
                    // Restart service to switch to seamless SMS mode
                    val intent = Intent(this, WebSocketService::class.java)
                    stopService(intent)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        startForegroundService(intent)
                    } else {
                        startService(intent)
                    }
                } else {
                    Log.w(TAG, "SMS permission denied — will use consent dialogs")
                }
            }
            REQUEST_NOTIFICATION_PERMISSION -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED
                ) {
                    Log.i(TAG, "Notification permission granted")
                }
            }
        }
    }

    companion object {
        private const val TAG = "MainActivity"
        private const val REQUEST_SMS_PERMISSION = 1001
        private const val REQUEST_NOTIFICATION_PERMISSION = 1002
    }
}
