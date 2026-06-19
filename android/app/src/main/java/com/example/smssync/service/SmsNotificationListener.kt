package com.example.smssync.service

import android.content.Intent
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.example.smssync.sms.CodeExtractor

/**
 * Reads incoming SMS notifications and extracts verification codes.
 *
 * No SMS permission needed — user grants "Notification access" instead.
 * Xiaomi does NOT block notification access for sideloaded apps.
 */
class SmsNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "SmsNotifListener"
        // DON'T process our own notifications (prevents infinite loop)
        private const val OUR_PACKAGE = "com.example.smssync"
    }

    // Simple dedup: ignore same code within 10 seconds
    private var lastCode = ""
    private var lastCodeTime = 0L

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null) return

        val packageName = sbn.packageName

        // Skip our own notifications to prevent infinite loop
        if (packageName == OUR_PACKAGE) return

        // Also skip system UI notifications
        if (packageName == "com.android.systemui") return

        val title = sbn.notification.extras.getString("android.title") ?: ""
        val text = sbn.notification.extras.getString("android.text") ?: ""
        val fullText = "$title $text"

        val code = CodeExtractor.extract(fullText) ?: return

        // Dedup: skip if same code within 10 seconds
        val now = System.currentTimeMillis()
        if (code == lastCode && now - lastCodeTime < 10_000) {
            Log.d(TAG, "Dedup: skipping duplicate code $code")
            return
        }
        lastCode = code
        lastCodeTime = now

        val sender = CodeExtractor.extractSenderName(fullText) ?: packageName

        Log.i(TAG, "Got code: $code from $sender (app: $packageName)")

        val intent = Intent(this, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_CODE_EXTRACTED
            putExtra(WebSocketService.EXTRA_CODE, code)
            putExtra(WebSocketService.EXTRA_SENDER, sender)
            putExtra(WebSocketService.EXTRA_BODY, fullText)
        }
        startService(intent)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {}
}
