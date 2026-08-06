# -*- coding: utf-8 -*-
"""Main Trigger Generator window."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..daq import DAQ_AVAILABLE, DAQWorker, default_daq_device, list_daq_devices
from ..experiment_io import (
    build_experiment_record,
    experiences_dir,
    load_experiment_file,
    save_experiment_record,
)
from ..models import GenerationConfig
from .phase_status import format_elapsed, phase_display


class TriggerGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.state_timer = None
        self.state_start_time = None
        self.worker_params = None
        self.experiment_start_time = None
        self._session_active = False
        self._build_ui()
        self._refresh_devices()
        self.load_params(silent=True)

    def _build_ui(self):
        self.setWindowTitle("Trigger Generator")
        self.setMinimumWidth(460)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 10)

        # Toolbar
        bar = QHBoxLayout()
        self.load_btn = QPushButton("Load…")
        self.load_btn.setObjectName("btnSecondary")
        self.load_btn.clicked.connect(lambda: self.load_params(silent=False))
        self.refresh_dev_btn = QPushButton("Refresh devices")
        self.refresh_dev_btn.setObjectName("btnSecondary")
        self.refresh_dev_btn.clicked.connect(self._refresh_devices)
        bar.addWidget(self.load_btn)
        bar.addWidget(self.refresh_dev_btn)
        bar.addStretch()
        root.addLayout(bar)

        # Hardware
        hw = QGroupBox("Hardware")
        hw_form = QFormLayout(hw)
        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.channel_edit = QLineEdit("ao0")
        self.channel_edit.setPlaceholderText("ao0, ao1, …")
        self.sampling_rate_spin = QDoubleSpinBox()
        self.sampling_rate_spin.setRange(100, 100000)
        self.sampling_rate_spin.setValue(1000)
        self.sampling_rate_spin.setDecimals(0)
        self.sampling_rate_spin.setSuffix(" Hz")
        hw_form.addRow("Device", self.device_combo)
        hw_form.addRow("Channel", self.channel_edit)
        hw_form.addRow("Sampling rate", self.sampling_rate_spin)
        root.addWidget(hw)

        # Mode + schedule
        sched = QGroupBox("Protocol")
        sched_form = QFormLayout(sched)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Classic — 0 V / 3 V pulses", "classic")
        self.mode_combo.addItem("LED — train / PWM", "led")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 300)
        self.delay_spin.setValue(5)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setSuffix(" s")
        self.infinite_check = QCheckBox("Repeat indefinitely")
        self.infinite_check.setChecked(True)
        self.infinite_check.toggled.connect(self._on_infinite_toggled)
        self.nb_spin = QSpinBox()
        self.nb_spin.setRange(1, 10000)
        self.nb_spin.setValue(5)
        self.nb_spin.setEnabled(False)
        sched_form.addRow("Mode", self.mode_combo)
        sched_form.addRow("Initial delay", self.delay_spin)
        sched_form.addRow("", self.infinite_check)
        sched_form.addRow("Repetitions", self.nb_spin)
        root.addWidget(sched)

        # Classic
        self.classic_group = QGroupBox("Classic pulses")
        classic = QFormLayout(self.classic_group)
        self.trigger_spin = QDoubleSpinBox()
        self.trigger_spin.setRange(1e-6, 60)
        self.trigger_spin.setValue(0.2)
        self.trigger_spin.setDecimals(6)
        self.trigger_spin.setSuffix(" s")
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0, 3600)
        self.interval_spin.setValue(20)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" s")
        classic.addRow("Pulse width (3 V)", self.trigger_spin)
        classic.addRow("Inter-pulse interval", self.interval_spin)
        root.addWidget(self.classic_group)

        # LED
        self.led_group = QGroupBox("LED train")
        led = QFormLayout(self.led_group)
        self.led_train_spin = QDoubleSpinBox()
        self.led_train_spin.setRange(1e-6, 86400)
        self.led_train_spin.setValue(1.0)
        self.led_train_spin.setDecimals(6)
        self.led_train_spin.setSuffix(" s")
        self.led_cycles_spin = QSpinBox()
        self.led_cycles_spin.setRange(1, 100000)
        self.led_cycles_spin.setValue(1)
        self.led_duty_spin = QDoubleSpinBox()
        self.led_duty_spin.setRange(0, 1)
        self.led_duty_spin.setValue(1.0)
        self.led_duty_spin.setSingleStep(0.05)
        self.led_duty_spin.setDecimals(3)
        self.led_intensity_spin = QDoubleSpinBox()
        self.led_intensity_spin.setRange(0, 1)
        self.led_intensity_spin.setValue(1.0)
        self.led_intensity_spin.setSingleStep(0.05)
        self.led_intensity_spin.setDecimals(3)
        self.led_pause_spin = QDoubleSpinBox()
        self.led_pause_spin.setRange(0, 3600)
        self.led_pause_spin.setValue(2.0)
        self.led_pause_spin.setDecimals(3)
        self.led_pause_spin.setSuffix(" s")
        self.led_v_high = QDoubleSpinBox()
        self.led_v_high.setRange(-10, 10)
        self.led_v_high.setValue(3.0)
        self.led_v_high.setSuffix(" V")
        self.led_v_low = QDoubleSpinBox()
        self.led_v_low.setRange(-10, 10)
        self.led_v_low.setValue(0.0)
        self.led_v_low.setSuffix(" V")
        led.addRow("Train duration", self.led_train_spin)
        led.addRow("Cycles / train", self.led_cycles_spin)
        led.addRow("Duty cycle", self.led_duty_spin)
        led.addRow("Light intensity", self.led_intensity_spin)
        led.addRow("Inter-train pause", self.led_pause_spin)
        led.addRow("Rest voltage", self.led_v_high)
        led.addRow("Pulse voltage", self.led_v_low)
        root.addWidget(self.led_group)

        # Controls
        btns = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("btnStart")
        self.start_btn.clicked.connect(self.start_generation)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("btnStop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_generation)
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        root.addLayout(btns)

        # Status
        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusPanel")
        self.status_frame.setMinimumHeight(72)
        st = QVBoxLayout(self.status_frame)
        self.phase_label = QLabel("Ready")
        self.phase_label.setObjectName("statusPhase")
        self.phase_label.setAlignment(Qt.AlignCenter)
        self.countdown_label = QLabel("—")
        self.countdown_label.setObjectName("statusCountdown")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        st.addWidget(self.phase_label)
        st.addWidget(self.countdown_label)
        root.addWidget(self.status_frame)

        total_row = QHBoxLayout()
        muted = QLabel("Elapsed")
        muted.setObjectName("muted")
        self.elapsed_label = QLabel("0:00.00")
        self.elapsed_label.setObjectName("muted")
        total_row.addWidget(muted)
        total_row.addWidget(self.elapsed_label)
        total_row.addStretch()
        root.addLayout(total_row)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self._set_status_ready()

        if not DAQ_AVAILABLE:
            self.start_btn.setEnabled(False)
            self.start_btn.setToolTip("PyDAQmx is not installed")
            sb.showMessage("PyDAQmx unavailable — install NI-DAQmx + PyDAQmx")

        self._on_mode_changed()

    def _set_status_ready(self):
        self.phase_label.setText("Ready")
        self.phase_label.setStyleSheet("color: #9aa0a6;")
        self.countdown_label.setText("—")
        self.status_frame.setStyleSheet("")
        self.elapsed_label.setText("0:00.00")

    def _refresh_devices(self):
        devices = list_daq_devices()
        current = self.device_combo.currentText().strip()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        if devices:
            self.device_combo.addItems(devices)
            if current in devices:
                self.device_combo.setCurrentText(current)
            self.statusBar().showMessage(
                f"NI-DAQmx devices: {', '.join(devices)}"
            )
        else:
            self.device_combo.addItem(default_daq_device())
            self.statusBar().showMessage("No NI-DAQmx device detected")
        self.device_combo.blockSignals(False)

    def _on_mode_changed(self, *_):
        led = self.mode_combo.currentData() == "led"
        self.led_group.setVisible(led)
        self.classic_group.setVisible(not led)
        QTimer.singleShot(0, self._fit_height)

    def _fit_height(self):
        cw = self.centralWidget()
        if cw and cw.layout():
            cw.layout().activate()
        h = self.sizeHint().height()
        if h > 0:
            self.resize(self.width(), h)

    def _on_infinite_toggled(self, checked: bool):
        self.nb_spin.setEnabled(not checked)

    def _collect_config(self) -> GenerationConfig:
        return GenerationConfig(
            device=self.device_combo.currentText().strip() or default_daq_device(),
            channel=self.channel_edit.text().strip() or "ao0",
            sampling_rate=self.sampling_rate_spin.value(),
            mode=self.mode_combo.currentData() or "classic",
            infinite=self.infinite_check.isChecked(),
            nb_triggers=self.nb_spin.value(),
            initial_trigger_delay=self.delay_spin.value(),
            trigger_duration=self.trigger_spin.value(),
            inter_trigger_interval=self.interval_spin.value(),
            led_train_duration_s=self.led_train_spin.value(),
            led_nb_clignotement=self.led_cycles_spin.value(),
            led_duty_clignotement=self.led_duty_spin.value(),
            led_light_intensity=self.led_intensity_spin.value(),
            led_inter_train_interval=self.led_pause_spin.value(),
            led_voltage_high=self.led_v_high.value(),
            led_voltage_low=self.led_v_low.value(),
        )

    def _apply_config(self, cfg: GenerationConfig):
        self.device_combo.setCurrentText(cfg.device)
        self.channel_edit.setText(cfg.channel)
        self.sampling_rate_spin.setValue(cfg.sampling_rate)
        idx = self.mode_combo.findData(cfg.mode)
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.delay_spin.setValue(cfg.initial_trigger_delay)
        self.infinite_check.setChecked(cfg.infinite)
        self.nb_spin.setValue(cfg.nb_triggers)
        self.trigger_spin.setValue(cfg.trigger_duration)
        self.interval_spin.setValue(cfg.inter_trigger_interval)
        self.led_train_spin.setValue(cfg.led_train_duration_s)
        self.led_cycles_spin.setValue(cfg.led_nb_clignotement)
        self.led_duty_spin.setValue(cfg.led_duty_clignotement)
        self.led_intensity_spin.setValue(cfg.led_light_intensity)
        self.led_pause_spin.setValue(cfg.led_inter_train_interval)
        self.led_v_high.setValue(cfg.led_voltage_high)
        self.led_v_low.setValue(cfg.led_voltage_low)
        self._on_mode_changed()

    def _set_controls_enabled(self, enabled: bool):
        for w in (
            self.mode_combo,
            self.device_combo,
            self.channel_edit,
            self.sampling_rate_spin,
            self.classic_group,
            self.led_group,
            self.delay_spin,
            self.infinite_check,
            self.load_btn,
            self.refresh_dev_btn,
        ):
            w.setEnabled(enabled)
        self.nb_spin.setEnabled(enabled and not self.infinite_check.isChecked())

    def start_generation(self):
        if self.worker is not None and self.worker.isRunning():
            return
        cfg = self._collect_config()
        try:
            cfg.validate()
        except ValueError as e:
            QMessageBox.warning(self, "Settings", str(e))
            return

        devices = list_daq_devices()
        if DAQ_AVAILABLE and not devices:
            QMessageBox.critical(
                self,
                "Hardware",
                "No NI-DAQmx device detected.\n"
                "Connect the device and click Refresh devices.",
            )
            return
        if devices and cfg.device not in devices:
            QMessageBox.critical(
                self,
                "Hardware",
                f"Device '{cfg.device}' not found.\n"
                f"Available: {', '.join(devices)}",
            )
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_controls_enabled(False)
        self._session_active = True

        # Child process owns NI on its main thread (works in frozen exes).
        self.worker = DAQWorker(cfg)
        self.worker.generation_started.connect(self._on_started)
        self.worker.generation_finished.connect(self._on_finished)
        self.worker.generation_error.connect(self._on_error)

        self.worker_params = cfg.status_snapshot()
        self.experiment_start_time = datetime.now()
        self.statusBar().showMessage(f"Starting on {cfg.channel_path()}…")
        self.worker.start()

    def stop_generation(self):
        if self.worker is None:
            return
        self.statusBar().showMessage("Stopping…")
        self.worker.stop()

    def _on_started(self):
        self.statusBar().showMessage("Running")
        self.state_start_time = time.time()
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._tick_status)
        self.state_timer.start(100)

    def _tick_status(self):
        if self.state_start_time is None or self.worker_params is None:
            return
        elapsed = time.time() - self.state_start_time
        self.elapsed_label.setText(format_elapsed(elapsed))
        text, countdown, fg, bg = phase_display(elapsed, self.worker_params)
        self.phase_label.setText(text)
        self.phase_label.setStyleSheet(f"color: {fg};")
        self.countdown_label.setText(countdown)
        self.status_frame.setStyleSheet(
            f"QFrame#statusPanel {{ background-color: {bg}; border: 1px solid #2e3440; border-radius: 8px; }}"
        )

    def _on_finished(self):
        if not getattr(self, "_session_active", False):
            return
        self._session_active = False
        if self.state_timer:
            self.state_timer.stop()
            self.state_timer = None
        if self.state_start_time is not None and self.worker_params is not None:
            duration = time.time() - self.state_start_time
            record = build_experiment_record(
                self.worker_params,
                duration,
                self.experiment_start_time or datetime.now(),
            )
            path = experiences_dir() / datetime.now().strftime(
                "trigger_generator_%Y-%m-%d_%H-%M-%S.json"
            )
            try:
                save_experiment_record(record, path)
            except Exception:
                pass
        self.state_start_time = None
        self._set_status_ready()
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.wait(5000)
        self.start_btn.setEnabled(DAQ_AVAILABLE)
        self.stop_btn.setEnabled(False)
        self._set_controls_enabled(True)
        self.statusBar().showMessage("Idle")

    def _on_error(self, msg: str):
        # Child exits next and emits generation_finished (UI unlock).
        QMessageBox.critical(self, "Error", msg)

    def load_params(self, silent: bool = False):
        save_dir = experiences_dir()
        if not save_dir.exists():
            if not silent:
                QMessageBox.warning(self, "Load", "No experiments folder found.")
            return
        files = list(save_dir.glob("trigger_generator_*.json")) + list(
            save_dir.glob("wavegene_*.json")
        )
        if not files:
            if not silent:
                QMessageBox.warning(self, "Load", "No experiment file found.")
            return
        if silent:
            path = max(files, key=lambda p: p.stat().st_mtime)
        else:
            path_str, _ = QFileDialog.getOpenFileName(
                self,
                "Load parameters",
                str(save_dir),
                "JSON files (*.json);;All files (*)",
            )
            if not path_str:
                return
            path = Path(path_str)
        try:
            data = load_experiment_file(path)
            cfg = GenerationConfig.from_dict(data)
            devices = list_daq_devices()
            if devices and cfg.device not in devices and silent:
                cfg.device = devices[0]
            self._apply_config(cfg)
            if not silent:
                QMessageBox.information(self, "Load", f"Loaded {path.name}")
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Load", f"Failed to load:\n{e}")
