package com.example.smssync.service

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.util.Log
import com.example.smssync.sms.CodeExtractor
import com.google.android.gms.auth.api.phone.SmsRetriever

/**
 * Transparent Activity that shows the system SMS consent dialog.
 *
 * The system dialog asks: "Allow [app] to read this message?"
 * User taps "Allow" → we get the SMS body → extract code → forward to PC
 * User taps "Deny" → we restart SMS listening
 *
 * This activity is translucent and finishes immediately after handling.
 */
class SmsConsentActivity : Activity() {

    companion object {
        private const val TAG = "SmsConsentActivity"
        const val EXTRA_CONSENT_INTENT = "consent_intent"
        private const val REQUEST_CODE_CONSENT = 2001
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val consentIntent = intent.getParcelableExtra<Intent>(EXTRA_CONSENT_INTENT)
        if (consentIntent == null) {
            Log.w(TAG, "No consent intent provided, finishing")
            finish()
            return
        }

        try {
            // The consent Intent from SMS Retriever is a regular Intent
            // that can be started with startActivityForResult
            startActivityForResult(consentIntent, REQUEST_CODE_CONSENT)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start consent dialog", e)
            finish()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)

        if (requestCode == REQUEST_CODE_CONSENT) {
            if (resultCode == RESULT_OK && data != null) {
                // User tapped "Allow" — get the SMS body
                val smsBody = data.getStringExtra(SmsRetriever.EXTRA_SMS_MESSAGE) ?: ""
                Log.i(TAG, "User consented, SMS: ${smsBody.take(50)}...")

                // Extract verification code
                val code = CodeExtractor.extract(smsBody)
                if (code != null) {
                    val sender = CodeExtractor.extractSenderName(smsBody) ?: "验证码"
                    Log.i(TAG, "Extracted code: $code from $sender")
                    // Forward to WebSocketService
                    val forwardIntent = Intent(this, WebSocketService::class.java).apply {
                        action = WebSocketService.ACTION_CODE_EXTRACTED
                        putExtra(WebSocketService.EXTRA_CODE, code)
                        putExtra(WebSocketService.EXTRA_SENDER, sender)
                        putExtra(WebSocketService.EXTRA_BODY, smsBody)
                    }
                    startService(forwardIntent)
                } else {
                    Log.d(TAG, "No verification code found in SMS")
                }
            } else {
                Log.d(TAG, "User denied consent or cancelled")
            }

            // Restart SMS listening for the next message
            SmsConsentHelper.restartListening(this)
        }

        // Always finish this translucent activity
        finish()
    }
}
