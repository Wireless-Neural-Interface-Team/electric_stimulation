# -*- coding: utf-8 -*-
"""Generation configuration (UI ↔ DAQ contract)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from .timing import samples_to_seconds, seconds_to_samples
from .waveforms import led_pattern_dimensions


@dataclass
class GenerationConfig:
    """All parameters needed to run one stimulation session."""

    device: str = "Dev1"
    channel: str = "ao0"
    sampling_rate: float = 1000.0
    mode: str = "classic"  # "classic" | "led"
    infinite: bool = True
    nb_triggers: int = 5
    initial_trigger_delay: float = 5.0

    # Classic
    trigger_duration: float = 0.2
    inter_trigger_interval: float = 20.0
    pulse_voltage: float = 3.0

    # LED
    led_train_duration_s: float = 1.0
    led_nb_clignotement: int = 1
    led_duty_clignotement: float = 1.0
    led_light_intensity: float = 1.0
    led_inter_train_interval: float = 2.0
    led_voltage_high: float = 3.0
    led_voltage_low: float = 0.0

    def channel_path(self) -> str:
        dev = (self.device or "Dev1").strip() or "Dev1"
        ch = (self.channel or "ao0").strip() or "ao0"
        return f"{dev}/{ch}"

    def delay_samples(self) -> int:
        return seconds_to_samples(self.initial_trigger_delay, self.sampling_rate)

    def classic_trigger_samples(self) -> int:
        return seconds_to_samples(self.trigger_duration, self.sampling_rate)

    def classic_interval_samples(self) -> int:
        return seconds_to_samples(self.inter_trigger_interval, self.sampling_rate)

    def validate(self) -> None:
        if self.sampling_rate <= 0:
            raise ValueError("Sampling rate must be positive.")
        if self.mode == "classic":
            if self.classic_trigger_samples() < 1:
                raise ValueError(
                    "Trigger duration is too short for the selected sampling rate."
                )
        elif self.mode == "led":
            if self.led_train_duration_s <= 0:
                raise ValueError("Train duration must be positive.")
            train_s, _ = led_pattern_dimensions(
                self.sampling_rate,
                self.led_train_duration_s,
                self.led_inter_train_interval,
            )
            if train_s < int(self.led_nb_clignotement):
                raise ValueError(
                    "Train duration yields too few samples for this many blinks. "
                    "Increase sampling rate or train duration, or reduce cycles."
                )
        else:
            raise ValueError(f"Unknown mode: {self.mode!r}")

    def status_snapshot(self) -> Dict[str, Any]:
        """Quantized timings for the on-screen phase indicator."""
        sr = float(self.sampling_rate)
        delay_s = self.delay_samples()
        trig_s = self.classic_trigger_samples()
        gap_s = self.classic_interval_samples()
        led_train, led_timer = led_pattern_dimensions(
            sr, self.led_train_duration_s, self.led_inter_train_interval
        )
        return {
            "device": self.device,
            "channel": self.channel,
            "sampling_rate": sr,
            "mode": self.mode,
            "infinite": self.infinite,
            "nb_triggers": int(self.nb_triggers),
            "initial_trigger_delay": samples_to_seconds(delay_s, sr),
            "initial_delay_samples": delay_s,
            "trigger": samples_to_seconds(trig_s, sr),
            "interval": samples_to_seconds(gap_s, sr),
            "trigger_samples": trig_s,
            "interval_samples": gap_s,
            "led_train_samples": led_train,
            "led_timer_samples": led_timer,
            "led_train_duration_s": samples_to_seconds(led_train, sr),
            "led_inter_train_interval": samples_to_seconds(led_timer - led_train, sr),
            "led_nb_clignotement": int(self.led_nb_clignotement),
            "led_duty_clignotement": float(self.led_duty_clignotement),
            "led_light_intensity": float(self.led_light_intensity),
            "led_voltage_high": float(self.led_voltage_high),
            "led_voltage_low": float(self.led_voltage_low),
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        # Legacy JSON keys
        mapped = dict(data)
        if "trigger_duration" not in mapped and "pulse_duration" in mapped:
            mapped["trigger_duration"] = mapped["pulse_duration"]
        if "inter_trigger_interval" not in mapped and "inter_pulse_interval" in mapped:
            mapped["inter_trigger_interval"] = mapped["inter_pulse_interval"]
        if "nb_triggers" not in mapped and "nb_pulses" in mapped:
            mapped["nb_triggers"] = mapped["nb_pulses"]
        kwargs = {k: v for k, v in mapped.items() if k in known}
        return cls(**kwargs)
