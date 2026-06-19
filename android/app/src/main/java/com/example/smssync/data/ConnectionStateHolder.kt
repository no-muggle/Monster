package com.example.smssync.data

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.File

object ConnectionStateHolder {
    private val _state = MutableStateFlow(ConnectionState.DISCONNECTED)
    val state: StateFlow<ConnectionState> = _state

    private val _lastCode = MutableStateFlow<String?>(null)
    val lastCode: StateFlow<String?> = _lastCode

    private val _lastSender = MutableStateFlow<String?>(null)
    val lastSender: StateFlow<String?> = _lastSender

    private val _history = MutableStateFlow<List<CodeEntry>>(emptyList())
    val history: StateFlow<List<CodeEntry>> = _history

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var historyFile: java.io.File? = null

    fun init(context: Context) {
        historyFile = java.io.File(context.filesDir, "sms_history.json")
        scope.launch {
            try {
                val json = historyFile?.readText() ?: ""
                if (json.isNotBlank()) {
                    _history.value = json.split("|||").mapNotNull { part ->
                        val p = part.split(":::")
                        if (p.size == 3) CodeEntry(p[0], p[1], p[2].toLongOrNull() ?: 0L) else null
                    }
                }
            } catch (_: Exception) {}
        }
    }

    fun updateState(newState: ConnectionState) {
        _state.value = newState
    }

    fun updateCode(code: String, sender: String) {
        _lastCode.value = code
        _lastSender.value = sender
        val entry = CodeEntry(code, sender, System.currentTimeMillis())
        _history.value = listOf(entry) + _history.value.take(4)
        saveHistory()
    }

    fun removeFromHistory(entry: CodeEntry) {
        _history.value = _history.value.filter { it != entry }
        saveHistory()
    }

    private fun saveHistory() {
        val file = historyFile ?: return
        scope.launch {
            try {
                val json = _history.value.joinToString("|||") { "${it.code}:::${it.sender}:::${it.timestamp}" }
                file.writeText(json)
            } catch (_: Exception) {}
        }
    }
}

data class CodeEntry(
    val code: String,
    val sender: String,
    val timestamp: Long,
)
