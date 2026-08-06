# -*- coding: utf-8 -*-
"""
Main-thread AO session (no Qt).

This is the only place that talks to NI-DAQmx during generation. The GUI
launches it in a *separate process* so behaviour matches `python script.py`
inside a frozen exe (no QThread / moveToThread / GUI-thread NI issues).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from ..models import GenerationConfig
from ..waveforms import build_classic_cycle, build_led_pattern
from .devices import (
    DAQ_AVAILABLE,
    device_name_from_path,
    format_daq_error,
    list_daq_devices,
)
from .tasks import start_ao_output, stop_clear_task

StopCheck = Callable[[], bool]


def _ensure_device(cfg: GenerationConfig) -> Optional[str]:
    available = list_daq_devices()
    name = device_name_from_path(cfg.channel_path())
    if not available:
        return (
            "No NI-DAQmx device was detected.\n"
            "Check that the hardware is connected and NI-DAQmx is installed."
        )
    if name and name not in available:
        return (
            f"Device '{name}' was not found.\n"
            f"Available device(s): {', '.join(available)}\n"
            f"Requested channel: {cfg.channel_path()}"
        )
    return None


def _wait_finite(task, timeout_s: float, should_stop: StopCheck) -> bool:
    """Return True if task completed normally, False if stopped early."""
    slice_s = 0.05
    elapsed = 0.0
    while elapsed < timeout_s:
        if should_stop():
            try:
                task.stop()
            except Exception:
                pass
            return False
        try:
            task.wait_until_done(slice_s)
            return not should_stop()
        except TimeoutError:
            elapsed += slice_s
        except Exception:
            elapsed += slice_s
    return False


def _build_cycle(cfg: GenerationConfig):
    if cfg.mode == "led":
        sig = build_led_pattern(
            cfg.sampling_rate,
            cfg.led_train_duration_s,
            cfg.led_nb_clignotement,
            cfg.led_duty_clignotement,
            cfg.led_light_intensity,
            cfg.led_inter_train_interval,
            cfg.led_voltage_high,
            cfg.led_voltage_low,
        )
        idle = float(cfg.led_voltage_high)
    else:
        sig = build_classic_cycle(
            cfg.sampling_rate,
            cfg.trigger_duration,
            cfg.inter_trigger_interval,
            cfg.pulse_voltage,
        )
        idle = 0.0
    sig = np.ascontiguousarray(sig, dtype=np.float64)
    if sig.size < 1:
        raise ValueError("Waveform cycle is empty.")
    return sig, idle


def run_ao_session(
    cfg: GenerationConfig,
    should_stop: Optional[StopCheck] = None,
    on_started: Optional[Callable[[], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Block until the AO session finishes or should_stop() becomes True.
    Raises on setup / hardware errors.
    """
    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    if should_stop is None:
        should_stop = lambda: False

    if not DAQ_AVAILABLE:
        raise RuntimeError("PyDAQmx is not installed.")
    problem = _ensure_device(cfg)
    if problem:
        raise RuntimeError(problem)
    cfg.validate()

    sig_cycle, idle_voltage = _build_cycle(cfg)
    delay_samples = cfg.delay_samples()
    task = None
    ao_opened = False

    def _start(data: np.ndarray, continuous: bool):
        nonlocal ao_opened
        if should_stop():
            raise RuntimeError("Stop requested before AO start.")
        _progress(f"start_ao continuous={continuous} samples={len(data)}")
        t = start_ao_output(
            cfg.channel_path(),
            float(cfg.sampling_rate),
            data,
            continuous,
            on_progress=_progress,
        )
        ao_opened = True
        _progress("start_ao ok")
        return t

    try:
        if not cfg.infinite:
            delay = (
                np.full(delay_samples, idle_voltage, dtype=np.float64)
                if delay_samples > 0
                else np.array([], dtype=np.float64)
            )
            body = np.tile(sig_cycle, max(1, int(cfg.nb_triggers)))
            data = np.concatenate([delay, body]) if delay.size else body
            task = _start(data, continuous=False)
            if on_started:
                on_started()
            _wait_finite(
                task, len(data) / float(cfg.sampling_rate) + 10.0, should_stop
            )
            return

        # Infinite
        started = False
        if delay_samples > 0:
            delay = np.full(delay_samples, idle_voltage, dtype=np.float64)
            task = _start(delay, continuous=False)
            if on_started:
                on_started()
                started = True
            _wait_finite(
                task,
                delay_samples / float(cfg.sampling_rate) + 5.0,
                should_stop,
            )
            stop_clear_task(task)
            task = None
            if should_stop():
                return

        task = _start(sig_cycle, continuous=True)
        if not started and on_started:
            on_started()
        while not should_stop():
            time.sleep(0.05)
        try:
            task.stop()
        except Exception:
            pass
    finally:
        stop_clear_task(task)
        if ao_opened and not should_stop():
            try:
                t_idle = start_ao_output(
                    cfg.channel_path(),
                    float(cfg.sampling_rate),
                    np.array([idle_voltage], dtype=np.float64),
                    continuous=False,
                )
                try:
                    t_idle.wait_until_done(0.5)
                except Exception:
                    pass
                stop_clear_task(t_idle)
            except Exception:
                pass


def stop_file_checker(path: Path) -> StopCheck:
    path = Path(path)

    def _check() -> bool:
        try:
            return path.exists()
        except Exception:
            return False

    return _check


def format_session_error(exc: BaseException, cfg: GenerationConfig) -> str:
    return format_daq_error(exc, cfg.channel_path())
