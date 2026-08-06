# -*- coding: utf-8 -*-
"""Compatibility shim — prefer electric_stimulation.daq / waveforms."""

from .daq import (
    DAQ_AVAILABLE,
    DAQWorker,
    build_channel_path,
    default_daq_device,
    list_daq_devices,
)
from .waveforms import build_led_pattern, led_pattern_dimensions

__all__ = [
    "DAQ_AVAILABLE",
    "DAQWorker",
    "build_channel_path",
    "build_led_pattern",
    "default_daq_device",
    "led_pattern_dimensions",
    "list_daq_devices",
]
