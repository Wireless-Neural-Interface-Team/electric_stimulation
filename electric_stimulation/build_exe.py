"""
Build a standalone Trigger Generator executable.

Usage:
    python -m electric_stimulation.build_exe
    # or: trigger-generator-build
"""

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent


def main():
    output_dir = Path.cwd() / "dist"
    exe_name = "TriggerGenerator.exe" if sys.platform == "win32" else "TriggerGenerator"
    exe_path = output_dir / exe_name

    if exe_path.exists():
        try:
            exe_path.unlink()
        except PermissionError:
            print("ERROR: The executable is locked (running or in use).")
            print("Close Trigger Generator and try again.")
            sys.exit(1)

    launcher = SCRIPT_DIR / "run_trigger_generator_gui.py"
    hidden = [
        "electric_stimulation",
        "electric_stimulation.gui",
        "electric_stimulation.gui.app",
        "electric_stimulation.gui.main_window",
        "electric_stimulation.gui.style",
        "electric_stimulation.gui.phase_status",
        "electric_stimulation.daq",
        "electric_stimulation.daq.tasks",
        "electric_stimulation.daq.worker",
        "electric_stimulation.waveforms",
        "electric_stimulation.waveforms.classic",
        "electric_stimulation.waveforms.led",
        "electric_stimulation.models",
        "electric_stimulation.timing",
        "electric_stimulation.experiment_io",
        "electric_stimulation.trigger_generator_gui",
        "electric_stimulation.trigger_generator_backend",
        "electric_stimulation.led_pattern",
        "PyQt5",
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "numpy",
        "PyDAQmx",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name=TriggerGenerator",
            "--windowed",
            "--onefile",
            "--clean",
            "--distpath",
            str(output_dir),
            "--specpath",
            tmp,
            "--workpath",
            tmp,
            "--paths",
            str(PACKAGE_ROOT),
        ]
        for mod in hidden:
            cmd.extend(["--hidden-import", mod])
        cmd.append(str(launcher.resolve()))
        subprocess.run(cmd, check=True, cwd=Path.cwd())
    print(f"\nOK: Executable created: {exe_path}")


if __name__ == "__main__":
    main()
