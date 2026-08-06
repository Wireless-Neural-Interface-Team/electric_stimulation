# -*- coding: utf-8 -*-
"""
Backend for NI-DAQmx trigger generation.

- build_channel_path, DAQWorker
- led_pattern_dimensions / build_led_pattern re-exported from led_pattern (GUI compatibility).
"""

import time
from ctypes import byref, c_int32

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

try:
    from .led_pattern import build_led_pattern, led_pattern_dimensions
except ImportError:
    from led_pattern import build_led_pattern, led_pattern_dimensions

# Optional: PyDAQmx for NI-DAQmx hardware access
try:
    import PyDAQmx as nidaq
    DAQ_AVAILABLE = True
except ImportError:
    DAQ_AVAILABLE = False
    nidaq = None

_AO_MIN_V = -10.0
_AO_MAX_V = 10.0


def build_channel_path(device_str, channel_str):
    """
    Build full channel path for NI-DAQmx.
    Example: Dev2 + ao0 -> Dev2/ao0
    """
    dev = device_str.strip() or "Dev2"
    ch = channel_str.strip() or "ao0"
    return f"{dev}/{ch}" if ch else dev


def _daq_stop_clear(task):
    if task is None:
        return
    try:
        task.StopTask()
    except Exception:
        pass
    try:
        task.ClearTask()
    except Exception:
        pass


