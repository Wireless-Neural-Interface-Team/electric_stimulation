# -*- coding: utf-8 -*-
"""LED train + inter-train pause (PWM / duty inside the train window)."""

import numpy as np

from ..timing import seconds_to_samples


def led_pattern_dimensions(sampling_rate_hz, train_duration_s, inter_train_interval_s):
    """
    Sample counts for one LED buffer (nearest-sample quantization).
    Returns (train_samples, timer_samples) where timer includes inter-train pause.
    """
    train_samples = seconds_to_samples(train_duration_s, sampling_rate_hz)
    pause_samples = seconds_to_samples(inter_train_interval_s, sampling_rate_hz)
    return train_samples, train_samples + pause_samples


def build_led_pattern(
    sampling_rate_hz,
    train_duration_s,
    n_cycles,
    train_duty,
    light_intensity,
    inter_train_interval_s,
    voltage_high=3.0,
    voltage_low=0.0,
):
    """
    One LED pattern buffer (train + pause at voltage_high).

    n_cycles: blinks inside the train window (equal slots ±1 sample).
    train_duty: fraction of each slot at pulse voltage.
    light_intensity: 0–1 PWM over active samples (Bresenham spread).
    """
    if train_duration_s <= 0:
        raise ValueError("Train duration must be positive.")
    if not (0.0 <= light_intensity <= 1.0):
        raise ValueError("Light intensity must be between 0 and 1.")
    if not (0.0 <= train_duty <= 1.0):
        raise ValueError("Train duty cycle must be between 0 and 1.")
    if n_cycles < 1:
        raise ValueError("Cycles per train must be at least 1.")

    train_samples, timer = led_pattern_dimensions(
        sampling_rate_hz, train_duration_s, inter_train_interval_s
    )
    sig = np.full(timer, voltage_high, dtype=np.float64)
    if train_samples <= 0 or light_intensity <= 0:
        return sig

    n_cycles = int(n_cycles)
    base = train_samples // n_cycles
    if base <= 0:
        raise ValueError(
            "Train period has too few samples for this many blinks. "
            "Raise sampling rate, increase train duration, or reduce cycles per train."
        )
    rem = train_samples % n_cycles
    lengths = np.empty(n_cycles, dtype=np.intp)
    if rem > 0:
        lengths[:rem] = base + 1
        lengths[rem:] = base
    else:
        lengths[:] = base

    starts = np.zeros(n_cycles, dtype=np.intp)
    if n_cycles > 1:
        starts[1:] = np.cumsum(lengths[:-1])

    avg_cell = train_samples / float(n_cycles)
    pulse_w = int(np.ceil(avg_cell * train_duty))
    pulse_w = max(0, min(pulse_w, base))
    if pulse_w <= 0:
        return sig

    ws = np.minimum(pulse_w, lengths)
    active = np.zeros(train_samples, dtype=bool)
    for k in range(n_cycles):
        w = int(ws[k])
        if w <= 0:
            continue
        s = int(starts[k])
        active[s : s + w] = True

    idx_on = np.flatnonzero(active)
    l_act = int(idx_on.size)
    k_low = max(0, min(l_act, int(round(l_act * light_intensity))))

    sig[:train_samples] = voltage_high
    if k_low >= l_act:
        sig[idx_on] = voltage_low
    elif k_low > 0:
        i = np.arange(l_act, dtype=np.intp)
        pick = (i + 1) * k_low // l_act > i * k_low // l_act
        sig[idx_on[pick]] = voltage_low
    return sig
