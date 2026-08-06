# -*- coding: utf-8 -*-
"""
Electric Stimulation — NI-DAQmx trigger generator for electrical stimulation.

Keep this module light: the frozen DAQ child imports through this package and
must not pull PyQt5 at import time.
"""

from __future__ import annotations

__all__ = [
    "DAQ_AVAILABLE",
    "DAQWorker",
    "GenerationConfig",
    "TriggerGeneratorWindow",
    "build_channel_path",
    "build_classic_cycle",
    "build_led_pattern",
    "default_daq_device",
    "led_pattern_dimensions",
    "list_daq_devices",
    "main",
]
__version__ = "0.5.4"


def __getattr__(name: str):
    if name in {
        "DAQ_AVAILABLE",
        "DAQWorker",
        "build_channel_path",
        "default_daq_device",
        "list_daq_devices",
    }:
        from . import daq as _daq

        return getattr(_daq, name)
    if name == "GenerationConfig":
        from .models import GenerationConfig

        return GenerationConfig
    if name in {"build_classic_cycle", "build_led_pattern", "led_pattern_dimensions"}:
        from . import waveforms as _wf

        return getattr(_wf, name)
    if name in {"TriggerGeneratorWindow", "main"}:
        from . import gui as _gui

        return getattr(_gui, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