class DAQWorker(QObject):
    """
    Worker for DAQ generation (runs in QThread).
    Emits: started (when output begins), finished, error(str).
    """
    finished = pyqtSignal()
    error = pyqtSignal(str)
    started = pyqtSignal()

    def __init__(self, device, sampling_rate, trigger_duration, inter_trigger_interval,
                 infinite, nb_triggers, initial_trigger_delay=5.0, mode="classic",
                 led_train_duration_s=1.0, led_nb_clignotement=1,
                 led_duty_clignotement=1.0, led_light_intensity=1.0,
                 led_inter_train_interval=2.0,
                 led_voltage_high=3.0, led_voltage_low=0.0):
        super().__init__()
        self.device = device
        self.sampling_rate = sampling_rate
        self.trigger_duration = trigger_duration
        self.inter_trigger_interval = inter_trigger_interval
        self.infinite = infinite
        self.nb_triggers = nb_triggers
        self.initial_trigger_delay = initial_trigger_delay
        self.mode = mode
        self.led_train_duration_s = led_train_duration_s
        self.led_nb_clignotement = led_nb_clignotement
        self.led_duty_clignotement = led_duty_clignotement
        self.led_light_intensity = led_light_intensity
        self.led_inter_train_interval = led_inter_train_interval
        self.led_voltage_high = led_voltage_high
        self.led_voltage_low = led_voltage_low
        self._stop_requested = False

    def stop(self):
        """Request worker to stop (called from main thread)."""
        self._stop_requested = True

    def _create_ao_task(self):
        task = nidaq.Task()
        task.CreateAOVoltageChan(
            self.device, None, _AO_MIN_V, _AO_MAX_V, nidaq.DAQmx_Val_Volts, None)
        return task

    def _wait_until_task_done(self, task, timeout_s):
        """Poll WaitUntilTaskDone until success, stop requested, or timeout. Returns True if done."""
        elapsed = 0.0
        while not self._stop_requested and elapsed < timeout_s:
            try:
                task.WaitUntilTaskDone(1.0)
                return True
            except Exception:
                elapsed += 1.0
        return False

    @pyqtSlot()
    def run(self):
        """Main generation logic (runs in worker thread)."""
        t = None
        led_completed_externally = False
        try:
            if not DAQ_AVAILABLE:
                self.error.emit("PyDAQmx is not installed.")
                return

            if self.mode == "led":
                self._run_led_mode()
                led_completed_externally = True
                return

            initial_delay_samples = int(self.initial_trigger_delay * self.sampling_rate)
            trigger_samples = int(self.trigger_duration * self.sampling_rate)
            interval_samples = int(self.inter_trigger_interval * self.sampling_rate)
            if trigger_samples < 1:
                raise ValueError(
                    "Classic mode: trigger duration is too short for the selected sampling rate."
                )
            samples_per_cycle = trigger_samples + interval_samples

            sig_cycle = np.zeros(samples_per_cycle, dtype=np.float64)
            sig_cycle[:trigger_samples] = 3.0

            read = c_int32()
            if self.infinite:
                if initial_delay_samples > 0:
                    self.started.emit()
                    t_delay = self._create_ao_task()
                    t_delay.CfgSampClkTiming(
                        "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                        nidaq.DAQmx_Val_FiniteSamps, initial_delay_samples)
                    t_delay.WriteAnalogF64(
                        initial_delay_samples, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                        np.zeros(initial_delay_samples, dtype=np.float64), byref(read), None)
                    t_delay.StartTask()
                    self._wait_until_task_done(
                        t_delay, self.initial_trigger_delay + 5)
                    _daq_stop_clear(t_delay)
                    if self._stop_requested:
                        t = None
                    else:
                        t = self._create_ao_task()
                        t.CfgSampClkTiming(
                            "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                            nidaq.DAQmx_Val_ContSamps, samples_per_cycle)
                        t.WriteAnalogF64(
                            samples_per_cycle, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                            sig_cycle, byref(read), None)
                        t.StartTask()
                else:
                    t = self._create_ao_task()
                    t.CfgSampClkTiming(
                        "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                        nidaq.DAQmx_Val_ContSamps, samples_per_cycle)
                    t.WriteAnalogF64(
                        samples_per_cycle, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                        sig_cycle, byref(read), None)
                    t.StartTask()
            else:
                data = np.concatenate([
                    np.zeros(initial_delay_samples, dtype=np.float64),
                    np.tile(sig_cycle, self.nb_triggers),
                ])
                nb_samples = len(data)
                t = self._create_ao_task()
                t.CfgSampClkTiming(
                    "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                    nidaq.DAQmx_Val_FiniteSamps, nb_samples)
                t.WriteAnalogF64(
                    nb_samples, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                    data, byref(read), None)
                t.StartTask()

            if self.infinite and initial_delay_samples == 0:
                self.started.emit()
            elif not self.infinite:
                self.started.emit()

            if t is not None:
                if self.infinite:
                    while not self._stop_requested:
                        time.sleep(0.1)
                else:
                    timeout = (
                        self.initial_trigger_delay
                        + self.nb_triggers * (
                            self.inter_trigger_interval + self.trigger_duration)
                        + 10)
                    self._wait_until_task_done(t, timeout)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if led_completed_externally:
                pass
            elif DAQ_AVAILABLE:
                try:
                    if t is not None:
                        _daq_stop_clear(t)
                except NameError:
                    pass
                self._finalize_output_voltage()
            if not led_completed_externally:
                self.finished.emit()

    def _idle_voltage_on_exit(self):
        return self.led_voltage_high if self.mode == "led" else 0.0

    def _run_led_mode(self):
        """LED train + PWM buffer (led_clignotement_v0.1 logic), continuous or finite repeats."""
        t = None
        try:
            sig_one = build_led_pattern(
                self.sampling_rate,
                self.led_train_duration_s,
                self.led_nb_clignotement,
                self.led_duty_clignotement,
                self.led_light_intensity,
                self.led_inter_train_interval,
                self.led_voltage_high,
                self.led_voltage_low,
            )
        except ValueError as e:
            self.error.emit(str(e))
            self.finished.emit()
            return

        read = c_int32()
        initial_delay_samples = int(self.initial_trigger_delay * self.sampling_rate)
        v_idle = self.led_voltage_high

        try:
            if initial_delay_samples > 0:
                self.started.emit()
                t_delay = self._create_ao_task()
                t_delay.CfgSampClkTiming(
                    "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                    nidaq.DAQmx_Val_FiniteSamps, initial_delay_samples)
                t_delay.WriteAnalogF64(
                    initial_delay_samples, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                    np.full(initial_delay_samples, v_idle, dtype=np.float64), byref(read), None)
                t_delay.StartTask()
                self._wait_until_task_done(
                    t_delay, self.initial_trigger_delay + 5)
                _daq_stop_clear(t_delay)
                if self._stop_requested:
                    return

            buf_len = len(sig_one)
            if self.infinite:
                t = self._create_ao_task()
                t.CfgSampClkTiming(
                    "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                    nidaq.DAQmx_Val_ContSamps, buf_len)
                t.WriteAnalogF64(
                    buf_len, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                    sig_one, byref(read), None)
                t.StartTask()
            else:
                data = np.tile(sig_one, self.nb_triggers)
                nb_samples = len(data)
                t = self._create_ao_task()
                t.CfgSampClkTiming(
                    "", self.sampling_rate, nidaq.DAQmx_Val_Rising,
                    nidaq.DAQmx_Val_FiniteSamps, nb_samples)
                t.WriteAnalogF64(
                    nb_samples, False, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                    data, byref(read), None)
                t.StartTask()

            if initial_delay_samples == 0:
                self.started.emit()

            if t is not None:
                if self.infinite:
                    while not self._stop_requested:
                        time.sleep(0.1)
                else:
                    pattern_dur = len(sig_one) / self.sampling_rate
                    timeout = (
                        self.initial_trigger_delay
                        + self.nb_triggers * pattern_dur
                        + 10
                    )
                    self._wait_until_task_done(t, timeout)

        except Exception as e:
            self.error.emit(str(e))
        finally:
            _daq_stop_clear(t)
            self._finalize_output_voltage()
            self.finished.emit()

    def _finalize_output_voltage(self):
        """Set AO to idle: 0 V (classic) or LED rest level (LED mode)."""
        if not DAQ_AVAILABLE:
            return
        target_v = self._idle_voltage_on_exit()
        time.sleep(0.05)
        t_zero = None
        try:
            t_zero = self._create_ao_task()
            if hasattr(t_zero, 'WriteAnalogScalarF64'):
                t_zero.StartTask()
                t_zero.WriteAnalogScalarF64(1, 10.0, target_v, None)
            else:
                read_zero = c_int32()
                t_zero.CfgSampClkTiming("", 1000, nidaq.DAQmx_Val_Rising,
                                       nidaq.DAQmx_Val_FiniteSamps, 1)
                t_zero.WriteAnalogF64(1, True, 10, nidaq.DAQmx_Val_GroupByScanNumber,
                                      np.array([target_v], dtype=np.float64), byref(read_zero), None)
                try:
                    t_zero.WaitUntilTaskDone(10.0)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            _daq_stop_clear(t_zero)
