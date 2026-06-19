"""Pairing dialog — dual-mode selection: QR code or matching code."""

from __future__ import annotations

import json
import logging
import random
import tkinter as tk
from tkinter import messagebox
from collections.abc import Callable
import qrcode
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

# Colors — dark theme
HEADER_BG = "#12121E"
HEADER_FG = "#FFFFFF"
BODY_BG = "#1E1E2E"
TEXT_PRIMARY = "#E8E8F0"
TEXT_SECONDARY = "#9A9AB0"
CARD_BG = "#2A2A3E"
CARD_BORDER = "#3E3E55"
CARD_HOVER_BG = "#323250"
CODE_COLOR = "#60A5FA"
CODE_BG = "#2A2240"
SUCCESS_GREEN = "#4ADE80"
DIVIDER_COLOR = "#3E3E55"
ERR_RED = "#F87171"

WINDOW_WIDTH = 460
ARROW_RIGHT = "→"  # →
ARROW_LEFT = "←"   # ←


class PairingDialog:
    """Tkinter dialog with mode selection, QR code, and matching code screens."""

    def __init__(
        self,
        lan_host: str,
        lan_port: int,
        lan_token: str,
        pc_name: str = "",
        relay_url: str = "",
    ):
        self._lan_host = lan_host
        self._lan_port = lan_port
        self._lan_token = lan_token
        self._pc_name = pc_name
        self._relay_url = relay_url
        self._matching_code: str | None = None
        self._relay_connected: bool = False

        self._window: tk.Tk | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._mode_frame: tk.Frame | None = None
        self._qr_frame: tk.Frame | None = None
        self._code_frame: tk.Frame | None = None
        self._status_label: tk.Label | None = None
        self._code_label: tk.Label | None = None
        self._retry_button: tk.Button | None = None

        # Callbacks
        self.on_start_relay: Callable[[str], None] | None = None
        self.on_quit: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Window sizing
    # ------------------------------------------------------------------

    def _refit_window(self) -> None:
        """Resize window to fit current screen content, then lock size."""
        self._window.resizable(True, True)
        self._window.update_idletasks()
        w = max(self._window.winfo_reqwidth(), WINDOW_WIDTH)
        h = self._window.winfo_reqheight()
        sw = self._window.winfo_screenwidth()
        sh = self._window.winfo_screenheight()
        self._window.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self._window.resizable(False, False)

    # ------------------------------------------------------------------
    # Header builder
    # ------------------------------------------------------------------

    def _build_header(self, parent: tk.Frame, title: str, show_back: bool = False) -> tk.Frame:
        """Build the dark header bar with optional back button."""
        header = tk.Frame(parent, bg=HEADER_BG, height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        if show_back:
            back_btn = tk.Label(
                header, text=f"  {ARROW_LEFT} 返回",
                font=("Microsoft YaHei UI", 9),
                bg=HEADER_BG, fg=TEXT_SECONDARY, cursor="hand2",
            )
            back_btn.pack(side=tk.LEFT, padx=(12, 0))
            back_btn.bind("<Button-1>", lambda e: self._show_mode_selection())
            back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=HEADER_FG))
            back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=TEXT_SECONDARY))

        title_label = tk.Label(
            header, text=title,
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=HEADER_BG, fg=HEADER_FG,
        )
        title_label.pack(expand=True)
        return header

    # ------------------------------------------------------------------
    # Mode selection screen
    # ------------------------------------------------------------------

    def _show_mode_selection(self) -> None:
        """Show the mode selection screen (first screen)."""
        if self._qr_frame:
            self._qr_frame.pack_forget()
        if self._code_frame:
            self._code_frame.pack_forget()

        if self._mode_frame is None:
            self._mode_frame = tk.Frame(self._window, bg=BODY_BG)
            self._build_header(self._mode_frame, "SMS Sync", show_back=False)
            self._build_mode_screen(self._mode_frame)

        self._mode_frame.pack(fill=tk.BOTH, expand=True)
        self._refit_window()

    def _build_mode_screen(self, parent: tk.Frame) -> None:
        """Build the two-card mode selection layout."""
        # Hint
        tk.Label(
            parent, text="请选择配对方式",
            font=("Microsoft YaHei UI", 10),
            bg=BODY_BG, fg=TEXT_SECONDARY,
        ).pack(pady=(24, 18))

        # Card 1: LAN QR
        card1 = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, cursor="hand2")
        card1.pack(fill=tk.X, padx=24, pady=(0, 12))
        self._make_card(card1, "\U0001F4F7", "局域网二维码",
                        "同一 WiFi 下扫码连接，无需服务器，低延迟",
                        lambda: self._show_qr_screen())
        self._bind_card_hover(card1)

        # Card 2: Matching code
        card2 = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, cursor="hand2")
        card2.pack(fill=tk.X, padx=24, pady=(0, 24))
        self._make_card(card2, "\U0001F511", "匹配码",
                        "6 位数字码，通过服务器中继，跨网络也能用",
                        lambda: self._on_matching_code_selected())
        self._bind_card_hover(card2)

        # Bottom status
        tk.Frame(parent, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, padx=24)
        tk.Label(
            parent, text="● 服务运行中",
            font=("Microsoft YaHei UI", 8),
            bg=BODY_BG, fg=SUCCESS_GREEN,
        ).pack(pady=(10, 16))

    def _make_card(self, card: tk.Frame, icon: str, title: str, subtitle: str, on_click: Callable) -> None:
        """Populate a card with icon, title, subtitle, and arrow."""
        inner = tk.Frame(card, bg=CARD_BG, padx=16, pady=14)
        inner.pack(fill=tk.X)
        inner.bind("<Button-1>", lambda e: on_click())

        tk.Label(inner, text=icon, font=("Segoe UI", 22),
                 bg=CARD_BG).pack(side=tk.LEFT, padx=(0, 14))

        text_col = tk.Frame(inner, bg=CARD_BG)
        text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(text_col, text=title,
                 font=("Microsoft YaHei UI", 12, "bold"),
                 bg=CARD_BG, fg=TEXT_PRIMARY, anchor="w").pack(fill=tk.X)
        tk.Label(text_col, text=subtitle,
                 font=("Microsoft YaHei UI", 8),
                 bg=CARD_BG, fg=TEXT_SECONDARY, anchor="w").pack(fill=tk.X)

        tk.Label(inner, text=ARROW_RIGHT,
                 font=("Segoe UI", 14), bg=CARD_BG,
                 fg=TEXT_SECONDARY).pack(side=tk.RIGHT, padx=(8, 0))

        # Make entire card clickable
        for widget in [card, inner, text_col] + list(inner.children.values()) + list(text_col.children.values()):
            try:
                widget.bind("<Button-1>", lambda e: on_click())
            except Exception:
                pass

    def _bind_card_hover(self, card: tk.Frame) -> None:
        """Add hover highlight to card border."""
        def on_enter(e):
            card.configure(highlightbackground=SUCCESS_GREEN, highlightthickness=2)

        def on_leave(e):
            card.configure(highlightbackground=CARD_BORDER, highlightthickness=1)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    # ------------------------------------------------------------------
    # QR code screen
    # ------------------------------------------------------------------

    def _show_qr_screen(self) -> None:
        """Show the LAN QR code screen."""
        if self._mode_frame:
            self._mode_frame.pack_forget()

        if self._qr_frame is None:
            self._qr_frame = tk.Frame(self._window, bg=BODY_BG)
            self._build_header(self._qr_frame, "局域网二维码", show_back=True)

            body = tk.Frame(self._qr_frame, bg=BODY_BG, padx=30, pady=20)
            body.pack(fill=tk.BOTH, expand=True)

            tk.Label(body, text="扫描二维码完成配对",
                     font=("Microsoft YaHei UI", 10),
                     bg=BODY_BG, fg=TEXT_SECONDARY).pack(pady=(0, 15))

            qr_image = self._generate_qr_image()
            self._photo = ImageTk.PhotoImage(qr_image)
            qr_box = tk.Frame(body, bg=DIVIDER_COLOR, padx=3, pady=3)
            qr_box.pack()
            tk.Label(qr_box, image=self._photo, bg="#FFFFFF").pack()

            info_frame = tk.Frame(body, bg=BODY_BG)
            info_frame.pack(pady=(15, 5))
            tk.Label(info_frame,
                     text=f"{self._lan_host}:{self._lan_port}",
                     font=("Consolas", 10, "bold"),
                     bg=BODY_BG, fg=TEXT_PRIMARY).pack()
            if self._pc_name:
                tk.Label(info_frame, text=self._pc_name,
                         font=("Segoe UI", 9),
                         bg=BODY_BG, fg=TEXT_SECONDARY).pack()

            tk.Frame(body, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, pady=(10, 10))
            tk.Label(body, text="● 服务运行中  点击 ✕ 隐藏到托盘",
                     font=("Microsoft YaHei UI", 8),
                     bg=BODY_BG, fg=SUCCESS_GREEN).pack()

        self._qr_frame.pack(fill=tk.BOTH, expand=True)
        self._refit_window()

    # ------------------------------------------------------------------
    # Matching code screen
    # ------------------------------------------------------------------

    def _on_matching_code_selected(self) -> None:
        """User clicked matching code card — generate code or show existing."""
        # If already connected, just show the existing code — don't regenerate
        if self._relay_connected and self._matching_code:
            self._show_code_screen()
            return

        # Generate 6-digit code
        self._matching_code = f"{random.randint(100000, 999999):06d}"
        logger.info("Generated matching code: %s", self._matching_code)
        self._show_code_screen()

        # Notify main.py to start relay connection
        if self.on_start_relay:
            self.on_start_relay(self._matching_code)

    def _copy_matching_code(self) -> None:
        """Copy the matching code to clipboard and show toast."""
        if not self._matching_code:
            return
        try:
            import pyperclip
            pyperclip.copy(self._matching_code)
            self._show_toast("已复制到剪贴板 ✓")
        except Exception:
            pass

    def _show_toast(self, msg: str) -> None:
        """Show a brief toast popup near the code label."""
        if not self._window:
            return
        toast = tk.Toplevel(self._window)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#333355")
        tk.Label(toast, text=msg,
                 font=("Microsoft YaHei UI", 10),
                 bg="#333355", fg="#FFFFFF",
                 padx=16, pady=8).pack()
        # Position near center of parent
        self._window.update_idletasks()
        px = self._window.winfo_rootx() + self._window.winfo_width() // 2
        py = self._window.winfo_rooty() + self._window.winfo_height() // 2 + 80
        toast.update_idletasks()
        toast.geometry(f"+{px-toast.winfo_width()//2}+{py}")
        self._window.after(1800, toast.destroy)

    def _show_code_screen(self) -> None:
        """Show the matching code display screen."""
        if self._mode_frame:
            self._mode_frame.pack_forget()

        if self._code_frame is None:
            self._code_frame = tk.Frame(self._window, bg=BODY_BG)
            self._build_header(self._code_frame, "匹配码连接", show_back=True)

            body = tk.Frame(self._code_frame, bg=BODY_BG, padx=30, pady=30)
            body.pack(fill=tk.BOTH, expand=True)

            tk.Label(body, text="在手机上输入此匹配码",
                     font=("Microsoft YaHei UI", 10),
                     bg=BODY_BG, fg=TEXT_SECONDARY).pack(pady=(0, 32))

            # Code display card — clickable to copy
            code_card = tk.Frame(body, bg=CODE_BG, padx=36, pady=32, cursor="hand2")
            code_card.pack()
            display_code = " ".join(self._matching_code)
            self._code_label = tk.Label(
                code_card, text=display_code,
                font=("Consolas", 44, "bold"),
                bg=CODE_BG, fg=CODE_COLOR,
            )
            self._code_label.pack()
            self._code_label.bind("<Button-1>", lambda e: self._copy_matching_code())
            code_card.bind("<Button-1>", lambda e: self._copy_matching_code())

            # Server address
            if self._relay_url:
                tk.Label(body, text=f"服务器: {self._relay_url}",
                         font=("Consolas", 8),
                         bg=BODY_BG, fg=TEXT_SECONDARY).pack(pady=(20, 6))

            tk.Frame(body, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, pady=(16, 16))

            # Status
            self._status_label = tk.Label(
                body, text="● 正在连接服务器...",
                font=("Microsoft YaHei UI", 8),
                bg=BODY_BG, fg=TEXT_SECONDARY,
            )
            self._status_label.pack()

            # Retry button (hidden by default, shown on error)
            self._retry_button = tk.Button(
                body, text="重试",
                font=("Microsoft YaHei UI", 9),
                bg=ERR_RED, fg="#FFFFFF",
                activebackground="#DC2626", activeforeground="#FFFFFF",
                relief="flat", cursor="hand2", padx=20, pady=4,
                command=lambda: self._on_matching_code_selected(),
            )

        else:
            # Update the code label if re-entering
            if self._code_label:
                display_code = " ".join(self._matching_code)
                self._code_label.configure(text=display_code)

        self._code_frame.pack(fill=tk.BOTH, expand=True)
        self._refit_window()

    def update_relay_status(self, status: str) -> None:
        """Thread-safe update of the relay connection status.

        Args:
            status: One of 'connecting', 'waiting', 'connected', 'error:<msg>'
        """
        if self._window is None:
            return

        status_map = {
            "connecting": ("● 正在连接服务器...", TEXT_SECONDARY),
            "waiting": ("● 等待手机输入匹配码...", TEXT_SECONDARY),
            "connected": ("● 手机已连接 ✓", SUCCESS_GREEN),
        }

        def _update():
            if self._status_label is None:
                return
            if status.startswith("error:"):
                self._relay_connected = False
                msg = status[6:]
                self._status_label.configure(
                    text=f"✗ {msg}", fg=ERR_RED
                )
                if self._retry_button is not None:
                    self._retry_button.pack(pady=(8, 0))
            else:
                self._relay_connected = (status == "connected")
                text, color = status_map.get(status, (status, TEXT_SECONDARY))
                self._status_label.configure(text=text, fg=color)
                if self._retry_button is not None:
                    self._retry_button.pack_forget()

        self._window.after(0, _update)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show the dialog window."""
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            self._window.focus_force()
            return

        win = tk.Tk()
        win.title("SMS Sync")
        win.configure(bg=BODY_BG)
        win.resizable(False, False)

        self._window = win
        self._show_mode_selection()

        def on_close():
            if messagebox.askyesno("退出 SMS Sync", "关闭窗口会退出程序，是否继续？", default="no"):
                win.destroy()
                if self.on_quit:
                    self.on_quit()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # Center on screen, fit to content
        win.minsize(WINDOW_WIDTH, 200)
        self._refit_window()

        logger.info("Pairing dialog shown")
        win.mainloop()

    def close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None
            self._photo = None

    def is_showing(self) -> bool:
        return self._window is not None and self._window.winfo_exists()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _generate_qr_image(self) -> Image.Image:
        data = json.dumps(
            {"v": 1, "host": self._lan_host, "port": self._lan_port,
             "token": self._lan_token, "name": self._pc_name},
            ensure_ascii=False,
        )
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=11, border=3,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
