"""PyInstaller entry point - a plain script outside the package, since
PyInstaller runs its entry script standalone and relative imports (as used
by transcript_app/__main__.py) don't work in that context."""
from transcript_app.app import main

if __name__ == "__main__":
    main()
