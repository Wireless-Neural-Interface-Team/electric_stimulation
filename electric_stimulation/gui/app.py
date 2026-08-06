# -*- coding: utf-8 -*-
"""Application bootstrap."""

from __future__ import annotations

import os
import sys

from PyQt5.QtCore import QDir, QLockFile
from PyQt5.QtWidgets import QApplication, QMessageBox

from .main_window import TriggerGeneratorWindow
from .style import APP_STYLESHEET


def _fix_stdio() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def main() -> int:
    _fix_stdio()

    app = QApplication(sys.argv)
    app.setApplicationName("Trigger Generator")
    app.setOrganizationName("WNI")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    # Device discovery only — full AO runs in a child process.
    try:
        from ..daq import list_daq_devices

        list_daq_devices()
    except Exception:
        pass

    lock_path = QDir.temp().absoluteFilePath(
        "electric_stimulation_trigger_generator.lock"
    )
    lock = QLockFile(lock_path)
    lock.setStaleLockTime(30_000)
    if not lock.tryLock(100):
        QMessageBox.critical(
            None,
            "Trigger Generator",
            "Trigger Generator is already running.\n\n"
            "Close the other window first — two instances block the NI device.",
        )
        return 1
    app._instance_lock = lock  # keep lock for process lifetime

    window = TriggerGeneratorWindow()
    window.show()
    return app.exec_()
