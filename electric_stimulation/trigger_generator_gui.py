# -*- coding: utf-8 -*-
"""
GUI for Trigger Generator.

Displays parameters, state indicator, and controls.
Uses trigger_generator_backend for DAQ logic.
"""

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QLabel, QMessageBox, QLineEdit, QFrame, QFileDialog,
    QComboBox,
)
try:
    from .experiment_io import (
        build_experiment_record,
        experiences_dir,
        save_experiment_record,
    )
    from .trigger_generator_backend import (
        build_channel_path, DAQWorker, DAQ_AVAILABLE, led_pattern_dimensions,
    )
except ImportError:
    from experiment_io import (
        build_experiment_record,
        experiences_dir,
        save_experiment_record,
    )
    from trigger_generator_backend import (
        build_channel_path, DAQWorker, DAQ_AVAILABLE, led_pattern_dimensions,
    )


def _state_frame_stylesheet(bg_hex):
    return f"QFrame {{ background-color: {bg_hex}; border-radius: 8px; }}"


def _format_elapsed(seconds):
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:05.2f}"


def _format_countdown(seconds):
    if seconds <= 0:
        return "0.00 s"
    return f"{seconds:.2f} s remaining"


class TriggerGeneratorWindow(QMainWindow):
    """Main application window for trigger generation control."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.worker_thread = None
        self.state_timer = None
        self.state_start_time = None
        self.worker_params = None
        self.init_ui()
        self.load_params_from_json(silent=True)

    def init_ui(self):
        """Build the main window layout and widgets."""
        self.setWindowTitle("Trigger Generator - NI-DAQmx")
        self.setMinimumWidth(400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Load Parameters (top left) ---
        top_bar = QHBoxLayout()
        self.load_btn = QPushButton("Load Parameters")
        self.load_btn.setMinimumHeight(32)
        self.load_btn.clicked.connect(self.load_params_from_json)
        top_bar.addWidget(self.load_btn)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # --- Parameters group ---
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Classic (0 V / 3 V pulses)", "classic")
        self.mode_combo.addItem("LED", "led")
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        params_layout.addRow("Mode:", self.mode_combo)

        # Device and channel (e.g. Dev2, ao0)
        self.device_edit = QLineEdit()
        self.device_edit.setPlaceholderText("Dev1, Dev2, ...")
        self.device_edit.setText("Dev2")
        params_layout.addRow("Device NI-DAQmx:", self.device_edit)

        self.channel_edit = QLineEdit()
        self.channel_edit.setPlaceholderText("ao0, ao1, ...")
        self.channel_edit.setText("ao0")
        params_layout.addRow("Channel:", self.channel_edit)

        # Sampling rate in Hz (output update frequency)
        self.sampling_rate_spin = QDoubleSpinBox()
        self.sampling_rate_spin.setRange(100, 100000)
        self.sampling_rate_spin.setValue(1000)
        self.sampling_rate_spin.setSuffix(" Hz")
        self.sampling_rate_spin.setDecimals(0)
        self.sampling_rate_spin.setToolTip(
            "Output sample rate (LED pulse lengths are quantized to this clock)."
        )
        params_layout.addRow("Sampling rate:", self.sampling_rate_spin)

        self.classic_pulse_group = QGroupBox("Pulses (classic mode)")
        classic_form = QFormLayout(self.classic_pulse_group)
        self.trigger_duration_spin = QDoubleSpinBox()
        self.trigger_duration_spin.setRange(1e-6, 60)
        self.trigger_duration_spin.setValue(0.2)
        self.trigger_duration_spin.setSuffix(" s")
        self.trigger_duration_spin.setDecimals(6)
        classic_form.addRow("Trigger duration (3 V):", self.trigger_duration_spin)
        self.inter_trigger_spin = QDoubleSpinBox()
        self.inter_trigger_spin.setRange(0, 3600)
        self.inter_trigger_spin.setValue(20)
        self.inter_trigger_spin.setSuffix(" s")
        self.inter_trigger_spin.setDecimals(1)
        classic_form.addRow("Inter-trigger interval:", self.inter_trigger_spin)
        params_layout.addRow(self.classic_pulse_group)

        # Initial delay before pattern starts (seconds)
        self.initial_trigger_delay_spin = QDoubleSpinBox()
        self.initial_trigger_delay_spin.setRange(0, 300)
        self.initial_trigger_delay_spin.setValue(5)
        self.initial_trigger_delay_spin.setSuffix(" s")
        self.initial_trigger_delay_spin.setDecimals(1)
        self.initial_trigger_delay_spin.setToolTip(
            "Classic: 0 V before first pulse. LED: rest voltage before the train."
        )
        params_layout.addRow("Initial delay:", self.initial_trigger_delay_spin)

        # Infinite: repeat forever; else use nb_triggers
        self.infinite_check = QCheckBox("Repeat indefinitely")
        self.infinite_check.setChecked(True)
        self.infinite_check.toggled.connect(self.on_infinite_toggled)
        params_layout.addRow("", self.infinite_check)

        self.nb_triggers_spin = QSpinBox()
        self.nb_triggers_spin.setRange(1, 10000)
        self.nb_triggers_spin.setValue(5)
        self.nb_triggers_spin.setEnabled(False)
        params_layout.addRow("Number of triggers:", self.nb_triggers_spin)

        # --- LED mode (led_clignotement_v0.1 logic) ---
        self.led_group = QGroupBox("LED — train")
        led_layout = QFormLayout(self.led_group)
        self.led_train_duration_spin = QDoubleSpinBox()
        self.led_train_duration_spin.setRange(1e-6, 86400.0)
        self.led_train_duration_spin.setValue(1.0)
        self.led_train_duration_spin.setSuffix(" s")
        self.led_train_duration_spin.setDecimals(6)
        self.led_train_duration_spin.setToolTip(
            "Duration of one stimulation train in seconds "
            "(length in samples = ceil(sampling rate × duration))."
        )
        led_layout.addRow("Train duration:", self.led_train_duration_spin)

        self.led_nb_cycles_spin = QSpinBox()
        self.led_nb_cycles_spin.setRange(1, 100000)
        self.led_nb_cycles_spin.setValue(1)
        self.led_nb_cycles_spin.setToolTip(
            "Number of blinks inside the train duration (equal-length slots). "
            "E.g. 5 → five flashes within one train."
        )
        led_layout.addRow("Cycles per train:", self.led_nb_cycles_spin)

        self.led_duty_train_spin = QDoubleSpinBox()
        self.led_duty_train_spin.setRange(0.0, 1.0)
        self.led_duty_train_spin.setValue(1.0)
        self.led_duty_train_spin.setSingleStep(0.05)
        self.led_duty_train_spin.setDecimals(3)
        self.led_duty_train_spin.setToolTip(
            "Target fraction of each slot at pulse voltage; the same pulse width (in samples) "
            "is used for every blink (from average slot length, capped so all slots fit)."
        )
        led_layout.addRow("Train duty cycle:", self.led_duty_train_spin)

        self.led_light_intensity_spin = QDoubleSpinBox()
        self.led_light_intensity_spin.setRange(0.0, 1.0)
        self.led_light_intensity_spin.setValue(1.0)
        self.led_light_intensity_spin.setSingleStep(0.05)
        self.led_light_intensity_spin.setDecimals(3)
        self.led_light_intensity_spin.setToolTip(
            "Light intensity (0–1): among active samples, round(Lxvalue) are at pulse voltage, "
            "evenly spaced (1 = full on; 0.2 ≈ 20% of samples; 0 = off)."
        )
        led_layout.addRow("Light intensity:", self.led_light_intensity_spin)

        self.led_inter_train_spin = QDoubleSpinBox()
        self.led_inter_train_spin.setRange(0.0, 3600.0)
        self.led_inter_train_spin.setValue(2.0)
        self.led_inter_train_spin.setSuffix(" s")
        self.led_inter_train_spin.setDecimals(3)
        led_layout.addRow("Inter-train pause:", self.led_inter_train_spin)

        self.led_v_high_spin = QDoubleSpinBox()
        self.led_v_high_spin.setRange(-10.0, 10.0)
        self.led_v_high_spin.setValue(3.0)
        self.led_v_high_spin.setSuffix(" V")
        self.led_v_high_spin.setDecimals(2)
        self.led_v_high_spin.setToolTip("Rest level (outside LED pulses in the original script)")
        led_layout.addRow("Rest voltage (high):", self.led_v_high_spin)

        self.led_v_low_spin = QDoubleSpinBox()
        self.led_v_low_spin.setRange(-10.0, 10.0)
        self.led_v_low_spin.setValue(0.0)
        self.led_v_low_spin.setSuffix(" V")
        self.led_v_low_spin.setDecimals(2)
        self.led_v_low_spin.setToolTip("Level during pulse (PWM coincidence)")
        led_layout.addRow("Pulse voltage (low):", self.led_v_low_spin)

        self.params_group = params_group
        layout.addWidget(params_group)
        layout.addWidget(self.led_group)

        # --- Action buttons ---
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setFont(QFont("", 11, QFont.Bold))
        self.start_btn.clicked.connect(self.start_generation)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setFont(QFont("", 11, QFont.Bold))
        self.stop_btn.clicked.connect(self.stop_generation)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # --- State indicator: shows current phase (Initial trigger delay, Trigger, 0V) + countdown ---
        self.state_frame = QFrame()
        self.state_frame.setFrameStyle(QFrame.StyledPanel)
        self.state_frame.setMinimumHeight(60)
        self.state_frame.setStyleSheet("""
            QFrame { background-color: #e0e0e0; border-radius: 8px; }
        """)
        state_layout = QVBoxLayout(self.state_frame)
        self.state_label = QLabel("—")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setFont(QFont("", 18, QFont.Bold))
        self.state_label.setStyleSheet("color: #666;")
        state_layout.addWidget(self.state_label)
        self.time_label = QLabel("—")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setFont(QFont("", 14))
        self.time_label.setStyleSheet("color: #666;")
        state_layout.addWidget(self.time_label)
        layout.addWidget(self.state_frame)

        # --- Total elapsed time (subtle display) ---
        self.time_total_frame = QFrame()
        self.time_total_frame.setFrameStyle(QFrame.NoFrame)
        self.time_total_frame.setMaximumHeight(32)
        self.time_total_frame.setStyleSheet("QFrame { background-color: transparent; }")
        time_total_layout = QHBoxLayout(self.time_total_frame)
        time_total_layout.setContentsMargins(4, 2, 4, 2)
        time_total_label_txt = QLabel("Total time:")
        time_total_label_txt.setStyleSheet("color: #999; font-size: 11px;")
        time_total_layout.addWidget(time_total_label_txt)
        self.time_total_label = QLabel("0:00")
        self.time_total_label.setFont(QFont("", 11))
        self.time_total_label.setStyleSheet("color: #999;")
        time_total_layout.addWidget(self.time_total_label)
        time_total_layout.addStretch()
        layout.addWidget(self.time_total_frame)

        # Disable start if PyDAQmx not installed
        if not DAQ_AVAILABLE:
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip("PyDAQmx is not installed")

        self.on_mode_changed()

    def on_mode_changed(self, _index=None):
        """Show LED or classic fields depending on mode."""
        led = self.mode_combo.currentData() == "led"
        self.led_group.setVisible(led)
        self.classic_pulse_group.setVisible(not led)
        self.nb_triggers_spin.setToolTip(
            "Classic: number of pulses. LED: number of full pattern repeats (train + pause)."
            if led
            else ""
        )
        # QMainWindow does not shrink by itself after setVisible(False); refresh after layout.
        QTimer.singleShot(0, self._shrink_window_to_content_height)

    def _shrink_window_to_content_height(self):
        """Fit window height to content (e.g. when switching back to Classic)."""
        cw = self.centralWidget()
        if cw is None:
            return
        lay = cw.layout()
        if lay is not None:
            lay.activate()
        cw.updateGeometry()
        self.updateGeometry()
        h = self.sizeHint().height()
        if h > 0:
            self.resize(self.width(), h)

    def on_infinite_toggled(self, checked):
        """Enable nb_triggers only when not in infinite mode."""
        self.nb_triggers_spin.setEnabled(not checked)

    def _worker_params_snapshot(
        self,
        device_str,
        channel_str,
        sampling_rate,
        trigger_duration,
        inter_trigger,
        initial_trigger_delay,
        infinite,
        nb_triggers,
        mode,
    ):
        led_train_samples, led_timer_samples = led_pattern_dimensions(
            sampling_rate,
            self.led_train_duration_spin.value(),
            self.led_inter_train_spin.value(),
        )
        return {
            "device": device_str,
            "channel": channel_str,
            "sampling_rate": sampling_rate,
            "initial_trigger_delay": initial_trigger_delay,
            "trigger": trigger_duration,
            "interval": inter_trigger,
            "infinite": infinite,
            "nb_triggers": nb_triggers,
            "mode": mode,
            "led_train_samples": led_train_samples,
            "led_timer_samples": led_timer_samples,
            "led_train_duration_s": self.led_train_duration_spin.value(),
            "led_nb_clignotement": int(self.led_nb_cycles_spin.value()),
            "led_duty_clignotement": self.led_duty_train_spin.value(),
            "led_light_intensity": self.led_light_intensity_spin.value(),
            "led_inter_train_interval": self.led_inter_train_spin.value(),
            "led_voltage_high": self.led_v_high_spin.value(),
            "led_voltage_low": self.led_v_low_spin.value(),
        }

    def set_params_enabled(self, enabled):
        """Enable or disable all parameter fields."""
        self.mode_combo.setEnabled(enabled)
        self.device_edit.setEnabled(enabled)
        self.channel_edit.setEnabled(enabled)
        self.sampling_rate_spin.setEnabled(enabled)
        self.classic_pulse_group.setEnabled(enabled)
        self.initial_trigger_delay_spin.setEnabled(enabled)
        self.infinite_check.setEnabled(enabled)
        self.nb_triggers_spin.setEnabled(enabled and not self.infinite_check.isChecked())
        self.led_group.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)

    def start_generation(self):
        """Start DAQ generation in a worker thread."""
        if self.worker_thread and self.worker_thread.isRunning():
            return

        # Gather parameters from UI
        device = build_channel_path(self.device_edit.text(), self.channel_edit.text())
        sampling_rate = self.sampling_rate_spin.value()
        trigger_duration = self.trigger_duration_spin.value()
        inter_trigger = self.inter_trigger_spin.value()
        initial_trigger_delay = self.initial_trigger_delay_spin.value()
        infinite = self.infinite_check.isChecked()
        nb_triggers = self.nb_triggers_spin.value()
        mode = self.mode_combo.currentData() or "classic"

        if mode == "classic":
            trigger_samples = int(trigger_duration * sampling_rate)
            if trigger_samples < 1:
                QMessageBox.warning(
                    self, "Classic settings",
                    "Trigger duration is too short for the selected sampling rate. "
                    "Increase trigger duration or sampling rate.",
                )
                return

        if mode == "led":
            train_dur_s = self.led_train_duration_spin.value()
            if train_dur_s <= 0:
                QMessageBox.warning(
                    self, "LED settings",
                    "Train duration must be positive.",
                )
                return
            period_un = int(math.ceil(sampling_rate * train_dur_s))
            n_blinks = int(self.led_nb_cycles_spin.value())
            if period_un < n_blinks:
                QMessageBox.warning(
                    self, "LED settings",
                    "This train duration yields too few samples for this many blinks. "
                    "Increase sampling rate or train duration, or reduce cycles per train.",
                )
                return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.set_params_enabled(False)

        # Create worker and thread
        self.worker = DAQWorker(
            device, sampling_rate, trigger_duration, inter_trigger,
            infinite, nb_triggers, initial_trigger_delay,
            mode=mode,
            led_train_duration_s=self.led_train_duration_spin.value(),
            led_nb_clignotement=int(self.led_nb_cycles_spin.value()),
            led_duty_clignotement=self.led_duty_train_spin.value(),
            led_light_intensity=self.led_light_intensity_spin.value(),
            led_inter_train_interval=self.led_inter_train_spin.value(),
            led_voltage_high=self.led_v_high_spin.value(),
            led_voltage_low=self.led_v_low_spin.value(),
        )
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.started.connect(self.on_generation_started)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)

        self.worker_params = self._worker_params_snapshot(
            self.device_edit.text().strip(),
            self.channel_edit.text().strip(),
            sampling_rate,
            trigger_duration,
            inter_trigger,
            initial_trigger_delay,
            infinite,
            nb_triggers,
            mode,
        )
        self.experiment_start_time = datetime.now()
        self.worker_thread.start()

    def stop_generation(self):
        """Request worker to stop generation."""
        if self.worker:
            self.worker.stop()

    def on_generation_started(self):
        """Start timer to display real-time state (called when DAQ output begins)."""
        self.state_start_time = time.time()
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self.update_state_indicator)
        self.state_timer.start(100)

    def update_state_indicator(self):
        """Update indicator based on current signal phase (called every 100ms)."""
        if self.state_start_time is None or self.worker_params is None:
            return
        elapsed = time.time() - self.state_start_time
        self.time_total_label.setText(_format_elapsed(elapsed))
        p = self.worker_params
        initial_delay = p["initial_trigger_delay"]
        sr = p["sampling_rate"]

        if p.get("mode") == "led":
            vh = p.get("led_voltage_high", 3.0)
            train_s = p.get("led_train_samples", 1)
            timer_s = max(1, p.get("led_timer_samples", 1))
            train_dur = train_s / sr
            cycle_dur = timer_s / sr
            if elapsed < initial_delay:
                text = f"LED — wait ({vh:.1f} V rest)"
                color, bg = "#666", "#e0e0e0"
                remaining = initial_delay - elapsed
                countdown = _format_countdown(remaining)
            else:
                t_loop = elapsed - initial_delay
                if not p["infinite"]:
                    total_dur = p["nb_triggers"] * cycle_dur
                    if t_loop >= total_dur:
                        text, color, bg = "Done", "#666", "#e0e0e0"
                        self.state_label.setText(text)
                        self.state_label.setStyleSheet(f"color: {color};")
                        self.state_frame.setStyleSheet(_state_frame_stylesheet(bg))
                        self.time_label.setText("—")
                        return
                pos = t_loop % cycle_dur
                if pos < train_dur:
                    text, color, bg = "LED — train (PWM)", "#6a1b9a", "#e1bee7"
                    remaining = train_dur - pos
                else:
                    text, color, bg = "LED — pause entre trains", "#37474f", "#eceff1"
                    remaining = cycle_dur - pos
                countdown = _format_countdown(remaining)
            self.state_label.setText(text)
            self.state_label.setStyleSheet(f"color: {color};")
            self.state_frame.setStyleSheet(_state_frame_stylesheet(bg))
            self.time_label.setText(countdown)
            return

        trigger, interval = p["trigger"], p["interval"]
        cycle_duration = trigger + interval

        # Phase 1: Initial delay (0 V in classic mode)
        if elapsed < initial_delay:
            text, color, bg = "(0 V)", "#666", "#e0e0e0"
            remaining = initial_delay - elapsed
            countdown = _format_countdown(remaining)
        else:
            # Phase 2: Trigger or interval
            cycle_time = elapsed - initial_delay
            if p["infinite"]:
                pos_in_cycle = cycle_time % cycle_duration
            else:
                total_cycles = p["nb_triggers"] * cycle_duration
                if cycle_time >= total_cycles:
                    # All triggers done
                    text, color, bg = "Done", "#666", "#e0e0e0"
                    self.state_label.setText(text)
                    self.state_label.setStyleSheet(f"color: {color};")
                    self.state_frame.setStyleSheet(_state_frame_stylesheet(bg))
                    self.time_label.setText("—")
                    return
                pos_in_cycle = cycle_time % cycle_duration

            if pos_in_cycle < trigger:
                text, color, bg = "Trigger (3 V)", "#1b5e20", "#c8e6c9"
                remaining = trigger - pos_in_cycle
            else:
                text, color, bg = "0 V (interval)", "#37474f", "#eceff1"
                remaining = cycle_duration - pos_in_cycle
            countdown = _format_countdown(remaining)

        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color: {color};")
        self.state_frame.setStyleSheet(_state_frame_stylesheet(bg))
        self.time_label.setText(countdown)

    def save_params_to_json(self, duration_seconds):
        """Save parameters and experiment info to a JSON file (on generation stop)."""
        if self.worker_params is None:
            return
        exp_time = getattr(self, "experiment_start_time", datetime.now())
        record = build_experiment_record(
            self.worker_params, duration_seconds, exp_time, datetime.now()
        )
        save_dir = experiences_dir()
        filename = exp_time.strftime("trigger_generator_%Y-%m-%d_%H-%M-%S.json")
        save_experiment_record(record, save_dir / filename)

    def load_params_from_json(self, silent=False):
        """Load parameters from a JSON file.
        If silent=True (e.g. at startup), loads the most recent file without dialog.
        If silent=False (button click), opens a file dialog to choose the file."""
        save_dir = experiences_dir()
        if not save_dir.exists():
            if not silent:
                QMessageBox.warning(self, "Load", "No experiments folder found.")
            return
        json_files = list(save_dir.glob("trigger_generator_*.json")) + list(save_dir.glob("wavegene_*.json"))
        if not json_files:
            if not silent:
                QMessageBox.warning(self, "Load", "No experiment file found.")
            return

        if silent:
            path = max(json_files, key=lambda p: p.stat().st_mtime)
        else:
            path_str, _ = QFileDialog.getOpenFileName(
                self, "Load Parameters",
                str(save_dir),
                "JSON files (*.json);;All files (*)"
            )
            if not path_str:
                return
            path = Path(path_str)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.device_edit.setText(data.get("device", "Dev2"))
            self.channel_edit.setText(data.get("channel", "ao0"))
            self.sampling_rate_spin.setValue(data.get("sampling_rate", 1000))
            self.trigger_duration_spin.setValue(data.get("trigger_duration", data.get("pulse_duration", 0.2)))
            self.inter_trigger_spin.setValue(data.get("inter_trigger_interval", data.get("inter_pulse_interval", 20)))
            self.initial_trigger_delay_spin.setValue(data.get("initial_trigger_delay", 5))
            self.infinite_check.setChecked(data.get("infinite", True))
            self.nb_triggers_spin.setValue(data.get("nb_triggers", data.get("nb_pulses", 5)))
            mode = data.get("mode", "classic")
            idx = self.mode_combo.findData(mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
            self.led_train_duration_spin.setValue(data.get("led_train_duration_s", 1.0))
            self.led_nb_cycles_spin.setValue(int(data.get("led_nb_clignotement", 1)))
            self.led_duty_train_spin.setValue(data.get("led_duty_clignotement", 1.0))
            self.led_light_intensity_spin.setValue(data.get("led_light_intensity", 1.0))
            self.led_inter_train_spin.setValue(data.get("led_inter_train_interval", 2.0))
            self.led_v_high_spin.setValue(data.get("led_voltage_high", 3.0))
            self.led_v_low_spin.setValue(data.get("led_voltage_low", 0.0))
            self.on_mode_changed()
            if not silent:
                QMessageBox.information(self, "Load", f"Parameters loaded from {path.name}")
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    def on_generation_finished(self):
        """Clean up when generation stops (user stop or completion)."""
        if self.state_timer:
            self.state_timer.stop()
            self.state_timer = None
        duration = 0
        if self.state_start_time is not None:
            duration = time.time() - self.state_start_time
            self.save_params_to_json(duration)
        self.state_start_time = None
        self.state_label.setText("—")
        self.time_label.setText("—")
        self.time_total_label.setText("0:00")
        self.state_label.setStyleSheet("color: #666;")
        self.time_label.setStyleSheet("color: #666;")
        self.state_frame.setStyleSheet(_state_frame_stylesheet("#e0e0e0"))
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(2000)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_params_enabled(True)

    def on_generation_error(self, msg):
        """Handle DAQ or worker error: cleanup and show message."""
        self.on_generation_finished()
        QMessageBox.critical(self, "Error", msg)


def main():
    """Application entry point."""
    app = QApplication([])
    app.setStyle("Fusion")
    window = TriggerGeneratorWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
