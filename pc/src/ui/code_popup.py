"""Custom popup window for received verification codes.

Dark-themed floating popup positioned at bottom-right.
Auto-closes after 7 seconds; click to dismiss.
"""

from __future__ import annotations

import tkinter as tk

# Dark theme colors
BG = "#1E1E2E"
CARD = "#2A2A3E"
ACCENT = "#7C5CFC"
TEXT = "#E0E0E0"
SUBTEXT = "#8888A0"
GREEN = "#4CAF50"
BORDER = "#3A3A50"


def show_code_popup(code: str, sender: str) -> None:
    root = tk.Tk()
    root.title("验证码")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.overrideredirect(True)

    # Rounded-corner effect via border
    outer = tk.Frame(root, bg=BORDER, padx=1, pady=1)
    outer.pack()

    inner = tk.Frame(outer, bg=CARD, padx=32, pady=24)
    inner.pack()

    # Header
    tk.Label(
        inner, text="📨 收到验证码",
        font=("Segoe UI", 9), bg=CARD, fg=SUBTEXT,
    ).pack(anchor="w")

    # Code in large, centered, accented text
    tk.Label(
        inner, text=code,
        font=("Consolas", 40, "bold"), bg=CARD, fg=ACCENT,
    ).pack(pady=(8, 4))

    # Sender
    tk.Label(
        inner, text=f"发送方: {sender}",
        font=("Microsoft YaHei UI", 10), bg=CARD, fg=SUBTEXT,
    ).pack(pady=(0, 16))

    # Copy button
    def do_copy(e=None):
        import pyperclip
        pyperclip.copy(code)
        copy_btn.configure(text="✓ 已复制", fg=GREEN)

    copy_btn = tk.Label(
        inner, text="📋 复制验证码",
        font=("Microsoft YaHei UI", 10, "bold"),
        bg=ACCENT, fg="#FFFFFF", padx=28, pady=10, cursor="hand2",
    )
    copy_btn.pack()
    copy_btn.bind("<Button-1>", do_copy)

    root.bind("<Button-1>", lambda e: root.destroy())
    root.after(7000, root.destroy)

    # Position: bottom-right corner
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"+{sw-w-20}+{sh-h-60}")

    root.lift()
    root.focus_force()
    root.attributes("-topmost", True)
    root.mainloop()
