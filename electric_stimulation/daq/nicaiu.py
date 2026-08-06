# -*- coding: utf-8 -*-
"""
Direct ctypes bindings to System32\\nicaiu.dll.

PyDAQmx's DAQmxCreateTask hangs inside PyInstaller-frozen processes even when
GetSysDevNames works. Calling the system DLL with an absolute path fixes AO.
"""

from __future__ import annotations

import os
from ctypes import (
    POINTER,
    WinDLL,
    byref,
    c_char_p,
    c_double,
    c_int32,
    c_uint32,
    c_uint64,
    c_void_p,
    create_string_buffer,
    windll,
)
from typing import List, Optional

import numpy as np

# NI-DAQmx ANSI C constants (NIDAQmx.h)
DAQmx_Val_Volts = 10348
DAQmx_Val_Rising = 10280
DAQmx_Val_FiniteSamps = 10178
DAQmx_Val_ContSamps = 10123
DAQmx_Val_GroupByScanNumber = 1
DAQmx_Val_AllowRegen = 10097

TaskHandle = c_void_p

_dll = None
_AVAILABLE = False
_LOAD_ERROR: Optional[str] = None


def _nicaiu_path() -> str:
    return os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nicaiu.dll"
    )


def _configure_prototypes(dll) -> None:
    dll.DAQmxCreateTask.argtypes = [c_char_p, POINTER(TaskHandle)]
    dll.DAQmxCreateTask.restype = c_int32
    dll.DAQmxClearTask.argtypes = [TaskHandle]
    dll.DAQmxClearTask.restype = c_int32
    dll.DAQmxStartTask.argtypes = [TaskHandle]
    dll.DAQmxStartTask.restype = c_int32
    dll.DAQmxStopTask.argtypes = [TaskHandle]
    dll.DAQmxStopTask.restype = c_int32
    dll.DAQmxGetSysDevNames.argtypes = [c_char_p, c_uint32]
    dll.DAQmxGetSysDevNames.restype = c_int32
    dll.DAQmxResetDevice.argtypes = [c_char_p]
    dll.DAQmxResetDevice.restype = c_int32
    dll.DAQmxGetExtendedErrorInfo.argtypes = [c_char_p, c_uint32]
    dll.DAQmxGetExtendedErrorInfo.restype = c_int32
    dll.DAQmxCreateAOVoltageChan.argtypes = [
        TaskHandle,
        c_char_p,
        c_char_p,
        c_double,
        c_double,
        c_int32,
        c_char_p,
    ]
    dll.DAQmxCreateAOVoltageChan.restype = c_int32
    dll.DAQmxCfgSampClkTiming.argtypes = [
        TaskHandle,
        c_char_p,
        c_double,
        c_int32,
        c_int32,
        c_uint64,
    ]
    dll.DAQmxCfgSampClkTiming.restype = c_int32
    dll.DAQmxWriteAnalogF64.argtypes = [
        TaskHandle,
        c_int32,
        c_int32,
        c_double,
        c_int32,
        POINTER(c_double),
        POINTER(c_int32),
        c_void_p,
    ]
    dll.DAQmxWriteAnalogF64.restype = c_int32
    dll.DAQmxWaitUntilTaskDone.argtypes = [TaskHandle, c_double]
    dll.DAQmxWaitUntilTaskDone.restype = c_int32
    try:
        dll.DAQmxSetWriteRegenMode.argtypes = [TaskHandle, c_int32]
        dll.DAQmxSetWriteRegenMode.restype = c_int32
    except Exception:
        pass


def _prepare_dll_search_path() -> None:
    """Ensure Windows can resolve NI dependency DLLs outside the frozen tree."""
    candidates = [
        os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            r"National Instruments\Shared\ExternalCompilerSupport\C\lib64\msvc",
        ),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            r"National Instruments\NI-DAQ\DAQmx ANSI C Dev\lib\msvc",
        ),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            r"National Instruments\Shared\ExternalCompilerSupport\C\lib64\gcc",
        ),
    ]
    existing = [d for d in candidates if os.path.isdir(d)]
    try:
        windll.kernel32.SetDllDirectoryW(None)
    except Exception:
        pass
    for d in existing:
        try:
            os.add_dll_directory(d)
        except Exception:
            pass
    # Prefer system/NI dirs over the PyInstaller bundle when resolving deps.
    os.environ["PATH"] = os.pathsep.join(existing + [os.environ.get("PATH", "")])


