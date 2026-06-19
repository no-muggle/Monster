# SMS Sync — 手机验证码同步到 PC (v2.0)

将 Android 手机收到的短信验证码实时同步到 Windows PC，自动复制到剪贴板并弹出 Windows Toast 通知。

支持**局域网直连**和**云服务器中继**两种配对模式。

## 架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      局域网模式 (默认)                            │
│  Android App ←→ WebSocket (局域网) ←→ PC Server (Python)        │
│                                                                  │
│                      云服务器模式 (默认中继)                       │
│  Android App ←→ 公网 VPS 中继 ←→ PC Client (Python)             │
└──────────────────────────────────────────────────────────────────┘

Android 端:
  ├─ SmsReceiver (RECEIVE_SMS 广播，静默)
  ├─ SmsAccessibilityService (无障碍，小米兜底)
  ├─ CodeExtractor (10层正则 + 发送方提取，过滤非验证码短信)
  ├─ QR Scanner (CameraX + ML Kit)
  └─ Foreground Service (后台保活 + 断联自动重连)

PC 端:
  ├─ Clipboard (pyperclip) + Windows Toast (windows_toasts)
  ├─ 双模式配对弹窗 — 二维码 / 6位匹配码 (tkinter 暗色主题)
  ├─ System Tray (pystray, 红/黄/绿 状态)
  └─ 云服务器中继客户端 (默认 ws://101.37.15.16:8765)
```

- **通信**: JSON over WebSocket
- **配对方式**:
  - 局域网：PC 生成二维码 (含 IP + 持久化 token) → 手机扫码
  - 匹配码：PC 自动生成 6 位匹配码 → 手机输入 → VPS 中继配对
- **心跳**: 30s ping/pong (LAN)，中继模式依赖 WebSocket keep-alive
- **重连**: connectionId 追踪 + 指数退避，重启自动重连 (LAN)

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
├── README.md
├── .gitignore
├── docs/                          # 设计文档
├── pc/                            # PC 端 (Python)
│   ├── requirements.txt
│   ├── run.bat
│   ├── launcher.py                # PyInstaller 入口
│   ├── relay_server.py            # 云服务器中继 (部署到 VPS)
│   ├── test_connection.py         # PC 端网络诊断
│   └── src/
│       ├── main.py                # 入口 (LAN 始终运行 + --relay 参数)
│       ├── server/
│       │   ├── websocket_server.py # WS 服务端 + token 验证
│       │   ├── message_handler.py  # JSON 协议解析
│       │   └── relay_client.py     # 云服务器中继客户端 (host 端)
│       ├── notification/
│       │   └── notifier.py         # 剪贴板 + Windows Toast
│       ├── ui/
│       │   ├── tray_icon.py        # 系统托盘 (红/黄/绿)
│       │   ├── pairing_dialog.py   # 双模式配对弹窗 (v2.0 暗色主题)
│       │   ├── qr_dialog.py        # 旧版 QR 弹窗 (已弃用)
│       │   └── code_popup.py       # 验证码弹窗 (已弃用)
│       ├── network/lan_ip.py       # 局域网 IP 检测
│       └── config/settings.py      # Token 持久化 + 配置管理
└── android/                        # Android 端 (Kotlin + Compose)
    └── app/src/main/java/com/example/smssync/
        ├── MainActivity.kt         # 入口 (自动启动服务 + 主题持久化)
        ├── service/
        │   ├── WebSocketService.kt     # 前台服务 (WS + SMS + 自动重连)
        │   ├── SmsReceiver.kt          # RECEIVE_SMS 广播接收
        │   ├── SmsAccessibilityService.kt  # 无障碍读通知
        │   └── SmsRetrieverReceiver.kt     # Consent API (已弃用)
        ├── network/
        │   ├── WebSocketClient.kt      # OkHttp WS + relay + connectionId
        │   └── MessageProtocol.kt
        ├── sms/CodeExtractor.kt        # 10层正则: 验证码/口令/动态码...
        ├── ui/
        │   ├── MainScreen.kt           # 主界面 + 权限卡片 + 双卡片配对
        │   ├── QrScannerScreen.kt      # 扫码 (BackHandler 拦截)
        │   ├── RelayConnectScreen.kt   # 6位匹配码 + 折叠高级 + 粘贴 + 5s超时
        │   └── theme/                  # Material 3 (暗/亮)
        └── data/
            ├── Models.kt
            ├── PreferencesManager.kt   # DataStore (含 relay 持久化)
            └── ConnectionStateHolder.kt # 共享状态 + 历史持久化
```

## 常用命令

### PC 端

```bash
cd pc && pip install -r requirements.txt    # 首次安装依赖
python -m src.main                          # 局域网模式 (默认连云中继)
python -m src.main --relay ws://VPS:8765    # 指定云服务器
python test_connection.py                   # 诊断网络
python relay_server.py                      # 启动中继服务器 (在 VPS 上)

# 打包
cd pc && rm -rf build dist __pycache__ src/__pycache__ src/*/__pycache__ *.spec
python -m PyInstaller --onefile --noconsole --name "SmsSync" --clean \
  --icon ../assets/icon.ico --hidden-import tkinter --hidden-import PIL \
  --hidden-import pystray --hidden-import pyperclip --hidden-import qrcode \
  --hidden-import websockets --hidden-import windows_toasts \
  --hidden-import src --hidden-import src.main --hidden-import src.server \
  --hidden-import src.notification --hidden-import src.ui \
  --hidden-import src.network --hidden-import src.config \
  --hidden-import src.ui.pairing_dialog launcher.py
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
adb logcat | grep -i "WebSocketService\|WebSocketClient\|SmsA11y\|SmsReceiver"
adb shell dumpsys activity services com.example.smssync     # 服务状态
adb shell dumpsys package com.example.smssync | grep SMS    # 权限
```

### 云服务器部署

```bash
# 在 VPS 上
pip install websockets --break-system-packages
nohup python3 relay_server.py > relay.log 2>&1 &

# 阿里云 ECS 安全组开放 TCP 8765 (入方向)
# 查看日志: tail -f relay.log

# PC 端
SmsSync-v2.0.exe                    # 默认连接 ws://101.37.15.16:8765
SmsSync-v2.0.exe --relay ws://VPS:8765  # 指定中继地址

# 手机端
# APP → 输入匹配码 → 配对 (服务器地址在"高级设置"中)
```

## 关键技术决策

### 双模式配对 (v2.0)
- PC 对话框同时支持局域网二维码和匹配码
- 匹配码由 PC 本地生成 6 位随机数，通过中继服务器注册
- LAN 服务器始终运行，QR 扫码和匹配码可同时使用
- 匹配码有效期 5 分钟 (仅等配对阶段)，连接后不会因空闲超时

### token 持久化
- `get_or_create_token()` 保存到 `%APPDATA%/sms-sync/pairing_token.txt`
- 重启 PC token 不变，无需重新扫码

### Android 配对持久化与自动重连
- LAN 配对信息持久化到 DataStore，APP 重启后自动重连
- 中继匹配码为一次性，断联后自动清除配对信息

### connectionId 防冲突
- `WebSocketClient.connect()` 递增 `connectionId`
- 回调中 `isCurrent()` 检查，旧连接事件不影响新连接
- `handleConnect()` 先 `disconnect()` 再 `connect()`

### 中继线程安全
- `relay_loop` 闭包使用局部变量捕获 `relay`/`loop`/`dialog`，避免二次生成时 `self._relay` 被覆盖
- `update_relay_status()` 通过 `window.after(0,...)` 线程安全更新 UI

### X 按钮行为
- 点击关闭弹确认框 "关闭窗口会退出程序，是否继续？"
- 确认后彻底退出 (不残留进程)

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
10 层有序正则策略: 验证码/短信口令/口令/动态码/校验码/安全码/授权码/英文 code-otp-pin/验证码后置/授权码

已移除独立数字匹配 (Strategy 11)，避免银行通知等非验证码短信误发送

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
| 小米收不到验证码 | 开 RECEIVE_SMS + 无障碍服务，锁定 APP + 电池无限制 |
| 无障碍掉线 | 小米杀后台，锁定 APP + 电池无限制 |
| 中继连不上 | 确认 VPS relay_server.py 运行中，安全组开放 8765 |
| 匹配码连接超时 | 5 秒超时自动提示，检查匹配码是否正确 |
| PC 关闭后进程残留 | 点 X 确认退出，或托盘右键退出 |
| Toast 不弹 | 关闭其他 SmsSync 进程 (端口冲突)，确认通知权限开启 |
| 非验证码短信误发 | v2.0 已修复，只发含验证码关键词的短信 |

## 发布

- GitHub: https://github.com/no-muggle/Monster
- Releases: https://github.com/no-muggle/Monster/releases
- 中继服务器: ws://101.37.15.16:8765

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| JDK | 17 |
| Android SDK | platform 34, build-tools 34.0.0 |
| Android 手机 | 8.0+ (API 26+) |
| PC | Windows 10/11 |
