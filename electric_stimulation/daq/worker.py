# -*- coding: utf-8 -*-
"""
DAQ controller: GUI launches a child process that owns NI-DAQmx on its main thread.

Status/stop use temp files (reliable with PyInstaller --windowed, unlike stdout pipes).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from ..models import GenerationConfig

# If the child never reports boot/started, unlock the UI with an error.
_STARTUP_TIMEOUT_MS = 20000


def build_daq_process_command(
    config_path: Path, stop_path: Path, status_path: Path
) -> list[str]:
    """Prefer a real Python interpreter for DAQ (PyInstaller freezes DAQmxCreateTask)."""
    cfg, stop, status = str(config_path), str(stop_path), str(status_path)
    args_mod = [
        "-m",
        "electric_stimulation.daq.cli_session",
        "--config",
        cfg,
        "--stop-file",
        stop,
        "--status-file",
        status,
    ]

    if not getattr(sys, "frozen", False):
        return [sys.executable, *args_mod]

    # Frozen GUI: try a non-frozen Python that can import this package.
    for py in _candidate_pythons():
        return [str(py), *args_mod]

    # Last resort: same frozen exe (often hangs on CreateTask on some PCs).
    exe_dir = Path(sys.executable).resolve().parent
    daq_exe = exe_dir / (
        "TriggerGeneratorDAQ.exe" if sys.platform == "win32" else "TriggerGeneratorDAQ"
    )
    if daq_exe.is_file():
        return [
            str(daq_exe),
            "--config",
            cfg,
            "--stop-file",
            stop,
            "--status-file",
            status,
        ]
    return [
        sys.executable,
        "--daq-session",
        "--config",
        cfg,
        "--stop-file",
        stop,
        "--status-file",
        status,
    ]


def _candidate_pythons() -> list[Path]:
    from shutil import which

    out: list[Path] = []
    env = os.environ.get("TG_DAQ_PYTHON", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            out.append(p)

    exe_dir = Path(sys.executable).resolve().parent
    hint = exe_dir / "daq_python.txt"
    if hint.is_file():
        try:
            p = Path(hint.read_text(encoding="utf-8").strip())
            if p.is_file():
                out.append(p)
        except Exception:
            pass

    for rel in (
        Path("si_env") / "Scripts" / "python.exe",
        Path("..") / "si_env" / "Scripts" / "python.exe",
        Path("..") / ".." / "si_env" / "Scripts" / "python.exe",
        Path("venv") / "Scripts" / "python.exe",
        Path("..") / ".." / "venv" / "Scripts" / "python.exe",
    ):
        p = (exe_dir / rel).resolve()
        if p.is_file():
            out.append(p)

    for name in ("python.exe", "python"):
        w = which(name)
        if w:
            out.append(Path(w))

    seen = set()
    uniq: list[Path] = []
    frozen_exe = Path(sys.executable).resolve()
    for p in out:
        rp = p.resolve()
        if rp == frozen_exe or rp in seen:
            continue
        # Windows Store python stub is not a real interpreter.
        if "WindowsApps" in str(rp):
            continue
        seen.add(rp)
        uniq.append(rp)
    return uniq


def _repo_root_for_pythonpath() -> Path | None:
    exe_dir = Path(sys.executable).resolve().parent
    for up in [exe_dir, *exe_dir.parents]:
        if (up / "electric_stimulation" / "daq" / "cli_session.py").is_file():
            return up
    return None


class DAQWorker(QObject):
    generation_started = pyqtSignal()
    generation_finished = pyqtSignal()
    generation_error = pyqtSignal(str)

    def __init__(self, config: GenerationConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._process: QProcess | None = None
        self._config_path: Path | None = None
        self._stop_path: Path | None = None
        self._status_path: Path | None = None
        self._running = False
        self._started_emitted = False
        self._boot_seen = False
        self._finished_emitted = False
        self._error_emitted = False
        self._status_offset = 0
        self._poll = QTimer(self)
        self._poll.setInterval(50)
        self._poll.timeout.connect(self._poll_status)
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self._on_startup_timeout)

    def isRunning(self) -> bool:
        return self._running

    def wait(self, msecs: int = 5000) -> bool:
        if self._process is None:
            return True
        return self._process.waitForFinished(msecs)

    def start(self) -> None:
        if self._running:
            return
        self._finished_emitted = False
        self._started_emitted = False
        self._boot_seen = False
        self._error_emitted = False
        self._status_offset = 0

        tmp = Path(tempfile.gettempdir())
        token = uuid.uuid4().hex
        self._config_path = tmp / f"tg_daq_cfg_{token}.json"
        self._stop_path = tmp / f"tg_daq_stop_{token}.flag"
        self._status_path = tmp / f"tg_daq_status_{token}.jsonl"
        for p in (self._stop_path, self._status_path):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        self._config_path.write_text(
            json.dumps(self.config.to_dict(), indent=2), encoding="utf-8"
        )
        self._status_path.write_text("", encoding="utf-8")

        cmd = build_daq_process_command(
            self._config_path, self._stop_path, self._status_path
        )
        self._running = True
        if not self._launch(cmd):
            # WDAC/AppLocker may block TriggerGeneratorDAQ.exe — fall back.
            if getattr(sys, "frozen", False) and "TriggerGeneratorDAQ" in cmd[0]:
                fallback = [
                    sys.executable,
                    "--daq-session",
                    "--config",
                    str(self._config_path),
                    "--stop-file",
                    str(self._stop_path),
                    "--status-file",
                    str(self._status_path),
                ]
                if not self._launch(fallback):
                    err = self._process.errorString() if self._process else "unknown"
                    self._running = False
                    self._poll.stop()
                    self._startup_timer.stop()
                    self._cleanup_files()
                    self._error_emitted = True
                    self.generation_error.emit(f"Failed to start DAQ process:\n{err}")
                    self._emit_finished()
                    return
            else:
                err = self._process.errorString() if self._process else "unknown"
                self._running = False
                self._poll.stop()
                self._startup_timer.stop()
                self._cleanup_files()
                self._error_emitted = True
                self.generation_error.emit(f"Failed to start DAQ process:\n{err}")
                self._emit_finished()
                return
        self._poll.start()
        self._startup_timer.start(_STARTUP_TIMEOUT_MS)

    def _launch(self, cmd: list[str]) -> bool:
        if self._process is not None:
            try:
                self._process.finished.disconnect(self._on_process_finished)
            except Exception:
                pass
            try:
                self._process.errorOccurred.disconnect(self._on_process_error)
            except Exception:
                pass
        self._process = QProcess(self)
        self._process.setStandardOutputFile(QProcess.nullDevice())
        self._process.setStandardErrorFile(QProcess.nullDevice())
        exe_dir = str(Path(cmd[0]).resolve().parent)
        self._process.setWorkingDirectory(exe_dir)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("TG_DAQ_SESSION", "1")
        repo = _repo_root_for_pythonpath()
        if repo is not None:
            existing = env.value("PYTHONPATH", "")
            env.insert(
                "PYTHONPATH",
                str(repo) if not existing else str(repo) + os.pathsep + existing,
            )
            if "python" in Path(cmd[0]).name.lower():
                self._process.setWorkingDirectory(str(repo))
        self._process.setProcessEnvironment(env)
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        program, *args = cmd
        self._process.start(program, args)
        return self._process.waitForStarted(20000)

    def stop(self) -> None:
        if self._stop_path is not None:
            try:
                self._stop_path.write_text("stop", encoding="utf-8")
            except Exception:
                pass
        QTimer.singleShot(4000, self._force_kill)

    def _force_kill(self) -> None:
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self._process.kill()

    def _on_startup_timeout(self) -> None:
        if not self._running or self._started_emitted or self._error_emitted:
            return
        alive = (
            self._process is not None
            and self._process.state() != QProcess.NotRunning
        )
        detail = "boot seen" if self._boot_seen else "no boot event (child stuck before DAQ)"
        self._error_emitted = True
        self.generation_error.emit(
            "DAQ child process did not start output in time.\n"
            f"({detail}; process {'still running' if alive else 'exited'})\n\n"
            "Close every Trigger Generator window, unplug/replug the NI device if needed, "
            "then retry."
        )
        self._force_kill()

    def _poll_status(self) -> None:
        if self._status_path is None:
            return
        try:
            data = self._status_path.read_text(encoding="utf-8")
        except Exception:
            return
        if len(data) <= self._status_offset:
            return
        chunk = data[self._status_offset :]
        self._status_offset = len(data)
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except Exception:
                continue
            kind = evt.get("event")
            if kind == "boot":
                self._boot_seen = True
            elif kind in ("arming", "boot"):
                self._boot_seen = True
            elif kind == "started" and not self._started_emitted:
                self._startup_timer.stop()
                self._started_emitted = True
                self.generation_started.emit()
            elif kind == "error" and not self._error_emitted:
                self._startup_timer.stop()
                self._error_emitted = True
                self.generation_error.emit(
                    str(evt.get("message") or "Unknown DAQ error")
                )

    def _on_process_error(self, _error) -> None:
        if not self._running:
            return
        if self._process is not None and self._process.state() == QProcess.NotRunning:
            err = self._process.errorString()
            if err and not self._error_emitted and not self._finished_emitted:
                self._error_emitted = True
                self.generation_error.emit(f"DAQ process error:\n{err}")

    def _on_process_finished(self, exit_code: int, _status) -> None:
        self._poll.stop()
        self._startup_timer.stop()
        self._running = False
        self._poll_status()
        if (
            exit_code not in (0, None)
            and not self._error_emitted
            and not self._started_emitted
        ):
            self._error_emitted = True
            self.generation_error.emit(f"DAQ process exited with code {exit_code}")
        self._cleanup_files()
        self._emit_finished()

    def _emit_finished(self) -> None:
        if self._finished_emitted:
            return
        self._finished_emitted = True
        self.generation_finished.emit()

    def _cleanup_files(self) -> None:
        for p in (self._config_path, self._stop_path, self._status_path):
            if p is None:
                continue
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass
