"""
Build Trigger Generator GUI executable (onedir).

DAQ generation is launched via a real Python interpreter when available
(TG_DAQ_PYTHON / si_env), because PyInstaller freezes DAQmxCreateTask.

Usage:
    python -m electric_stimulation.build_exe
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = SCRIPT_DIR.parent


def main():
    output_dir = Path.cwd() / "dist"
    app_dir = output_dir / "TriggerGenerator"
    exe_name = "TriggerGenerator.exe" if sys.platform == "win32" else "TriggerGenerator"

    legacy_onefile = output_dir / exe_name
    if legacy_onefile.exists():
        try:
            legacy_onefile.unlink()
        except PermissionError:
            print("ERROR: dist/TriggerGenerator.exe is locked (still running).")
            sys.exit(1)
    if app_dir.exists():
        try:
            shutil.rmtree(app_dir)
        except PermissionError:
            print("ERROR: dist/TriggerGenerator/ is locked (still running).")
            print("Close Trigger Generator and try again.")
            sys.exit(1)

    gui_launcher = SCRIPT_DIR / "run_trigger_generator_gui.py"
    hidden = [
        "electric_stimulation",
        "electric_stimulation.gui",
        "electric_stimulation.gui.app",
        "electric_stimulation.gui.main_window",
        "electric_stimulation.gui.style",
        "electric_stimulation.gui.phase_status",
        "electric_stimulation.daq",
        "electric_stimulation.daq.tasks",
        "electric_stimulation.daq.devices",
        "electric_stimulation.daq.nicaiu",
        "electric_stimulation.daq.worker",
        "electric_stimulation.daq.session_runner",
        "electric_stimulation.daq.cli_session",
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
    ]

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--name=TriggerGenerator",
            "--windowed",
            "--onedir",
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
        cmd.append(str(gui_launcher.resolve()))
        subprocess.run(cmd, check=True, cwd=Path.cwd())

    # Helper script so the GUI can find the DAQ Python easily on this machine.
    helper = app_dir / "daq_python.txt"
    si_python = PACKAGE_ROOT / "si_env" / "Scripts" / "python.exe"
    if si_python.is_file():
        helper.write_text(str(si_python.resolve()), encoding="utf-8")

    print(f"\nOK: Executable created: {app_dir / exe_name}")
    if helper.exists():
        print(f"OK: DAQ python hint: {helper}")
    print("Keep the whole TriggerGenerator folder together.")
    print("DAQ uses a real Python (si_env) — required because NI CreateTask hangs in frozen exes.")


if __name__ == "__main__":
    main()
