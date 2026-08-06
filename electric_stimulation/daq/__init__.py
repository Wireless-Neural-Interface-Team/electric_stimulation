# -*- coding: utf-8 -*-
"""NI-DAQmx public API.

Important: do not import Qt/worker at module import time — the DAQ child process
must stay Qt-free or it can hang under a frozen --windowed build.
"""

from __future__ import annotations

from .devices import (
    DAQ_AVAILABLE,
    build_channel_path,
    default_daq_device,
    device_name_from_path,
    format_daq_error,
    list_daq_devices,
    nidaq,
    reset_daq_device,
)
from .tasks import start_ao_output, stop_clear_task, warm_up_daqmx

__all__ = [
    "DAQ_AVAILABLE",
    "DAQWorker",
    "build_channel_path",
    "default_daq_device",
    "device_name_from_path",
    "format_daq_error",
    "list_daq_devices",
    "nidaq",
    "reset_daq_device",
    "start_ao_output",
    "stop_clear_task",
    "warm_up_daqmx",
]


def __getattr__(name: str):
    if name == "DAQWorker":
        from .worker import DAQWorker

        return DAQWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
