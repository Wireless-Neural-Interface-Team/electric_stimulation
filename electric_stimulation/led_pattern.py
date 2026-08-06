# -*- coding: utf-8 -*-
"""Compatibility shim — prefer electric_stimulation.waveforms.led."""

from .waveforms.led import build_led_pattern, led_pattern_dimensions

__all__ = ["build_led_pattern", "led_pattern_dimensions"]
