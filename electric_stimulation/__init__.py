# -*- coding: utf-8 -*-
"""
Electric Stimulation — NI-DAQmx trigger generator for electrical stimulation.
"""

from .daq import (
    DAQ_AVAILABLE,
    DAQWorker,
    build_channel_path,
    default_daq_device,
    list_daq_devices,
)
from .gui import TriggerGeneratorWindow, main
from .models import GenerationConfig
from .waveforms import build_classic_cycle, build_led_pattern, led_pattern_dimensions

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
__version__ = "0.4.0"