def load_dll():
    global _dll, _AVAILABLE, _LOAD_ERROR
    if _dll is not None:
        return _dll if _AVAILABLE else None
    path = _nicaiu_path()
    try:
        _prepare_dll_search_path()
        if not os.path.isfile(path):
            raise FileNotFoundError(path)

        # Bypass PyInstaller's ctypes hook: load the module ourselves, then
        # wrap the existing HMODULE. Name-only WinDLL('nicaiu') hangs on
        # DAQmxCreateTask inside frozen exes.
        from ctypes import wintypes

        k32 = windll.kernel32
        LOAD_LIBRARY_SEARCH_DEFAULT_DIRS = 0x00001000
        LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x00000800
        k32.LoadLibraryExW.restype = wintypes.HMODULE
        k32.LoadLibraryExW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.HANDLE,
            wintypes.DWORD,
        ]
        handle = k32.LoadLibraryExW(
            path, None, LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS
        )
        if not handle:
            handle = k32.LoadLibraryExW(path, None, LOAD_LIBRARY_SEARCH_SYSTEM32)
        if not handle:
            k32.LoadLibraryW.restype = wintypes.HMODULE
            k32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
            handle = k32.LoadLibraryW(path)
        if not handle:
            raise OSError(f"LoadLibrary failed for {path}")

        dll = WinDLL(path, handle=handle)
        _configure_prototypes(dll)
        _dll = dll
        _AVAILABLE = True
        _LOAD_ERROR = None
        return dll
    except Exception as e:
        _AVAILABLE = False
        _LOAD_ERROR = str(e)
        _dll = False  # type: ignore[assignment]
        return None


def is_available() -> bool:
    return load_dll() is not None


def load_info() -> str:
    load_dll()
    if _AVAILABLE:
        return _nicaiu_path()
    return f"unavailable: {_LOAD_ERROR}"


def _check(err: int, fn: str) -> None:
    if err >= 0:
        return
    dll = load_dll()
    buf = create_string_buffer(2048)
    try:
        dll.DAQmxGetExtendedErrorInfo(buf, 2048)
        msg = buf.value.decode("utf-8", errors="replace")
    except Exception:
        msg = f"NI-DAQmx error {err}"
    raise RuntimeError(f"{msg}\n in function {fn}")


def list_devices() -> List[str]:
    dll = load_dll()
    if not dll:
        return []
    buf = create_string_buffer(4096)
    _check(dll.DAQmxGetSysDevNames(buf, 4096), "DAQmxGetSysDevNames")
    raw = buf.value.decode("utf-8", errors="replace")
    return [d.strip() for d in raw.split(",") if d.strip()]


def reset_device(name: str) -> None:
    dll = load_dll()
    if not dll or not name:
        return
    _check(dll.DAQmxResetDevice(name.encode("ascii")), "DAQmxResetDevice")


class AoTask:
    """Minimal AO task: create → configure → write → start → stop/clear."""

    def __init__(self, name: str = "TriggerGeneratorAO"):
        dll = load_dll()
        if not dll:
            raise RuntimeError(f"Cannot load nicaiu.dll ({_LOAD_ERROR})")
        self._dll = dll
        self.handle = TaskHandle()
        _check(
            dll.DAQmxCreateTask(name.encode("ascii"), byref(self.handle)),
            "DAQmxCreateTask",
        )

    def create_ao_voltage_chan(self, physical: str, min_v: float, max_v: float) -> None:
        _check(
            self._dll.DAQmxCreateAOVoltageChan(
                self.handle,
                physical.encode("ascii"),
                None,
                c_double(min_v),
                c_double(max_v),
                DAQmx_Val_Volts,
                None,
            ),
            "DAQmxCreateAOVoltageChan",
        )

    def cfg_samp_clk(self, rate: float, mode: int, samps_per_chan: int) -> None:
        _check(
            self._dll.DAQmxCfgSampClkTiming(
                self.handle,
                None,
                c_double(rate),
                DAQmx_Val_Rising,
                mode,
                c_uint64(int(samps_per_chan)),
            ),
            "DAQmxCfgSampClkTiming",
        )

    def allow_regen(self) -> None:
        try:
            _check(
                self._dll.DAQmxSetWriteRegenMode(self.handle, DAQmx_Val_AllowRegen),
                "DAQmxSetWriteRegenMode",
            )
        except Exception:
            pass

    def write_f64(self, data) -> None:
        arr = np.ascontiguousarray(data, dtype=np.float64)
        n = int(arr.size)
        written = c_int32(0)
        _check(
            self._dll.DAQmxWriteAnalogF64(
                self.handle,
                n,
                0,
                c_double(10.0),
                DAQmx_Val_GroupByScanNumber,
                arr.ctypes.data_as(POINTER(c_double)),
                byref(written),
                None,
            ),
            "DAQmxWriteAnalogF64",
        )

    def start(self) -> None:
        _check(self._dll.DAQmxStartTask(self.handle), "DAQmxStartTask")

    def stop(self) -> None:
        if not self.handle:
            return
        try:
            self._dll.DAQmxStopTask(self.handle)
        except Exception:
            pass

    def wait_until_done(self, timeout_s: float) -> None:
        err = self._dll.DAQmxWaitUntilTaskDone(self.handle, c_double(timeout_s))
        if err == -200284:
            raise TimeoutError("WaitUntilTaskDone timeout")
        if err < 0:
            _check(err, "DAQmxWaitUntilTaskDone")

    def clear(self) -> None:
        if not self.handle:
            return
        try:
            self._dll.DAQmxClearTask(self.handle)
        except Exception:
            pass
        self.handle = TaskHandle()
