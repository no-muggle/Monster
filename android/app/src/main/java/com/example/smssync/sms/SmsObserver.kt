package com.example.smssync.sms

import android.content.Context
import android.content.Intent
import android.database.ContentObserver
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Telephony
import android.util.Log
import com.example.smssync.service.WebSocketService

/**
 * ContentObserver that watches the SMS inbox for new messages.
 *
 * More reliable than BroadcastReceiver on Xiaomi — doesn't depend on
 * system broadcast delivery which MIUI may block.
 */
class SmsObserver(
    private val context: Context,
    handler: Handler = Handler(Looper.getMainLooper()),
) : ContentObserver(handler) {

    companion object {
        private const val TAG = "SmsObserver"
        private const val SMS_URI = "content://sms/inbox"
    }

    override fun onChange(selfChange: Boolean, uri: Uri?) {
        super.onChange(selfChange, uri)

        try {
            checkNewSms()
        } catch (e: Exception) {
            Log.e(TAG, "Error checking SMS", e)
        }
    }

    private fun checkNewSms() {
        val cursor = context.contentResolver.query(
            Uri.parse(SMS_URI),
            arrayOf(Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE),
            null, null,
            "${Telephony.Sms.DEFAULT_SORT_ORDER} DESC LIMIT 1",
        ) ?: return

        cursor.use {
            if (it.moveToFirst()) {
                val sender = it.getString(0) ?: "未知"
                val body = it.getString(1) ?: ""
                val date = it.getLong(2)

                Log.d(TAG, "New SMS from $sender: ${body.take(50)}")

                val code = CodeExtractor.extract(body)
                if (code != null) {
                    val displayName = CodeExtractor.extractSenderName(body) ?: sender
                    Log.i(TAG, "Code: $code from $displayName")

                    val intent = Intent(context, WebSocketService::class.java).apply {
                        action = WebSocketService.ACTION_CODE_EXTRACTED
                        putExtra(WebSocketService.EXTRA_CODE, code)
                        putExtra(WebSocketService.EXTRA_SENDER, displayName)
                        putExtra(WebSocketService.EXTRA_BODY, body)
                    }
                    context.startService(intent)
                }
            }
        }
    }
}
