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
from .trigger_generator_backend import (
    DAQ_AVAILABLE,
    DAQWorker,
    build_channel_path,
)
from .trigger_generator_gui import TriggerGeneratorWindow, main

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
