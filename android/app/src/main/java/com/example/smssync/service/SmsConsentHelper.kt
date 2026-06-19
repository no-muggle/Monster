package com.example.smssync.service

import android.content.Context
import android.util.Log
import com.google.android.gms.auth.api.phone.SmsRetriever

/**
 * Helper for starting the SMS User Consent API listener.
 * Includes debouncing to prevent excessive calls.
 */
object SmsConsentHelper {

    private const val TAG = "SmsConsentHelper"
    private var lastStartTime = 0L
    private const val MIN_INTERVAL_MS = 30_000L  // debounce: max once per 30s

    fun startListening(context: Context) {
        val now = System.currentTimeMillis()
        if (now - lastStartTime < MIN_INTERVAL_MS) {
            return  // debounce
        }
        lastStartTime = now

        try {
            val client = SmsRetriever.getClient(context)
            client.startSmsUserConsent(null)
                .addOnSuccessListener {
                    Log.i(TAG, "SMS consent listener started successfully")
                }
                .addOnFailureListener { e ->
                    Log.e(TAG, "Failed to start SMS consent listener: ${e.message}")
                }
        } catch (e: Exception) {
            Log.e(TAG, "Error starting SMS consent listener", e)
        }
    }

    fun restartListening(context: Context) {
        startListening(context)
    }
}
