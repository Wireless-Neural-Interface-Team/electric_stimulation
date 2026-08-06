# Electric stimulation

GUI to generate electrical trigger signals via **National Instruments NI-DAQmx** (micro-electrode array neurostimulation).

**Platforms:** Windows, macOS, Linux · **Python:** ≥ 3.8 · **PyPI:** `electric-stimulation`

## Architecture (v0.4)

```
electric_stimulation/
  models.py          GenerationConfig (typed protocol parameters)
  timing.py          sample-clock quantization
  waveforms/         classic + LED buffers (NumPy)
  daq/               NI-DAQmx devices, tasks, QThread worker
  gui/               PyQt5 application (Fusion + instrument theme)
  experiment_io.py   JSON save/load next to the exe
```

Legacy modules (`trigger_generator_gui`, `trigger_generator_backend`, `led_pattern`) remain as thin compatibility shims.

## Install

```bash
uv venv si_env --python 3.12
# Windows: si_env\Scripts\activate
# macOS/Linux: source si_env/bin/activate
uv pip install electric-stimulation
# or from repo: uv pip install -e ".[build]"
```

Requires [NI-DAQmx](https://www.ni.com/en/support/downloads/drivers/download.ni-daqmx.html) on the machine.

## Run

```bash
trigger-generator
# or
python -m electric_stimulation
```

## Build standalone executable

```bash
trigger-generator-build
# → dist/TriggerGenerator.exe (Windows) or dist/TriggerGenerator
```

## Notes

- Only **one** application instance at a time (NI AO cannot be shared).
- Timings are quantized to the AO sample clock (`round(seconds × fs)`).
- Infinite mode uses hardware-timed continuous regeneration; Stop aborts the task immediately.
