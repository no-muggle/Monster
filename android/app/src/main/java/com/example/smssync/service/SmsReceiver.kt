package com.example.smssync.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import com.example.smssync.sms.CodeExtractor

/**
 * BroadcastReceiver for SMS_RECEIVED action.
 * Used when RECEIVE_SMS permission is granted — no user interaction needed.
 */
class SmsReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "SmsReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
        if (messages.isNullOrEmpty()) return

        for (message in messages) {
            val sender = message.originatingAddress ?: "未知"
            val body = message.messageBody ?: ""

            Log.d(TAG, "SMS from $sender: ${body.take(50)}...")

            val displayName = CodeExtractor.extractSenderName(body) ?: sender

            val code = CodeExtractor.extract(body)
            if (code != null) {
                Log.i(TAG, "Code: $code from $displayName")
                val forwardIntent = Intent(context, WebSocketService::class.java).apply {
                    action = WebSocketService.ACTION_CODE_EXTRACTED
                    putExtra(WebSocketService.EXTRA_CODE, code)
                    putExtra(WebSocketService.EXTRA_SENDER, displayName)
                    putExtra(WebSocketService.EXTRA_BODY, body)
                }
                context.startService(forwardIntent)
            }
        }
    }
}
