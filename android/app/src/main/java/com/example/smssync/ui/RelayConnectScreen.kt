package com.example.smssync.ui

import android.content.ClipboardManager
import android.content.Context
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

private const val DEFAULT_RELAY_URL = "wss://your-server.com:8765"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RelayConnectScreen(
    onConnect: (relayUrl: String, roomCode: String) -> Unit,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    var relayUrl by remember { mutableStateOf(DEFAULT_RELAY_URL) }
    var roomCode by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var showAdvanced by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("输入匹配码") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                "输入 PC 上显示的 6 位匹配码",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )

            // Matching code input
            OutlinedTextField(
                value = roomCode,
                onValueChange = {
                    if (it.length <= 6 && it.all { c -> c.isDigit() }) {
                        roomCode = it
                        error = null
                    }
                },
                label = { Text("匹配码") },
                placeholder = { Text("6 位数字") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                trailingIcon = {
                    // Paste button
                    IconButton(onClick = {
                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                        val clip = clipboard.primaryClip
                        if (clip != null && clip.itemCount > 0) {
                            val text = clip.getItemAt(0).text?.toString() ?: ""
                            val digits = text.filter { it.isDigit() }.take(6)
                            if (digits.length == 6) {
                                roomCode = digits
                                error = null
                            }
                        }
                    }) {
                        Icon(Icons.Default.ContentPaste, contentDescription = "粘贴", modifier = Modifier.size(20.dp))
                    }
                },
            )

            // Advanced settings toggle
            TextButton(onClick = { showAdvanced = !showAdvanced }) {
                Icon(
                    if (showAdvanced) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(4.dp))
                Text("高级设置", style = MaterialTheme.typography.bodySmall)
            }

            // Collapsible server address
            AnimatedVisibility(visible = showAdvanced) {
                OutlinedTextField(
                    value = relayUrl,
                    onValueChange = { relayUrl = it; error = null },
                    label = { Text("服务器地址") },
                    placeholder = { Text("wss://your-server.com:8765") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }

            if (error != null) {
                Text(
                    error!!,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            Button(
                onClick = {
                    if (!relayUrl.startsWith("ws")) {
                        error = "服务器地址需以 ws:// 或 wss:// 开头"
                        return@Button
                    }
                    if (roomCode.length != 6 || roomCode.toIntOrNull() == null) {
                        error = "请输入 6 位匹配码"
                        return@Button
                    }
                    onConnect(relayUrl.trim(), roomCode.trim())
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Default.Link, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("配对")
            }
        }
    }
}
