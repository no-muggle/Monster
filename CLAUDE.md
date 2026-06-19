# SMS Sync — 手机验证码同步到 PC (v1.0)

将 Android 手机收到的短信验证码实时同步到 Windows PC，自动复制到剪贴板并弹出 Windows Toast 通知。

支持**局域网直连**和**云服务器中继**两种配对模式。

## 架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      局域网模式 (默认)                            │
│  Android App ←→ WebSocket (局域网) ←→ PC Server (Python)        │
│                                                                  │
│                      云服务器模式 (--relay)                       │
│  Android App ←→ 公网 VPS 中继 ←→ PC Client (Python)             │
└──────────────────────────────────────────────────────────────────┘

Android 端:
  ├─ SmsReceiver (RECEIVE_SMS 广播，静默)
  ├─ SmsAccessibilityService (无障碍，小米兜底)
  ├─ CodeExtractor (11层正则 + 发送方提取)
  ├─ QR Scanner (CameraX + ML Kit)
  └─ Foreground Service (后台保活)

PC 端:
  ├─ Clipboard (pyperclip) + Windows Toast 通知
  ├─ QR 码 / 房间码 弹窗 (tkinter)
  ├─ System Tray (pystray, 绿/黄/红 状态)
  └─ 云服务器中继客户端 (可选)
```

- **通信**: JSON over WebSocket
- **配对方式**:
  - 局域网：PC 生成二维码 (含 IP + 持久化 token) → 手机扫码
  - 云服务器：PC 连接 VPS 获取 4 位房间码 → 手机输入房间码和服务器地址
- **心跳**: 30s ping/pong
- **重连**: connectionId 追踪 + 指数退避

## 短信接收方案

| 方案 | 条件 | 体验 |
|------|------|------|
| **SmsReceiver** (BroadcastReceiver) | `RECEIVE_SMS` 权限已授权 | 完全静默 |
| **SmsAccessibilityService** (无障碍) | 用户在设置中开启 | 完全静默，读通知栏 |
| ~~SMS Consent API~~ | ~~Google Play Services~~ | 已废弃：国内 GMS 被墙 |

无障碍掉线时 APP 主界面显示醒目橙色提示卡片，服务每 5 分钟自动检测。

## 项目结构

```
messsge/
├── CLAUDE.md
├── requirements.txt
├── run.bat
├── launcher.py                    # PyInstaller 入口
├── relay_server.py                # 云服务器中继 (部署到 VPS)
├── test_connection.py             # PC 端网络诊断
├── SmsSync-v1.0.exe              # PC 端单文件 (30 MB)
├── sms-sync-v1.0.apk             # Android 安装包 (36 MB)
├── src/
│   ├── main.py                    # 入口 (+ 防火墙 + --relay 参数)
│   ├── server/
│   │   ├── websocket_server.py    # WS 服务端 + token 验证
│   │   ├── message_handler.py     # JSON 协议解析
│   │   └── relay_client.py        # 云服务器中继客户端 (host 端)
│   ├── notification/
│   │   └── notifier.py            # 剪贴板 + Windows Toast
│   ├── ui/
│   │   ├── tray_icon.py           # 系统托盘 (绿/黄/红)
│   │   ├── qr_dialog.py           # QR 码 / 房间码弹窗
│   │   └── code_popup.py          # 验证码弹窗 (已弃用)
│   ├── network/lan_ip.py          # 局域网 IP 检测
│   └── config/settings.py         # Token 持久化 + 配置管理
├── tests/
└── android/                       # Android Studio 打开
    ├── gradle/wrapper/
    └── app/src/main/java/com/example/smssync/
        ├── MainActivity.kt        # 入口 (自动启动服务 + 主题持久化)
        ├── service/
        │   ├── WebSocketService.kt    # 前台服务 (WS + SMS 监听 + 状态轮询)
        │   ├── SmsReceiver.kt         # RECEIVE_SMS 广播接收
        │   ├── SmsAccessibilityService.kt  # 无障碍读通知 (过滤自包)
        │   └── SmsRetrieverReceiver.kt     # Consent API (已弃用)
        ├── network/
        │   ├── WebSocketClient.kt     # OkHttp WS + relay + connectionId
        │   └── MessageProtocol.kt
        ├── sms/CodeExtractor.kt       # 11层正则: 验证码/口令/动态码...
        ├── ui/
        │   ├── MainScreen.kt          # 主界面 + 权限卡片 + 历史 + 暗色主题
        │   ├── QrScannerScreen.kt     # 扫码
        │   ├── RelayConnectScreen.kt  # 云服务器连接 (房间码)
        │   └── theme/                 # Material 3 (黑/亮)
        └── data/
            ├── Models.kt
            ├── PreferencesManager.kt      # DataStore (含主题 + 配对)
            └── ConnectionStateHolder.kt   # 共享状态 + 历史持久化
