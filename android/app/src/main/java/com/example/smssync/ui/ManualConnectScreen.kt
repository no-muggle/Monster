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
import com.example.smssync.data.PairingInfo

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ManualConnectScreen(
    onConnect: (PairingInfo) -> Unit,
    onBack: () -> Unit,
) {
    var host by remember { mutableStateOf("") }
    var port by remember { mutableStateOf("9876") }
    var token by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("手动连接") },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                "在 PC 端二维码窗口下方找到以下信息并填入",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )

            OutlinedTextField(
                value = host,
                onValueChange = { host = it; error = null },
                label = { Text("IP 地址") },
                placeholder = { Text("例如 192.168.1.100") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )

            OutlinedTextField(
                value = port,
                onValueChange = { port = it; error = null },
                label = { Text("端口") },
                placeholder = { Text("9876") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            )

            OutlinedTextField(
                value = token,
                onValueChange = { token = it; error = null },
                label = { Text("配对码（可选）") },
                placeholder = { Text("32位配对码，未填则跳过验证") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )

            if (error != null) {
                Text(error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }

            Spacer(Modifier.height(8.dp))

            Button(
                onClick = {
                    if (host.isBlank()) { error = "请输入 IP 地址"; return@Button }
                    val portNum = port.toIntOrNull()
                    if (portNum == null || portNum !in 1..65535) { error = "端口号无效"; return@Button }
                    onConnect(PairingInfo(host.trim(), portNum, token.trim()))
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("连接")
            }
        }
    }
}
