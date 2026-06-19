package com.example.smssync.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.example.smssync.data.CodeEntry
import com.example.smssync.data.ConnectionState
import com.example.smssync.data.ConnectionStateHolder
import com.example.smssync.data.PreferencesManager
import com.example.smssync.service.WebSocketService
import com.example.smssync.ui.theme.*
import java.text.SimpleDateFormat
import java.util.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    connectionState: ConnectionState, lastCode: String?, lastSender: String?,
    isDarkTheme: Boolean, onScanQrClick: () -> Unit, onRelayClick: () -> Unit, onDisconnectClick: () -> Unit, onToggleTheme: () -> Unit,
    refreshKey: Int,
) {
    val context = LocalContext.current
    val preferencesManager = remember { PreferencesManager(context) }
    var pairedPcName by remember { mutableStateOf("") }

    LaunchedEffect(Unit) { preferencesManager.savedPairing.collect { pairedPcName = it.pcName } }

    val hasSmsPerm = ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED
    val hasAccessibility = try { Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)?.contains("SmsAccessibilityService") == true } catch (_: Exception) { false }
    val history by ConnectionStateHolder.history.collectAsState()

    Scaffold(topBar = {
        TopAppBar(title = { Text("SMS Sync", fontWeight = FontWeight.Bold) },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = if (isDarkTheme) MaterialTheme.colorScheme.surface else MaterialTheme.colorScheme.primary,
                titleContentColor = if (isDarkTheme) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onPrimary),
            actions = { IconButton(onClick = onToggleTheme) { Icon(if (isDarkTheme) Icons.Default.LightMode else Icons.Default.DarkMode, "主题", tint = MaterialTheme.colorScheme.onPrimary) } })
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Spacer(Modifier.height(8.dp))
            ConnectionCard(connectionState, pairedPcName)
            CodeCard(lastCode, lastSender)

            if (!hasSmsPerm || !hasAccessibility) {
                Text("为确保稳定接收验证码，请开启以下权限", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f))
                if (!hasSmsPerm) PermissionCard(Icons.Default.Sms, "短信权限", "静默接收验证码", "⚠️") { context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply { data = Uri.parse("package:${context.packageName}") }) }
                if (!hasAccessibility) PermissionCard(Icons.Default.Accessibility, "无障碍服务已关闭", "点击重新开启", "⚠️") { context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
            }

            if (history.isNotEmpty()) {
                Text("历史验证码", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f), modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
                LazyColumn(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(history.size, key = { history[it].timestamp }) { i ->
                        val e = history[i]
                        HistoryItem(e,
                            onCopy = { (context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager).setPrimaryClip(android.content.ClipData.newPlainText("code", e.code)); android.widget.Toast.makeText(context, "已复制 ${e.code}", android.widget.Toast.LENGTH_SHORT).show() },
                            onSend = {
                                if (connectionState == ConnectionState.CONNECTED) {
                                    context.startService(Intent(context, WebSocketService::class.java).apply { action = WebSocketService.ACTION_CODE_EXTRACTED; putExtra(WebSocketService.EXTRA_CODE, e.code); putExtra(WebSocketService.EXTRA_SENDER, e.sender); putExtra(WebSocketService.EXTRA_BODY, "") })
                                    android.widget.Toast.makeText(context, "已发送 ${e.code}", android.widget.Toast.LENGTH_SHORT).show()
                                } else {
                                    android.widget.Toast.makeText(context, "未连接PC，无法发送", android.widget.Toast.LENGTH_SHORT).show()
                                }
                            },
                            onDelete = { ConnectionStateHolder.removeFromHistory(e) })
                    }
                }
            }

            Spacer(Modifier.weight(1f))
            if (connectionState == ConnectionState.CONNECTED) {
                OutlinedButton(onClick = onDisconnectClick, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.LinkOff, null); Spacer(Modifier.width(8.dp)); Text("断开连接") }
            } else {
                Button(onClick = onScanQrClick, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.QrCodeScanner, null); Spacer(Modifier.width(8.dp)); Text("扫描二维码连接") }
                Spacer(Modifier.height(6.dp))
                OutlinedButton(onClick = onRelayClick, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Cloud, null); Spacer(Modifier.width(8.dp)); Text("云服务器连接") }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun ConnectionCard(state: ConnectionState, pcName: String) {
    val (clr, txt) = when (state) { ConnectionState.CONNECTED -> Color(0xFF4CAF50) to "已连接"; ConnectionState.CONNECTING -> Color(0xFFFF9800) to "连接中..."; ConnectionState.RECONNECTING -> Color(0xFFFF9800) to "重连中..."; ConnectionState.DISCONNECTED -> Color(0xFFF44336) to "未连接" }
    Card(Modifier.fillMaxWidth(), RoundedCornerShape(16.dp), elevation = CardDefaults.cardElevation(2.dp)) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(14.dp).clip(CircleShape).background(clr)); Spacer(Modifier.width(14.dp))
            Column { Text(txt, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold); if (pcName.isNotBlank() && state == ConnectionState.CONNECTED) Text("配对: $pcName", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)) }
        }
    }
}

@Composable
private fun CodeCard(code: String?, sender: String?) {
    Card(Modifier.fillMaxWidth(), RoundedCornerShape(16.dp), elevation = CardDefaults.cardElevation(2.dp), colors = CardDefaults.cardColors(containerColor = if (code != null) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.6f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))) {
        Column(Modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            if (code != null) { Text(code, fontSize = 32.sp, fontWeight = FontWeight.Bold, letterSpacing = 4.sp, textAlign = TextAlign.Center); if (sender != null) { Spacer(Modifier.height(4.dp)); Text(sender, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)) } }
            else Text("等待接收验证码...", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f))
        }
    }
}

@Composable
private fun PermissionCard(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, subtitle: String, emoji: String, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth(), RoundedCornerShape(12.dp)) {
        Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = MaterialTheme.colorScheme.primary); Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) { Text(title, style = MaterialTheme.typography.labelLarge); Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)) }
            Text(emoji, fontSize = 18.sp)
        }
    }
}

@Composable
private fun HistoryItem(entry: CodeEntry, onCopy: () -> Unit, onSend: () -> Unit, onDelete: () -> Unit) {
    val date = Date(entry.timestamp)
    val today = Calendar.getInstance().apply { set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0) }.time
    val timeStr = if (date >= today) SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(date) else SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(date)

    Card(Modifier.fillMaxWidth(), RoundedCornerShape(8.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f))) {
        Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 4.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f).clickable(onClick = onCopy)) {
                Text(entry.code, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, letterSpacing = 2.sp, color = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.Bottom) { Text(entry.sender, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)); Spacer(Modifier.width(8.dp)); Text(timeStr, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)) }
            }
            IconButton(onClick = onSend) { Icon(Icons.Default.Send, "发送", tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(18.dp)) }
            IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, "删除", tint = Color(0xFFF44336).copy(alpha = 0.6f), modifier = Modifier.size(18.dp)) }
        }
    }
}