```

## 常用命令

### PC 端

```bash
pip install -r requirements.txt     # 首次安装依赖
python -m src.main                  # 局域网模式
python -m src.main --relay wss://VPS:8765  # 云服务器模式
python test_connection.py           # 诊断网络
python relay_server.py              # 启动中继服务器 (在 VPS 上)

python -m PyInstaller --onefile --console --name "SmsSync" \
  --icon assets/icon.ico --hidden-import tkinter --hidden-import PIL \
  --hidden-import pystray --hidden-import pyperclip --hidden-import qrcode \
  --hidden-import websockets --hidden-import windows_toasts \
  --hidden-import src --hidden-import src.main --hidden-import src.server \
  --hidden-import src.notification --hidden-import src.ui \
  --hidden-import src.network --hidden-import src.config launcher.py
```

### Android 端

```bash
cd android
export ANDROID_HOME="C:/Users/cuibo/AppData/Local/Android/Sdk"
./gradlew assembleDebug                                    # 编译
adb install -r app/build/outputs/apk/debug/app-debug.apk   # 安装
```

### ADB 调试

```bash
adb logcat | grep -i "WebSocket\|SmsA11y\|SmsReceiver"
adb shell dumpsys activity services com.example.smssync     # 服务状态
adb shell dumpsys package com.example.smssync | grep SMS    # 权限
```

### 云服务器部署

```bash
# 在 VPS 上
pip install websockets
nohup python relay_server.py > relay.log 2>&1 &
# 确保防火墙开放 8765 端口

# PC 端
SmsSync-v1.0.exe --relay wss://VPS_IP:8765
# 弹窗显示 4 位房间码

# 手机端
# APP → 云服务器连接 → 输入服务器地址 + 房间码 → 连接
```

## 关键技术决策

### token 持久化
- `get_or_create_token()` 保存到 `%APPDATA%/sms-sync/pairing_token.txt`
- 重启 PC token 不变，无需重新扫码

### connectionId 防冲突
- `WebSocketClient.connect()` 递增 `connectionId`
- 回调中 `isCurrent()` 检查，旧连接事件不影响新连接
- `handleConnect()` 先 `disconnect()` 再 `connect()`

### Python 3.9 兼容
- 所有文件 `from __future__ import annotations`
- `asyncio.TimeoutError` 需单独捕获

### 小米手机特殊处理
- `RECEIVE_SMS`: 设置→应用→权限→短信 手动开启
- 无障碍服务: 设置→更多设置→无障碍→SMS Sync 开启
- `pm grant` / `settings put secure` / `appops set` 均被小米封锁
- SMS Consent API 不可用: 国内 GMS 被墙
- 无障碍掉线: 界面橙色提示 + 5分钟自动检测

### 验证码识别 (CodeExtractor)
11 层有序正则策略: 验证码/短信口令/口令/动态码/校验码/安全码/授权码/英文 code-otp-pin/独立数字

### 历史记录持久化
- 保存到 `sms_history.json`，最多 5 条
- 点击=复制，发送按钮=重发到PC
- 当天显示 HH:mm:ss，更早显示 MM-dd HH:mm
- 重发自动去重

### 暗色主题持久化
- 通过 DataStore 保存主题偏好
- 杀后台重进保持之前选择

### Gradle 镜像
- `mirrors.cloud.tencent.com/gradle/`

## 常见问题

| 问题 | 解决 |
|------|------|
| PC 连不上 | 管理员运行 `netsh advfirewall firewall add rule name="SMS Sync" dir=in action=allow protocol=TCP localport=9876` |
| 手机连不上 | 同一 WiFi、关 AP 隔离、关移动数据 |
| Token 失效 | 删除 `%APPDATA%/sms-sync/pairing_token.txt` 重新扫码 |
| 断联后连不上 | 强制停止 APP 重开，扫码即可 |
| 小米收不到验证码 | 开 RECEIVE_SMS + 无障碍服务 |
| 无障碍掉线 | 小米杀后台，锁定 APP + 电池无限制 |
| 手动连接没跳转 | onQrScanned 未设置 showManual=false |
| 中继无房间码 | 确认 VPS relay_server.py 运行中，端口开放 |
| PC 日志刷 ConnectionClosed | 正常 WiFi 断流，已降级为 DEBUG |

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| JDK | 17 |
| Android SDK | platform 34, build-tools 34.0.0 |
| Android 手机 | 8.0+ (API 26+) |
| PC | Windows 10/11 |
