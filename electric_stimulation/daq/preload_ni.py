# -*- coding: utf-8 -*-
"""Preload system nicaiu.dll before PyDAQmx (critical for PyInstaller)."""

from __future__ import annotations

import os
import sys


def preload_nicaiu() -> str | None:
    """
    Force-load the system NI-DAQmx DLL with an absolute path.

    PyInstaller's ctypes hook can make LoadLibrary('nicaiu') hang or bind the
    wrong search path inside a frozen exe. Loading System32\\nicaiu.dll first
    fixes AO start hanging after 'arming'.
    """
    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nicaiu.dll"),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            r"National Instruments\Shared\ExternalCompilerSupport\C\lib64\msvc\nicaiu.dll",
        ),
    ]
    try:
        import ctypes

        # Prefer the real Windows DLL directory (ignore WOW64 redirection issues).
        try:
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass

        for path in candidates:
            if not os.path.isfile(path):
                continue
            try:
                ctypes.WinDLL(path)
                return path
            except Exception:
                continue
        # Last resort: name-only load (works under plain Python).
        ctypes.WinDLL("nicaiu")
        return "nicaiu"
    except Exception:
        return None


# Run on import when frozen, before PyDAQmx is loaded by devices.py.
if getattr(sys, "frozen", False):
    preload_nicaiu()
