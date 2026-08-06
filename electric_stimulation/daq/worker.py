# -*- coding: utf-8 -*-
"""QThread worker that drives NI-DAQmx AO generation."""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ..models import GenerationConfig
from ..waveforms import build_classic_cycle, build_led_pattern
from . import DAQ_AVAILABLE, device_name_from_path, format_daq_error, list_daq_devices
from .tasks import start_ao_output, stop_clear_task


class DAQWorker(QObject):
    """
    Runs generation in a worker thread.
    Signals: started, finished, error(str).
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)
    started = pyqtSignal()

    def __init__(self, config: GenerationConfig = None, *args, **kwargs):
        super().__init__()
        if config is None and args:
            # Legacy: DAQWorker(device, rate, trigger, interval, infinite, nb, delay=..., mode=...)
            if isinstance(args[0], GenerationConfig):
                config = args[0]
            else:
                config = GenerationConfig(
                    device=(args[0] or "Dev1/ao0").split("/")[0],
                    channel=(args[0] or "Dev1/ao0").split("/")[-1]
                    if "/" in str(args[0])
                    else "ao0",
                    sampling_rate=args[1] if len(args) > 1 else kwargs.get("sampling_rate", 1000),
                    trigger_duration=args[2] if len(args) > 2 else 0.2,
                    inter_trigger_interval=args[3] if len(args) > 3 else 20.0,
                    infinite=args[4] if len(args) > 4 else True,
                    nb_triggers=args[5] if len(args) > 5 else 5,
                    initial_trigger_delay=args[6]
                    if len(args) > 6
                    else kwargs.get("initial_trigger_delay", 5.0),
                    mode=kwargs.get("mode", "classic"),
                    led_train_duration_s=kwargs.get("led_train_duration_s", 1.0),
                    led_nb_clignotement=kwargs.get("led_nb_clignotement", 1),
                    led_duty_clignotement=kwargs.get("led_duty_clignotement", 1.0),
                    led_light_intensity=kwargs.get("led_light_intensity", 1.0),
                    led_inter_train_interval=kwargs.get("led_inter_train_interval", 2.0),
                    led_voltage_high=kwargs.get("led_voltage_high", 3.0),
                    led_voltage_low=kwargs.get("led_voltage_low", 0.0),
                )
                # If first arg was full path Dev1/ao0
                if args and isinstance(args[0], str) and "/" in args[0]:
                    parts = args[0].split("/", 1)
                    config.device, config.channel = parts[0], parts[1]
        if config is None:
            config = GenerationConfig()
        self.config = config
        self._stop_requested = False
        self._ao_opened = False
        self._active_task = None

    def stop(self) -> None:
        """Abort immediately (safe from the GUI thread)."""
        self._stop_requested = True
        task = self._active_task
        if task is not None:
            try:
                task.StopTask()
            except Exception:
                pass

    def _set_active(self, task) -> None:
        self._active_task = task

    def _start(self, data: np.ndarray, continuous: bool):
        task = start_ao_output(
            self.config.channel_path(),
            self.config.sampling_rate,
            data,
            continuous,
        )
        self._ao_opened = True
        self._set_active(task)
        return task

    def _wait_done(self, task, timeout_s: float) -> bool:
        slice_s = 0.05
        elapsed = 0.0
        while elapsed < timeout_s:
            if self._stop_requested:
                try:
                    task.StopTask()
                except Exception:
                    pass
                return False
            try:
                task.WaitUntilTaskDone(slice_s)
                return not self._stop_requested
            except Exception:
                elapsed += slice_s
        return False

    def _run_waveform(
        self, sig_cycle: np.ndarray, delay_samples: int, idle_voltage: float
    ):
        sig_cycle = np.ascontiguousarray(sig_cycle, dtype=np.float64)
        if sig_cycle.size < 1:
            raise ValueError("Waveform cycle is empty.")

        cfg = self.config
        t = None

        if not cfg.infinite:
            delay = (
                np.full(delay_samples, idle_voltage, dtype=np.float64)
                if delay_samples > 0
                else np.array([], dtype=np.float64)
            )
            body = np.tile(sig_cycle, max(1, int(cfg.nb_triggers)))
            data = np.concatenate([delay, body]) if delay.size else body
            t = self._start(data, continuous=False)
            self.started.emit()
            self._wait_done(t, len(data) / float(cfg.sampling_rate) + 10.0)
            return t

        if delay_samples > 0:
            self.started.emit()
            delay = np.full(delay_samples, idle_voltage, dtype=np.float64)
            t_delay = self._start(delay, continuous=False)
            self._wait_done(
                t_delay, delay_samples / float(cfg.sampling_rate) + 5.0
            )
            stop_clear_task(t_delay)
            self._set_active(None)
            if self._stop_requested:
                return None

        t = self._start(sig_cycle, continuous=True)
        if delay_samples <= 0:
            self.started.emit()
        while not self._stop_requested:
            time.sleep(0.05)
        try:
            t.StopTask()
        except Exception:
            pass
        return t

    def _idle_voltage(self) -> float:
        return (
            self.config.led_voltage_high
            if self.config.mode == "led"
            else 0.0
        )

    def _finalize_idle(self) -> None:
        if not DAQ_AVAILABLE or not self._ao_opened or self._stop_requested:
            return
        self._set_active(None)
        t_zero = None
        try:
            t_zero = self._start(
                np.array([self._idle_voltage()], dtype=np.float64), continuous=False
            )
            try:
                t_zero.WaitUntilTaskDone(0.5)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            stop_clear_task(t_zero)
            self._set_active(None)

    def _ensure_device(self) -> Optional[str]:
        available = list_daq_devices()
        name = device_name_from_path(self.config.channel_path())
        if not available:
            return (
                "No NI-DAQmx device was detected.\n"
                "Check that the hardware is connected and NI-DAQmx is installed."
            )
        if name and name not in available:
            return (
                f"Device '{name}' was not found.\n"
                f"Available device(s): {', '.join(available)}\n"
                f"Requested channel: {self.config.channel_path()}"
            )
        return None

    @pyqtSlot()
    def run(self) -> None:
        t = None
        try:
            if not DAQ_AVAILABLE:
                self.error.emit("PyDAQmx is not installed.")
                return
            problem = self._ensure_device()
            if problem:
                self.error.emit(problem)
                return

            self.config.validate()
            cfg = self.config
            delay_samples = cfg.delay_samples()

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
                idle = cfg.led_voltage_high
            else:
                sig = build_classic_cycle(
                    cfg.sampling_rate,
                    cfg.trigger_duration,
                    cfg.inter_trigger_interval,
                    cfg.pulse_voltage,
                )
                idle = 0.0

            t = self._run_waveform(sig, delay_samples, idle)

        except Exception as e:
            self.error.emit(format_daq_error(e, self.config.channel_path()))
        finally:
            stop_clear_task(t)
            self._set_active(None)
            if self._ao_opened and not self._stop_requested:
                self._finalize_idle()
            self.finished.emit()
