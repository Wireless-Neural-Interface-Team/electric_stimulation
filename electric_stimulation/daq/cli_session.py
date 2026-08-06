# -*- coding: utf-8 -*-
"""
CLI entry for the DAQ child process (no Qt).

Status protocol (append one JSON object per line to --status-file):
  {"event":"boot"}
  {"event":"started"}
  {"event":"done"}
  {"event":"error","message":"..."}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path


def _fix_stdio() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _emit(status_path: Path, obj: dict) -> None:
    try:
        with status_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    _fix_stdio()

    parser = argparse.ArgumentParser(description="Trigger Generator DAQ session")
    parser.add_argument("--config", required=True)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--daq-session", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    stop_path = Path(args.stop_file)
    status_path = Path(args.status_file)

    try:
        if stop_path.exists():
            stop_path.unlink()
    except Exception:
        pass
    try:
        status_path.write_text("", encoding="utf-8")
    except Exception:
        pass

    # Prove the child is alive before importing NI / numpy.
    _emit(status_path, {"event": "boot", "argv": list(sys.argv)})

    try:
        from ..models import GenerationConfig
        from . import nicaiu as _nicaiu
        from .session_runner import format_session_error, run_ao_session, stop_file_checker

        _emit(status_path, {"event": "progress", "message": f"nicaiu={_nicaiu.load_info()}"})
    except Exception as e:
        _emit(
            status_path,
            {
                "event": "error",
                "message": f"Import failed in DAQ child:\n{e}\n{traceback.format_exc()}",
            },
        )
        return 3

    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        cfg = GenerationConfig.from_dict(data)
    except Exception as e:
        _emit(status_path, {"event": "error", "message": f"Invalid config: {e}"})
        return 2

    try:
        _emit(status_path, {"event": "arming", "channel": cfg.channel_path()})
        run_ao_session(
            cfg,
            should_stop=stop_file_checker(stop_path),
            on_started=lambda: _emit(status_path, {"event": "started"}),
            on_progress=lambda msg: _emit(status_path, {"event": "progress", "message": msg}),
        )
        _emit(status_path, {"event": "done"})
        return 0
    except Exception as e:
        _emit(status_path, {"event": "error", "message": format_session_error(e, cfg)})
        return 1
    finally:
        try:
            if stop_path.exists():
                stop_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
