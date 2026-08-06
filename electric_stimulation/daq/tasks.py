# -*- coding: utf-8 -*-
"""Low-level AO task create / write / stop with USB-600x recovery."""

from __future__ import annotations

import threading
from ctypes import byref, c_int32
from typing import Optional

import numpy as np

try:
    import PyDAQmx as nidaq

    _DAQ = True
except ImportError:
    nidaq = None  # type: ignore[assignment]
    _DAQ = False

from . import reset_daq_device  # circular? use local import inside functions for reset

_AO_MIN_V = -10.0
_AO_MAX_V = 10.0


def _daq_ok() -> bool:
    return _DAQ


def _is_recoverable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "access violation" in msg
        or "reserved" in msg
        or "null pointer" in msg
        or isinstance(exc, TimeoutError)
    )


def stop_clear_task(task, timeout_s: float = 0.5) -> None:
    if task is None:
        return

    def _work():
        try:
            task.StopTask()
        except Exception:
            pass
        try:
            task.ClearTask()
        except Exception:
            pass

    th = threading.Thread(target=_work, daemon=True)
    th.start()
    th.join(timeout=timeout_s)


def create_nidaq_task(device_path: str, timeout_s: float = 1.0):
    if not _DAQ:
        raise RuntimeError("PyDAQmx is not installed.")
    from . import reset_daq_device as _reset

    last_exc: Optional[BaseException] = None
    for attempt in range(2):
        box: dict = {}

        def _build():
            try:
                box["task"] = nidaq.Task()
            except Exception as e:
                box["err"] = e

        th = threading.Thread(target=_build, daemon=True)
        th.start()
        th.join(timeout=timeout_s)
        if th.is_alive():
            _reset(device_path)
            last_exc = TimeoutError(
                "NI-DAQmx Task() hung — device was reset. Retry Start."
            )
            continue
        if "err" in box:
            last_exc = box["err"]
            if attempt == 0 and _is_recoverable(box["err"]):
                _reset(device_path)
                continue
            raise box["err"]
        return box["task"]
    raise last_exc  # type: ignore[misc]


def start_ao_output(
    device_path: str,
    sampling_rate: float,
    data: np.ndarray,
    continuous: bool,
):
    if not _DAQ:
        raise RuntimeError("PyDAQmx is not installed.")
    from . import reset_daq_device as _reset

    data = np.ascontiguousarray(data, dtype=np.float64)
    nb = int(data.size)
    if nb < 1:
        raise ValueError("AO buffer is empty.")
    mode = nidaq.DAQmx_Val_ContSamps if continuous else nidaq.DAQmx_Val_FiniteSamps
    last_exc: Optional[BaseException] = None
    for attempt in range(2):
        task = None
        try:
            task = create_nidaq_task(device_path)
            task.CreateAOVoltageChan(
                device_path, None, _AO_MIN_V, _AO_MAX_V, nidaq.DAQmx_Val_Volts, None
            )
            task.CfgSampClkTiming(
                "", sampling_rate, nidaq.DAQmx_Val_Rising, mode, nb
            )
            read = c_int32()
            task.WriteAnalogF64(
                nb, False, 10, nidaq.DAQmx_Val_GroupByScanNumber, data, byref(read), None
            )
            task.StartTask()
            return task
        except Exception as e:
            stop_clear_task(task)
            last_exc = e
            if attempt == 0 and _is_recoverable(e):
                _reset(device_path)
                continue
            raise
    raise last_exc  # type: ignore[misc]
