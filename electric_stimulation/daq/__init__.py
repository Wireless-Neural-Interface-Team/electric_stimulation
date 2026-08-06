# -*- coding: utf-8 -*-
"""NI-DAQmx device discovery and public DAQ API."""

from __future__ import annotations

from typing import List

try:
    import PyDAQmx as nidaq

    DAQ_AVAILABLE = True
except ImportError:
    nidaq = None  # type: ignore[assignment]
    DAQ_AVAILABLE = False


def build_channel_path(device_str: str, channel_str: str) -> str:
    """Dev1 + ao0 → Dev1/ao0."""
    dev = (device_str or "").strip() or "Dev1"
    ch = (channel_str or "").strip() or "ao0"
    return f"{dev}/{ch}"


def list_daq_devices() -> List[str]:
    if not DAQ_AVAILABLE:
        return []
    try:
        buf = nidaq.create_string_buffer(4096)
        nidaq.DAQmxGetSysDevNames(buf, 4096)
        raw = (
            buf.value.decode("utf-8", errors="replace")
            if isinstance(buf.value, bytes)
            else str(buf.value)
        )
        return [d.strip() for d in raw.split(",") if d.strip()]
    except Exception:
        return []


def default_daq_device() -> str:
    devices = list_daq_devices()
    return devices[0] if devices else "Dev1"


def device_name_from_path(device_path: str) -> str:
    return (device_path or "").split("/", 1)[0]


def reset_daq_device(device_path: str) -> bool:
    name = device_name_from_path(device_path)
    if not DAQ_AVAILABLE or not name:
        return False
    try:
        nidaq.DAQmxResetDevice(name)
        return True
    except Exception:
        return False


def format_daq_error(exc: BaseException, device_path: str) -> str:
    msg = str(exc).strip() or repr(exc)
    devices = list_daq_devices()
    device_name = device_name_from_path(device_path)
    lower = msg.lower()

    if "access violation" in lower or "null pointer" in lower:
        return (
            "NI-DAQmx crashed while accessing the hardware (null pointer).\n\n"
            f"Requested channel: {device_path}\n"
            f"Devices detected: {', '.join(devices) if devices else '(none)'}\n\n"
            "Typical fixes:\n"
            "- Use a device listed above (often Dev1)\n"
            "- Close other Trigger Generator / NI-MAX sessions\n"
            "- Unplug/replug the NI device, then retry"
        )
    if "reserved" in lower:
        return (
            f"{msg}\n\n"
            "The AO channel is already in use.\n"
            "Close other Trigger Generator windows and NI-MAX tasks, then retry."
        )
    if device_name and devices and device_name not in devices:
        return (
            f"{msg}\n\n"
            f"Requested device '{device_name}' was not found.\n"
            f"Available device(s): {', '.join(devices)}"
        )
    if devices:
        return f"{msg}\n\nAvailable device(s): {', '.join(devices)}"
    return msg


from .tasks import start_ao_output, stop_clear_task  # noqa: E402
from .worker import DAQWorker  # noqa: E402

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
]
