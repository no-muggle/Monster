"""Pairing dialog — dual-mode selection: QR code or matching code.

Uses grid stacking for flicker-free screen transitions.
All three screens are pre-built once; switching is just tkraise().
"""

from __future__ import annotations

import json
import logging
import queue
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
DIGIT_BLOCK_BG = "#1E1838"
DIGIT_BLOCK_BORDER = "#3D3570"
SUCCESS_GREEN = "#4ADE80"
DIVIDER_COLOR = "#3E3E55"
ERR_RED = "#F87171"

WINDOW_WIDTH = 460
ARROW_RIGHT = "→"
ARROW_LEFT = "←"


class PairingDialog:
    """Tkinter dialog with flicker-free screen switching via grid stacking."""

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
        self._container: tk.Frame | None = None
        self._mode_frame: tk.Frame | None = None
        self._qr_frame: tk.Frame | None = None
        self._code_frame: tk.Frame | None = None
        self._status_label: tk.Label | None = None
        self._digit_labels: list[tk.Label] = []
        self._digit_frame: tk.Frame | None = None
        self._retry_button: tk.Button | None = None
        self._mode_status_label: tk.Label | None = None
        self._qr_status_label: tk.Label | None = None

        # Thread-safe UI update queue (worker threads push, main loop polls)
        self._ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        # Callbacks
        self.on_start_relay: Callable[[str], None] | None = None
        self.on_quit: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Window sizing
    # ------------------------------------------------------------------

    def _refit_window(self, first_time: bool = False) -> None:
        """Resize window to fit content.

        On first show, centers on screen. On subsequent calls,
        preserves the user's chosen window position.
        """
        if self._window is None:
            return
        self._window.update_idletasks()
        w = max(self._window.winfo_reqwidth(), WINDOW_WIDTH)
        h = self._window.winfo_reqheight()
        if first_time:
            sw = self._window.winfo_screenwidth()
            sh = self._window.winfo_screenheight()
            x, y = (sw - w) // 2, (sh - h) // 2
        else:
            x, y = self._window.winfo_x(), self._window.winfo_y()
        self._window.geometry(f"{w}x{h}+{x}+{y}")

    # ------------------------------------------------------------------
    # Header builder
    # ------------------------------------------------------------------

    def _build_header(
        self, parent: tk.Frame, title: str, show_back: bool = False
    ) -> tk.Frame:
        """Build the dark header bar with optional back button."""
        header = tk.Frame(parent, bg=HEADER_BG, height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        if show_back:
            back_btn = tk.Label(
                header, text=f"  {ARROW_LEFT} 返回",
                font=("Microsoft YaHei UI", 10),
                bg=HEADER_BG, fg=TEXT_SECONDARY, cursor="hand2",
            )
            back_btn.pack(side=tk.LEFT, padx=(12, 0))
            back_btn.bind("<Button-1>", lambda e: self._show_mode_selection())
            back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=HEADER_FG))
            back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=TEXT_SECONDARY))

        tk.Label(
            header, text=title,
            font=("Microsoft YaHei UI", 13, "bold"),
            bg=HEADER_BG, fg=HEADER_FG,
        ).pack(expand=True)
        return header

    # ------------------------------------------------------------------
    # Mode selection screen
    # ------------------------------------------------------------------

    def _switch_to(self, target: tk.Frame) -> None:
        """Switch to target frame: hide others from layout, show target, refit."""
        for f in (self._mode_frame, self._qr_frame, self._code_frame):
            if f is None:
                continue
            if f is target:
                f.grid()
                f.tkraise()
            else:
                f.grid_remove()
        self._refit_window()

    def _show_mode_selection(self) -> None:
        """Show the mode selection screen."""
        if self._mode_frame is not None:
            self._switch_to(self._mode_frame)

    def _build_mode_screen(self, parent: tk.Frame) -> None:
        """Build the two-card mode selection layout."""
        tk.Label(
            parent, text="请选择配对方式",
            font=("Microsoft YaHei UI", 12),
            bg=BODY_BG, fg=TEXT_SECONDARY,
        ).pack(pady=(24, 18))

        # Card 1: LAN QR
        card1 = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, cursor="hand2")
        card1.pack(fill=tk.X, padx=24, pady=(0, 12))
        self._make_card(card1, self._load_icon("qr"), "二维码",
                        "同一 WiFi 下扫码连接，支持自动重连",
                        lambda: self._show_qr_screen())
        self._bind_card_hover(card1)

        # Card 2: Matching code
        card2 = tk.Frame(parent, bg=CARD_BG, highlightbackground=CARD_BORDER,
                         highlightthickness=1, cursor="hand2")
        card2.pack(fill=tk.X, padx=24, pady=(0, 24))
        self._make_card(card2, self._load_icon("key"), "匹配码",
                        "6 位数字码，跨网络也能用",
                        lambda: self._on_matching_code_selected())
        self._bind_card_hover(card2)

        # Bottom status — phone connection state
        tk.Frame(parent, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, padx=24)
        self._mode_status_label = tk.Label(
            parent, text="● 等待手机连接...",
            font=("Microsoft YaHei UI", 9),
            bg=BODY_BG, fg=TEXT_SECONDARY,
        )
        self._mode_status_label.pack(pady=(10, 16))

    def _make_card(
        self, card: tk.Frame, icon: str | ImageTk.PhotoImage, title: str,
        subtitle: str, on_click: Callable,
    ) -> None:
        """Populate a card with icon, title, subtitle, and arrow."""
        inner = tk.Frame(card, bg=CARD_BG, padx=16, pady=14)
        inner.pack(fill=tk.X)
        inner.bind("<Button-1>", lambda e: on_click())

        if isinstance(icon, str):
            tk.Label(inner, text=icon, font=("Segoe UI", 22),
                     bg=CARD_BG).pack(side=tk.LEFT, padx=(0, 14))
        else:
            tk.Label(inner, image=icon, bg=CARD_BG).pack(
                side=tk.LEFT, padx=(0, 14))

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
        for widget in [card, inner, text_col] + \
                      list(inner.children.values()) + \
                      list(text_col.children.values()):
            try:
                widget.bind("<Button-1>", lambda e: on_click())
            except Exception:
                pass

    def _load_icon(self, kind: str) -> ImageTk.PhotoImage:
        """Load a PNG icon from assets/ folder, return PhotoImage.

        Args:
            kind: 'qr' for QR-corner icon, 'key' for key icon.
        """
        import sys
        from PIL import Image

        # Resolve assets path (works both as script and as PyInstaller exe)
        base = getattr(sys, "_MEIPASS", "")
        if not base:
            base = str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent)
        path = f"{base}/assets/{kind}.png"

        img = Image.open(path).resize((28, 28), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        # Store reference to prevent garbage collection
        if kind == "qr":
            self._qr_icon_photo = photo
        else:
            self._key_icon_photo = photo
        return photo

    def _bind_card_hover(self, card: tk.Frame) -> None:
        """Add hover highlight to card background (no layout shift)."""

        def _set_bg(widget: tk.Widget, color: str) -> None:
            try:
                widget.configure(bg=color)
            except Exception:
                pass
            for child in widget.winfo_children():
                _set_bg(child, color)

        def on_enter(e):
            card.configure(highlightbackground=SUCCESS_GREEN)
            _set_bg(card, CARD_HOVER_BG)

        def on_leave(e):
            card.configure(highlightbackground=CARD_BORDER)
            _set_bg(card, CARD_BG)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

    # ------------------------------------------------------------------
    # QR code screen
    # ------------------------------------------------------------------

    def _show_qr_screen(self) -> None:
        """Show the LAN QR code screen."""
        if self._qr_frame is not None:
            self._switch_to(self._qr_frame)

    def _build_qr_body(self, parent: tk.Frame) -> None:
        """Build the QR code screen content."""
        self._build_header(parent, "二维码", show_back=True)

        body = tk.Frame(parent, bg=BODY_BG, padx=20, pady=12)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="扫描二维码完成配对",
                 font=("Microsoft YaHei UI", 11),
                 bg=BODY_BG, fg=TEXT_SECONDARY).pack(pady=(0, 12))

        qr_image = self._generate_qr_image()
        self._photo = ImageTk.PhotoImage(qr_image)
        qr_box = tk.Frame(body, bg=DIVIDER_COLOR, padx=3, pady=3)
        qr_box.pack()
        tk.Label(qr_box, image=self._photo, bg="#FFFFFF").pack()

        info_frame = tk.Frame(body, bg=BODY_BG)
        info_frame.pack(pady=(12, 6))
        tk.Label(info_frame,
                 text=f"{self._lan_host}:{self._lan_port}",
                 font=("Consolas", 11, "bold"),
                 bg=BODY_BG, fg=TEXT_PRIMARY).pack()
        if self._pc_name:
            tk.Label(info_frame, text=self._pc_name,
                     font=("Microsoft YaHei UI", 9),
                     bg=BODY_BG, fg=TEXT_SECONDARY).pack()

        tk.Frame(body, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, pady=(10, 10))
        self._qr_status_label = tk.Label(
            body, text="● 等待手机连接...",
            font=("Microsoft YaHei UI", 9),
            bg=BODY_BG, fg=TEXT_SECONDARY,
        )
        self._qr_status_label.pack()

    # ------------------------------------------------------------------
    # Matching code screen
    # ------------------------------------------------------------------

    def _on_matching_code_selected(self) -> None:
        """User clicked matching code card — generate code + show screen."""
        # If already connected, just show the existing code
        if self._relay_connected and self._matching_code:
            self._show_code_screen()
            return

        # Generate 6-digit code
        self._matching_code = f"{random.randint(100000, 999999):06d}"
        logger.info("Generated matching code: %s", self._matching_code)

        # Update digit blocks with the new code BEFORE raising the screen
        self._refresh_digit_blocks()
        # Reset status to connecting
        if self._status_label is not None:
            self._status_label.configure(
                text="● 正在连接...", fg=TEXT_SECONDARY,
            )
        if self._retry_button is not None:
            self._retry_button.pack_forget()
        self._show_code_screen()

        # Notify main.py to start relay connection
        if self.on_start_relay:
            self.on_start_relay(self._matching_code)

    def _refresh_digit_blocks(self) -> None:
        """Update digit labels with the current matching code."""
        if not self._matching_code or not self._digit_labels:
            return
        for i, ch in enumerate(self._matching_code):
            if i < len(self._digit_labels):
                self._digit_labels[i].configure(text=ch)

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
        self._window.update_idletasks()
        px = self._window.winfo_rootx() + self._window.winfo_width() // 2
        py = self._window.winfo_rooty() + self._window.winfo_height() // 2 + 80
        toast.update_idletasks()
        toast.geometry(f"+{px - toast.winfo_width() // 2}+{py}")
        self._window.after(1800, toast.destroy)

    def _show_code_screen(self) -> None:
        """Show the matching code screen."""
        if self._code_frame is not None:
            self._switch_to(self._code_frame)

    def _build_code_body(self, parent: tk.Frame) -> None:
        """Build the matching code screen content."""
        self._build_header(parent, "匹配码连接", show_back=True)

        body = tk.Frame(parent, bg=BODY_BG, padx=30, pady=30)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="在手机上输入此匹配码",
                 font=("Microsoft YaHei UI", 11),
                 bg=BODY_BG, fg=TEXT_SECONDARY).pack(pady=(0, 36))

        # Code display card — 6 placeholder digit blocks (updated later)
        code_card = tk.Frame(body, bg=CODE_BG, padx=28, pady=28, cursor="hand2")
        code_card.pack()
        code_card.bind("<Button-1>", lambda e: self._copy_matching_code())

        self._digit_frame = tk.Frame(code_card, bg=CODE_BG)
        self._digit_frame.pack()
        self._digit_labels = []
        for _ in range(6):
            block = tk.Frame(
                self._digit_frame, bg=DIGIT_BLOCK_BG,
                highlightbackground=DIGIT_BLOCK_BORDER,
                highlightthickness=1,
                padx=16, pady=12,
                cursor="hand2",
            )
            block.pack(side=tk.LEFT, padx=4)
            lbl = tk.Label(
                block, text="—",
                font=("Consolas", 36, "bold"),
                bg=DIGIT_BLOCK_BG, fg=CODE_COLOR,
                cursor="hand2",
            )
            lbl.pack()
            lbl.bind("<Button-1>", lambda e: self._copy_matching_code())
            block.bind("<Button-1>", lambda e: self._copy_matching_code())
            self._digit_labels.append(lbl)

        tk.Frame(body, bg=DIVIDER_COLOR, height=1).pack(fill=tk.X, pady=(16, 16))

        # Status label
        self._status_label = tk.Label(
            body, text="● 正在连接...",
            font=("Microsoft YaHei UI", 9),
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
        # Not packed until an error occurs

    # ------------------------------------------------------------------
    # Status updates (thread-safe via queue)
    # ------------------------------------------------------------------
    # Worker threads (LAN server, relay) push callbacks to _ui_queue.
    # The main loop poller drains the queue and runs callbacks on the
    # correct tkinter thread.

    def _start_ui_poller(self) -> None:
        """Begin polling the UI queue from the main loop."""
        if self._window is None:
            return

        def _poll():
            try:
                while True:
                    callback = self._ui_queue.get_nowait()
                    try:
                        callback()
                    except Exception:
                        logger.exception("UI callback failed")
            except queue.Empty:
                pass
            if self._window is not None:
                self._window.after(100, _poll)

        self._window.after(100, _poll)

    def update_relay_status(self, status: str) -> None:
        """Thread-safe update of the relay connection status.

        Can be called from any thread.
        """
        status_map = {
            "connecting": ("● 正在连接...", TEXT_SECONDARY),
            "waiting": ("● 等待手机输入匹配码...", TEXT_SECONDARY),
            "connected": ("● 手机已连接 ✓", SUCCESS_GREEN),
        }

        def _update():
            if self._window is None or self._status_label is None:
                return
            if status.startswith("error:"):
                self._relay_connected = False
                msg = status[6:]
                self._status_label.configure(
                    text=f"✗ {msg}", fg=ERR_RED
                )
                if self._retry_button is not None:
                    self._retry_button.pack(pady=(8, 0))
                    self._refit_window()
            else:
                self._relay_connected = (status == "connected")
                text, color = status_map.get(status, (status, TEXT_SECONDARY))
                self._status_label.configure(text=text, fg=color)
                if self._retry_button is not None:
                    self._retry_button.pack_forget()
                    self._refit_window()

        self._ui_queue.put(_update)

    def update_connection_status(self, connected: bool) -> None:
        """Thread-safe update of the phone connection status on all screens.

        Can be called from any thread.
        """
        def _update():
            if self._window is None:
                return
            if connected:
                text = "● 手机已连接 ✓"
                color = SUCCESS_GREEN
            else:
                text = "● 等待手机连接..."
                color = TEXT_SECONDARY

            if self._mode_status_label is not None:
                self._mode_status_label.configure(text=text, fg=color)
            if self._qr_status_label is not None:
                self._qr_status_label.configure(text=text, fg=color)

        self._ui_queue.put(_update)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show the dialog window. Pre-builds all screens for flicker-free switching."""
        if self._window is not None and self._window.winfo_exists():
            self._window.lift()
            self._window.focus_force()
            return

        win = tk.Tk()
        win.title("SMS Sync")
        win.configure(bg=BODY_BG)
        win.resizable(False, False)
        self._window = win

        # ── Single grid container for all screens ──
        self._container = tk.Frame(win, bg=BODY_BG)
        self._container.pack(fill=tk.BOTH, expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        # Pre-build all three frames in the container
        self._mode_frame = tk.Frame(self._container, bg=BODY_BG)
        self._qr_frame = tk.Frame(self._container, bg=BODY_BG)
        self._code_frame = tk.Frame(self._container, bg=BODY_BG)

        # Build screen content
        self._build_mode_screen(self._mode_frame)
        self._build_qr_body(self._qr_frame)
        self._build_code_body(self._code_frame)

        # Grid all frames to establish remembered options, then show mode screen
        for f in (self._mode_frame, self._qr_frame, self._code_frame):
            f.grid(row=0, column=0, sticky="nsew")
        self._switch_to(self._mode_frame)

        def on_close():
            if messagebox.askyesno(
                "退出 SMS Sync", "关闭窗口会退出程序，是否继续？", default="no",
            ):
                win.destroy()
                if self.on_quit:
                    self.on_quit()

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.minsize(WINDOW_WIDTH, 200)
        self._refit_window(first_time=True)
        self._start_ui_poller()

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
            {
                "v": 1, "host": self._lan_host, "port": self._lan_port,
                "token": self._lan_token, "name": self._pc_name,
            },
            ensure_ascii=False,
        )
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10, border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white")
