# -*- coding: utf-8 -*-
"""Paths and JSON I/O for saved experiment parameters."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def experiences_dir() -> Path:
    return app_dir() / "experiences"


def build_experiment_record(
    worker_params: Dict[str, Any],
    duration_seconds: float,
    start_time: datetime,
    end_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    if end_time is None:
        end_time = datetime.now()
    p = worker_params
    return {
        "device": p.get("device", "Dev1"),
        "channel": p.get("channel", "ao0"),
        "sampling_rate": p.get("sampling_rate", 1000),
        "trigger_duration": p.get("trigger", p.get("trigger_duration", 0.2)),
        "inter_trigger_interval": p.get(
            "interval", p.get("inter_trigger_interval", 20)
        ),
        "initial_trigger_delay": p.get("initial_trigger_delay", 5),
        "infinite": p.get("infinite", True),
        "nb_triggers": p.get("nb_triggers", 5),
        "mode": p.get("mode", "classic"),
        "led_train_duration_s": p.get("led_train_duration_s", 1.0),
        "led_nb_clignotement": p.get("led_nb_clignotement", 1),
        "led_duty_clignotement": p.get("led_duty_clignotement", 1.0),
        "led_light_intensity": p.get("led_light_intensity", 1.0),
        "led_inter_train_interval": p.get("led_inter_train_interval", 2.0),
        "led_voltage_high": p.get("led_voltage_high", 3.0),
        "led_voltage_low": p.get("led_voltage_low", 0.0),
        "duration_seconds": round(duration_seconds, 2),
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_experiment_record(record: Dict[str, Any], filepath) -> None:
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


def load_experiment_file(filepath) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
