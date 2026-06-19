package com.example.smssync.service

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log

/**
 * AlarmManager-based periodic wakeup to restart the SMS consent listener.
 * Survives process death — AlarmManager runs at the system level.
 */
class ConsentAlarmReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "ConsentAlarm"
        private const val INTERVAL_MS = 3 * 60 * 1000L  // restart every 3 minutes

        fun schedule(context: Context) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val intent = Intent(context, ConsentAlarmReceiver::class.java)
            val pendingIntent = PendingIntent.getBroadcast(
                context, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

            // Use exact alarm if possible, otherwise inexact
            try {
                alarmManager.setExactAndAllowWhileIdle(
                    AlarmManager.RTC_WAKEUP,
                    System.currentTimeMillis() + INTERVAL_MS,
                    pendingIntent,
                )
            } catch (_: Exception) {
                alarmManager.setInexactRepeating(
                    AlarmManager.RTC_WAKEUP,
                    System.currentTimeMillis() + INTERVAL_MS,
                    INTERVAL_MS,
                    pendingIntent,
                )
            }
            Log.d(TAG, "Alarm scheduled in ${INTERVAL_MS / 1000}s")
        }

        fun cancel(context: Context) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            val intent = Intent(context, ConsentAlarmReceiver::class.java)
            val pendingIntent = PendingIntent.getBroadcast(
                context, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            alarmManager.cancel(pendingIntent)
        }
    }

    override fun onReceive(context: Context, intent: Intent) {
        Log.i(TAG, "Alarm fired — renewing consent listener")
        SmsConsentHelper.startListening(context)
        // Schedule next alarm
        schedule(context)
    }
}
