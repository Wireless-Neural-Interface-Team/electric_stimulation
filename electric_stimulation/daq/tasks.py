# -*- coding: utf-8 -*-
"""Low-level AO task create / write / stop via ctypes nicaiu.dll."""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import nicaiu
from .devices import reset_daq_device as _reset

_AO_MIN_V = -10.0
_AO_MAX_V = 10.0


def _is_recoverable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "access violation" in msg
        or "reserved" in msg
        or "null pointer" in msg
    )


def stop_clear_task(task, timeout_s: float = 0.5) -> None:
    del timeout_s
    if task is None:
        return
    try:
        task.stop()
    except Exception:
        pass
    try:
        task.clear()
    except Exception:
        pass


def create_nidaq_task(device_path: str, name: str = "TriggerGeneratorAO"):
    if not nicaiu.is_available():
        raise RuntimeError(f"nicaiu.dll not available ({nicaiu.load_info()})")
    last_exc: Optional[BaseException] = None
    for attempt in range(2):
        task = None
        try:
            task = nicaiu.AoTask(name=f"{name}_{attempt}")
            return task
        except Exception as e:
            last_exc = e
            stop_clear_task(task)
            if attempt == 0 and _is_recoverable(e):
                _reset(device_path)
                continue
            raise
    raise last_exc  # type: ignore[misc]


def start_ao_output(
    device_path: str,
    sampling_rate: float,
    data: np.ndarray,
    continuous: bool,
    on_task_created=None,
    on_progress=None,
):
    if not nicaiu.is_available():
        raise RuntimeError(f"nicaiu.dll not available ({nicaiu.load_info()})")

    def _prog(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    data = np.ascontiguousarray(data, dtype=np.float64)
    nb = int(data.size)
    if nb < 1:
        raise ValueError("AO buffer is empty.")
    mode = nicaiu.DAQmx_Val_ContSamps if continuous else nicaiu.DAQmx_Val_FiniteSamps
    last_exc: Optional[BaseException] = None
    for attempt in range(2):
        task = None
        try:
            _prog(f"CreateTask attempt={attempt}")
            task = create_nidaq_task(device_path)
            if on_task_created is not None:
                on_task_created(task)
            _prog("CreateAOVoltageChan")
            task.create_ao_voltage_chan(device_path, _AO_MIN_V, _AO_MAX_V)
            _prog("CfgSampClkTiming")
            task.cfg_samp_clk(float(sampling_rate), mode, nb)
            if continuous:
                task.allow_regen()
            _prog("WriteAnalogF64")
            task.write_f64(data)
            _prog("StartTask")
            task.start()
            _prog("StartTask done")
            return task
        except Exception as e:
            if on_task_created is not None:
                on_task_created(None)
            stop_clear_task(task)
            last_exc = e
            if attempt == 0 and _is_recoverable(e):
                _reset(device_path)
                continue
            raise
    raise last_exc  # type: ignore[misc]


def warm_up_daqmx() -> None:
    if not nicaiu.is_available():
        return
    try:
        nicaiu.list_devices()
    except Exception:
        pass
    task = None
    try:
        task = nicaiu.AoTask(name="TriggerGeneratorWarmup")
    except Exception:
        task = None
    finally:
        stop_clear_task(task)
