# -*- coding: utf-8 -*-
"""
Electric Stimulation - NI-DAQmx trigger generator for electrical stimulation.

Modules:
- trigger_generator_backend: DAQWorker, build_channel_path, re-exports LED helpers
- led_pattern: build_led_pattern, led_pattern_dimensions (NumPy only)
- experiment_io: JSON record builders for saved runs
- trigger_generator_gui: TriggerGeneratorWindow, main()
"""

from .led_pattern import build_led_pattern, led_pattern_dimensions

__all__ = [
    "DAQ_AVAILABLE",
    "DAQWorker",
    "TriggerGeneratorWindow",
    "build_channel_path",
    "build_led_pattern",
    "led_pattern_dimensions",
    "main",
]
__version__ = "0.1.0"


def __getattr__(name):
    """Lazy imports to keep package import side-effect free."""
    if name in {"DAQ_AVAILABLE", "DAQWorker", "build_channel_path"}:
        from .trigger_generator_backend import DAQ_AVAILABLE, DAQWorker, build_channel_path

        return {
            "DAQ_AVAILABLE": DAQ_AVAILABLE,
            "DAQWorker": DAQWorker,
            "build_channel_path": build_channel_path,
        }[name]

    if name in {"TriggerGeneratorWindow", "main"}:
        from .trigger_generator_gui import TriggerGeneratorWindow, main

        return {
            "TriggerGeneratorWindow": TriggerGeneratorWindow,
            "main": main,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
