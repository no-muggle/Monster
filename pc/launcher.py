"""Entry point for PyInstaller packaged exe.

Imports from src/ and launches the SMS Sync server.
Separate from src/main.py to avoid relative import issues when frozen.
"""

import ctypes
import sys

if sys.platform == "win32":
    # Set AppUserModelID BEFORE any GUI/COM init so Windows Toast shows our name
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SMS Sync")

from src.main import main

if __name__ == "__main__":
    main()
