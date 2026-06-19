package com.example.smssync.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import com.example.smssync.sms.CodeExtractor

/**
 * Accessibility service that reads SMS notifications to extract verification codes.
 *
 * NO SMS permission needed. NO Google services needed.
 * Works on ALL devices including Xiaomi with blocked permissions.
 *
 * User just needs to enable this in Settings → Accessibility.
 */
class SmsAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "SmsA11y"
        private const val OUR_PACKAGE = "com.example.smssync"
    }

    private var lastCode = ""
    private var lastCodeTime = 0L

    override fun onServiceConnected() {
        super.onServiceConnected()
        val info = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            notificationTimeout = 100
            flags = AccessibilityServiceInfo.DEFAULT
        }
        serviceInfo = info
        Log.i(TAG, "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.eventType != AccessibilityEvent.TYPE_NOTIFICATION_STATE_CHANGED) return

        // Skip our own notifications to prevent feedback loop
        val pkg = event.packageName?.toString() ?: ""
        if (pkg == OUR_PACKAGE) return

        val texts = event.text
        if (texts.isNullOrEmpty()) return

        val fullText = texts.joinToString(" ")

        // Dedup: skip same code within 5 seconds
        val code = CodeExtractor.extract(fullText) ?: return
        val now = System.currentTimeMillis()
        if (code == lastCode && now - lastCodeTime < 5000) return
        lastCode = code
        lastCodeTime = now

        val sender = CodeExtractor.extractSenderName(fullText)
            ?: event.packageName?.toString() ?: "验证码"

        Log.i(TAG, "Got code: $code from $sender (pkg=$pkg)")

        val intent = Intent(this, WebSocketService::class.java).apply {
            action = WebSocketService.ACTION_CODE_EXTRACTED
            putExtra(WebSocketService.EXTRA_CODE, code)
            putExtra(WebSocketService.EXTRA_SENDER, sender)
            putExtra(WebSocketService.EXTRA_BODY, fullText)
        }
        startService(intent)
    }

    override fun onInterrupt() {}
}
