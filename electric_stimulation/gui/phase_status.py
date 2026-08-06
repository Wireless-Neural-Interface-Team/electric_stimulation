# -*- coding: utf-8 -*-
"""Phase / countdown text for the live status panel."""

from __future__ import annotations

from typing import Any, Dict, Tuple


def format_elapsed(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:05.2f}"


def format_countdown(seconds: float) -> str:
    if seconds <= 0:
        return "0.00 s"
    return f"{seconds:.2f} s remaining"


def phase_display(elapsed: float, params: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """
    Returns (phase_text, countdown, fg_color, panel_bg).
    Colors are tuned for the dark instrument theme.
    """
    initial_delay = float(params.get("initial_trigger_delay", 0))
    sr = float(params.get("sampling_rate", 1000)) or 1000.0

    if params.get("mode") == "led":
        vh = float(params.get("led_voltage_high", 3.0))
        train_s = int(params.get("led_train_samples", 1))
        timer_s = max(1, int(params.get("led_timer_samples", 1)))
        train_dur = train_s / sr
        cycle_dur = timer_s / sr
        if elapsed < initial_delay:
            return (
                f"LED — wait ({vh:.1f} V rest)",
                format_countdown(initial_delay - elapsed),
                "#9aa0a6",
                "#1a1d23",
            )
        t_loop = elapsed - initial_delay
        if not params.get("infinite"):
            total_dur = int(params.get("nb_triggers", 1)) * cycle_dur
            if t_loop >= total_dur:
                return "Done", "—", "#9aa0a6", "#1a1d23"
        pos = t_loop % cycle_dur
        if pos < train_dur:
            return (
                "LED — train (PWM)",
                format_countdown(train_dur - pos),
                "#c4b5fd",
                "#1e1830",
            )
        return (
            "LED — pause",
            format_countdown(cycle_dur - pos),
            "#94a3b8",
            "#171b22",
        )

    trigger = float(params.get("trigger", 0.2))
    interval = float(params.get("interval", 20))
    cycle_duration = trigger + interval
    if elapsed < initial_delay:
        return (
            "Idle (0 V)",
            format_countdown(initial_delay - elapsed),
            "#9aa0a6",
            "#1a1d23",
        )
    cycle_time = elapsed - initial_delay
    if not params.get("infinite"):
        total_cycles = int(params.get("nb_triggers", 1)) * cycle_duration
        if cycle_time >= total_cycles:
            return "Done", "—", "#9aa0a6", "#1a1d23"
    pos = cycle_time % cycle_duration
    if pos < trigger:
        return (
            "Trigger (3 V)",
            format_countdown(trigger - pos),
            "#86efac",
            "#14241a",
        )
    return (
        "Interval (0 V)",
        format_countdown(cycle_duration - pos),
        "#94a3b8",
        "#171b22",
    )
