# -*- coding: utf-8 -*-
"""Launcher for Trigger Generator (GUI) or DAQ child session."""

import os
import sys


def _is_daq_session() -> bool:
    if "--daq-session" in sys.argv:
        return True
    return os.environ.get("TG_DAQ_SESSION", "").strip() == "1"


def _dispatch() -> int:
    # Child process: NI-DAQmx on this process main thread (no GUI / no Qt).
    if _is_daq_session():
        from electric_stimulation.daq.cli_session import main as daq_main

        argv = [a for a in sys.argv[1:] if a != "--daq-session"]
        return daq_main(argv)

    from electric_stimulation.gui import main

    return main()


if __name__ == "__main__":
    sys.exit(_dispatch())
