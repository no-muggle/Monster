package com.example.smssync.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RelayConnectScreen(
    onConnect: (relayUrl: String, roomCode: String) -> Unit,
    onBack: () -> Unit,
) {
    var relayUrl by remember { mutableStateOf("wss://") }
    var roomCode by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("云服务器连接") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") } },
            )
        },
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)) {

            Text("输入云服务器地址和 PC 上显示的房间码",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))

            OutlinedTextField(
                value = relayUrl, onValueChange = { relayUrl = it; error = null },
                label = { Text("服务器地址") },
                placeholder = { Text("wss://your-server.com:8765") },
                modifier = Modifier.fillMaxWidth(), singleLine = true,
            )

            OutlinedTextField(
                value = roomCode, onValueChange = { roomCode = it; error = null },
                label = { Text("房间码") },
                placeholder = { Text("4位数字") },
                modifier = Modifier.fillMaxWidth(), singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            )

            if (error != null)
                Text(error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)

            Button(onClick = {
                if (!relayUrl.startsWith("ws")) { error = "服务器地址需以 ws:// 或 wss:// 开头"; return@Button }
                if (roomCode.length != 4 || roomCode.toIntOrNull() == null) { error = "请输入4位房间码"; return@Button }
                onConnect(relayUrl.trim(), roomCode.trim())
            }, modifier = Modifier.fillMaxWidth()) { Text("连接") }
        }
    }
}
