# -*- coding: utf-8 -*-
"""Classic 0 V / 3 V pulse cycle."""

import numpy as np

from ..timing import seconds_to_samples

_PULSE_VOLTAGE = 3.0


def build_classic_cycle(
    sampling_rate: float,
    trigger_duration_s: float,
    inter_trigger_interval_s: float,
    pulse_voltage: float = _PULSE_VOLTAGE,
) -> np.ndarray:
    """
    One classic cycle: high pulse then idle at 0 V.
    Length = round(trigger×fs) + round(interval×fs) samples.
    """
    trigger_samples = seconds_to_samples(trigger_duration_s, sampling_rate)
    interval_samples = seconds_to_samples(inter_trigger_interval_s, sampling_rate)
    if trigger_samples < 1:
        raise ValueError(
            "Classic mode: trigger duration is too short for the selected sampling rate."
        )
    sig = np.zeros(trigger_samples + interval_samples, dtype=np.float64)
    sig[:trigger_samples] = float(pulse_voltage)
    return sig
