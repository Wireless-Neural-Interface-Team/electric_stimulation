"""
Script to build a standalone executable for Trigger Generator.

Usage:
    python build_exe.py
    # or: python -m build_exe (from project root)

Prerequisites:
    pip install -r requirements.txt pyinstaller

The executable will be generated in dist/ (in the current directory).
"""

import subprocess
import sys
from pathlib import Path
import tempfile
import importlib

SCRIPT_DIR = Path(__file__).resolve().parent


def _can_import_pydaqmx():
    """
    Return True only if PyDAQmx can be imported in current environment.
    NI-DAQmx runtime is a system dependency and may be missing on build machines.
    """
    try:
        importlib.import_module("PyDAQmx")
        return True
    except Exception:
        return False


def main():
    output_dir = Path.cwd() / "dist"
    exe_name = "TriggerGenerator.exe" if sys.platform == "win32" else "TriggerGenerator"
    exe_path = output_dir / exe_name

    if exe_path.exists():
        try:
            exe_path.unlink()
        except PermissionError:
            print("ERROR: The executable is locked (running or in use by another program).")
            print("Close Trigger Generator and try again.")
            sys.exit(1)

    launcher = SCRIPT_DIR / "run_trigger_generator_gui.py"
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name=TriggerGenerator",
            "--windowed",
            "--onefile",
            "--clean",
            "--distpath", str(output_dir),
            "--specpath", tmp,
            "--workpath", tmp,
            "--hidden-import=PyQt5",
            "--hidden-import=PyQt5.QtCore",
            "--hidden-import=PyQt5.QtGui",
            "--hidden-import=PyQt5.QtWidgets",
            "--hidden-import=numpy",
            str(launcher.resolve()),
        ]
        if _can_import_pydaqmx():
            cmd.append("--hidden-import=PyDAQmx")
        else:
            print("WARNING: PyDAQmx/NI-DAQmx not available during build; DAQ will be unavailable at runtime.")
        subprocess.run(cmd, check=True, cwd=Path.cwd())
    print(f"\nExecutable created: {exe_path}")


if __name__ == "__main__":
    main()
