"""PyInstaller entry point - a plain script outside the package, since
PyInstaller runs its entry script standalone and relative imports (as used
by transcript_app/__main__.py) don't work in that context."""
import multiprocessing
import os
import sys

if __name__ == "__main__":
    # The packaged app is a windowed (console=False) app with no visible
    # stdout/stderr, even when launched from a terminal with output
    # redirected - so print() has nowhere to go and everything is silently
    # lost, making problems impossible to diagnose. Redirect to a real log
    # file instead, so both us and real users can check what happened.
    _log_dir = os.path.expanduser("~/Library/Logs/VoxType")
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = open(os.path.join(_log_dir, "voxtype.log"), "a", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file

    # Without this, the packaged app spawns a runaway chain of
    # multiprocessing.resource_tracker child processes (each one, on
    # relaunching this same frozen executable, thinks no tracker exists yet
    # and spawns another) - confirmed via `ps -o pid,ppid` showing a straight
    # parent-child chain that grew without bound. freeze_support() makes the
    # frozen executable correctly recognize multiprocessing re-exec calls
    # instead of re-running the whole app each time. Must be the very first
    # thing that runs, before any other imports.
    multiprocessing.freeze_support()

    from transcript_app.app import main

    main()
