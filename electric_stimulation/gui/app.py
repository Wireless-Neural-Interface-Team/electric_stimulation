# -*- coding: utf-8 -*-
"""Application bootstrap."""

from __future__ import annotations

import sys

from PyQt5.QtCore import QDir, QLockFile
from PyQt5.QtWidgets import QApplication, QMessageBox

from .main_window import TriggerGeneratorWindow
from .style import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Trigger Generator")
    app.setOrganizationName("WNI")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

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
