# DEPRECATED: Replaced by pairing_dialog.py. This file is kept for reference
# and will be removed in a future release. Do not import.
"""QR code dialog for pairing the Android app."""

from __future__ import annotations

import json
import logging
import tkinter as tk

import qrcode
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

BLUE = "#2196F3"
DARK = "#1A1A2E"
WHITE = "#FFFFFF"
GRAY = "#888899"


class QrDialog:
    """Tkinter window displaying a QR code or room code for pairing."""

    def __init__(self, host: str, port: int, token: str, pc_name: str = "", is_relay: bool = False):
        self._host = host
        self._port = port
        self._token = token
        self._pc_name = pc_name
        self._is_relay = is_relay
        self._window: tk.Tk | None = None
        self._photo: ImageTk.PhotoImage | None = None

    def _build_qr_data(self) -> str:
        return json.dumps(
            {"v": 1, "host": self._host, "port": self._port,
             "token": self._token, "name": self._pc_name},
            ensure_ascii=False,
        )

    def _generate_qr_image(self) -> Image.Image:
        data = self._build_qr_data()
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10, border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")

    def show(self) -> None:
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            self._window.focus_force()
            return

        win = tk.Tk()
        win.title("SMS Sync")
        win.configure(bg=WHITE)
        win.resizable(False, False)

        # Header bar
        header = tk.Frame(win, bg=BLUE, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="SMS Sync", font=("Segoe UI", 16, "bold"),
            bg=BLUE, fg=WHITE,
        ).pack(expand=True)

        # Body
        body = tk.Frame(win, bg=WHITE, padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        if self._is_relay:
            # Relay mode: show room code prominently
            tk.Label(
                body, text="在手机上输入以下房间码",
                font=("Microsoft YaHei UI", 10),
                bg=WHITE, fg=GRAY,
            ).pack(pady=(0, 20))
            code_frame = tk.Frame(body, bg="#F0F0F8", padx=30, pady=20)
            code_frame.pack()
            tk.Label(
                code_frame, text=self._token,  # token = room code in relay mode
                font=("Consolas", 48, "bold"),
                bg="#F0F0F8", fg="#7C5CFC",
            ).pack()
            tk.Label(
                code_frame, text="房间码",
                font=("Microsoft YaHei UI", 9),
                bg="#F0F0F8", fg=GRAY,
            ).pack()
        else:
            # Local mode: show QR code
            tk.Label(
                body, text="扫描二维码完成配对",
                font=("Microsoft YaHei UI", 10),
                bg=WHITE, fg=GRAY,
            ).pack(pady=(0, 15))
            qr_image = self._generate_qr_image()
            self._photo = ImageTk.PhotoImage(qr_image)
            qr_frame = tk.Frame(body, bg="#E0E0E0", padx=3, pady=3)
            qr_frame.pack()
            tk.Label(qr_frame, image=self._photo, bg=WHITE).pack()

        # Server info (skip in relay mode — already showed room code)
        if not self._is_relay:
            info_frame = tk.Frame(body, bg=WHITE)
            info_frame.pack(pady=(15, 5))
            tk.Label(
                info_frame, text=f"{self._host}:{self._port}",
                font=("Consolas", 10, "bold"), bg=WHITE, fg=DARK,
            ).pack()
            if self._pc_name:
                tk.Label(
                    info_frame, text=self._pc_name,
                    font=("Segoe UI", 9), bg=WHITE, fg=GRAY,
                ).pack()

        # Divider
        tk.Frame(body, bg="#E0E0E0", height=1).pack(fill=tk.X, pady=(10, 10))

        # Status
        tk.Label(
            body,
            text="● 服务运行中  点击 ✕ 隐藏到托盘",
            font=("Microsoft YaHei UI", 8),
            bg=WHITE, fg="#4CAF50",
        ).pack()

        win.protocol("WM_DELETE_WINDOW", lambda: win.withdraw())

        # Center
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

        self._window = win
        logger.info("QR dialog shown for ws://%s:%d", self._host, self._port)
        win.mainloop()

    def close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
            self._photo = None

    def _on_close(self) -> None:
        if self._window is not None:
            self._window.withdraw()

    def is_showing(self) -> bool:
        return self._window is not None and self._window.winfo_exists()
