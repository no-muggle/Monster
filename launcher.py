"""Entry point for PyInstaller packaged exe.

Imports from src/ and launches the SMS Sync server.
Separate from src/main.py to avoid relative import issues when frozen.
"""

from src.main import main

if __name__ == "__main__":
    main()
