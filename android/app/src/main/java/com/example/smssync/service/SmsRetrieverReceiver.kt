package com.example.smssync.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import com.google.android.gms.auth.api.phone.SmsRetriever

/**
 * BroadcastReceiver for SMS User Consent API.
 *
 * Receives SMS_RETRIEVED_ACTION broadcasts. The broadcast contains an
 * Intent extra that launches a system consent dialog. Once the user
 * taps "Allow", the SMS body is returned.
 *
 * NO SMS permission required — works on Xiaomi and all other devices.
 */
class SmsRetrieverReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "SmsRetrieverReceiver"
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != SmsRetriever.SMS_RETRIEVED_ACTION) {
            return
        }

        Log.d(TAG, "SMS retriever broadcast received")

        // Extract the consent Intent from extras
        val extras = intent.extras ?: run {
            Log.w(TAG, "No extras in SMS retriever broadcast")
            return
        }

        // Get the status
        val status = extras.get(SmsRetriever.EXTRA_STATUS) as? com.google.android.gms.common.api.Status
        if (status != null && status.statusCode == com.google.android.gms.common.api.CommonStatusCodes.TIMEOUT) {
            Log.d(TAG, "SMS retriever timed out, restarting...")
            SmsConsentHelper.restartListening(context)
            return
        }

        // Get the consent intent
        val consentIntent = extras.getParcelable<Intent>(SmsRetriever.EXTRA_CONSENT_INTENT)
        if (consentIntent != null) {
            Log.d(TAG, "Got consent intent, launching consent activity")
            // Launch the consent activity to show the user the Allow/Deny dialog
            val activityIntent = Intent(context, SmsConsentActivity::class.java).apply {
                putExtra(SmsConsentActivity.EXTRA_CONSENT_INTENT, consentIntent)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(activityIntent)
        } else {
            Log.w(TAG, "No consent intent in broadcast extras")
            SmsConsentHelper.restartListening(context)
        }
    }
}
