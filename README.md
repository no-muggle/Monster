# SMS Sync — 手机验证码同步到 PC

> v2.0 · Android → PC 验证码实时同步，自动复制到剪贴板。

将 Android 手机收到的短信验证码实时同步到 Windows PC，自动复制剪贴板并弹出 Windows Toast 通知。

支持**局域网直连**和**云服务器中继**两种配对模式。

---

## 功能

- 📋 **自动复制** — 验证码到达 PC 后自动复制到剪贴板，直接粘贴使用
- 🔔 **Windows 通知** — Toast 弹窗显示验证码和发送方
- 📱 **双模式配对** — 局域网扫码 or 匹配码走云服务器中继
- 🌐 **跨网络** — 匹配码模式支持手机在任何网络同步到 PC
- 🎨 **暗色主题** — PC 对话框和 Android APP 均支持暗色模式
- 📜 **历史记录** — 最多 5 条，点击复制，支持重发
- 🔌 **自动重连** — WebSocket 断线指数退避重连

## 快速开始

### PC 端（Windows 10/11）

1. 下载 `SmsSync-v2.0.exe`（无需安装 Python）
2. 双击运行，系统托盘出现图标
3. 弹窗选择配对方式：
   - **局域网二维码** — 同一 WiFi 下手机扫码配对
   - **匹配码** — 输入 6 位数字码，通过云服务器中继

### Android 端

1. 安装 `sms-sync-v2.0.apk`
2. 授予短信权限 + 开启无障碍服务（小米必做）
3. 主界面选择配对方式：
   - **扫描二维码** — 扫 PC 端的码
   - **输入匹配码** — 输入 PC 显示的 6 位码

### 云服务器（可选，匹配码模式需要）

```bash
pip install websockets
python relay_server.py  # 默认端口 8765
```

---

## 开发

### 环境

| 组件 | 版本 |
|------|------|
| Python | 3.9+ |
| JDK | 17 |
| Android SDK | Platform 34 |

### PC 端

```bash
cd pc
pip install -r requirements.txt
python -m src.main                        # 局域网模式
python -m src.main --relay ws://VPS:8765  # 云服务器模式
```

打包：
```bash
cd pc
python -m PyInstaller --onefile --noconsole --name "SmsSync" \
  --hidden-import tkinter --hidden-import PIL --hidden-import pystray \
  --hidden-import pyperclip --hidden-import qrcode --hidden-import websockets \
  --hidden-import windows_toasts --hidden-import src --hidden-import src.main \
  --hidden-import src.server --hidden-import src.notification \
  --hidden-import src.ui --hidden-import src.network --hidden-import src.config \
  --hidden-import src.ui.pairing_dialog launcher.py
```

### Android 端

```bash
cd android
export ANDROID_HOME="~/Android/Sdk"
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### 调试

```bash
# PC 日志
tail -f %APPDATA%/sms-sync/sms-sync.log

# Android 日志
adb logcat | grep -i "WebSocket\|SmsA11y\|SmsReceiver"

# 中继服务器日志
ssh VPS tail -f relay.log
```

---

## 项目结构

```
messsge/
├── README.md
├── CLAUDE.md
├── pc/                     # PC 端 (Python)
│   ├── src/main.py         # 入口
│   ├── src/server/         # WebSocket 服务 + 中继客户端
│   ├── src/ui/             # 对话框 + 系统托盘
│   ├── src/notification/   # 剪贴板 + Toast
│   ├── src/config/         # Token + 配置
│   ├── relay_server.py     # 云服务器中继
│   └── launcher.py         # PyInstaller 入口
├── android/                # Android 端 (Kotlin + Compose)
│   └── app/src/main/java/com/example/smssync/
│       ├── service/        # 前台服务 + 短信接收
│       ├── ui/             # 主界面 + 扫码 + 匹配码
│       ├── network/        # WebSocket 客户端
│       └── sms/            # CodeExtractor (10层正则)
└── docs/                   # 设计文档
```

## 常见问题

| 问题 | 解决 |
|------|------|
| PC 连不上 | 管理员运行 `netsh advfirewall firewall add rule name="SMS Sync" dir=in action=allow protocol=TCP localport=9876` |
| 手机连不上 | 同 WiFi、关 AP 隔离、关移动数据 |
| Token 失效 | 删除 `%APPDATA%/sms-sync/pairing_token.txt` 重新扫码 |
| 小米收不到验证码 | 开 RECEIVE_SMS + 无障碍服务，锁定 APP + 电池无限制 |
| 无障碍掉线 | 小米杀后台，锁定 APP + 电池无限制 |
| 非验证码短信误发 | 已过滤，只发含验证码关键词的短信 |

## License

MIT
