# -*- coding: utf-8 -*-
"""NI-DAQmx device discovery (ctypes nicaiu — safe for frozen exes)."""

from __future__ import annotations

from typing import List

from . import nicaiu

DAQ_AVAILABLE = nicaiu.is_available()
nidaq = None  # legacy alias; prefer nicaiu module


def build_channel_path(device_str: str, channel_str: str) -> str:
    """Dev1 + ao0 → Dev1/ao0."""
    dev = (device_str or "").strip() or "Dev1"
    ch = (channel_str or "").strip() or "ao0"
    return f"{dev}/{ch}"


def list_daq_devices() -> List[str]:
    if not nicaiu.is_available():
        return []
    try:
        return nicaiu.list_devices()
    except Exception:
        return []


def default_daq_device() -> str:
    devices = list_daq_devices()
    return devices[0] if devices else "Dev1"


def device_name_from_path(device_path: str) -> str:
    return (device_path or "").split("/", 1)[0]


def reset_daq_device(device_path: str) -> bool:
    name = device_name_from_path(device_path)
    if not nicaiu.is_available() or not name:
        return False
    try:
        nicaiu.reset_device(name)
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
