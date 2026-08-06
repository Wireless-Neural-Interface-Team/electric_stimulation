# -*- coding: utf-8 -*-
"""Sample-clock quantization helpers (shared by waveforms and DAQ)."""


def seconds_to_samples(seconds: float, sampling_rate: float) -> int:
    """Nearest non-negative sample count on the AO clock."""
    return max(0, int(round(float(seconds) * float(sampling_rate))))


def samples_to_seconds(samples: int, sampling_rate: float) -> float:
    """Exact duration implied by a sample count at the given rate."""
    rate = float(sampling_rate)
    if rate <= 0:
        return 0.0
    return float(samples) / rate
