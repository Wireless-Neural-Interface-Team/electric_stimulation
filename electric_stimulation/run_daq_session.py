# -*- coding: utf-8 -*-
"""Frozen/console entry point for the DAQ child process only (no GUI)."""

import sys

from electric_stimulation.daq.cli_session import main

if __name__ == "__main__":
    # Allow optional --daq-session flag from the GUI launcher.
    argv = [a for a in sys.argv[1:] if a != "--daq-session"]
    sys.exit(main(argv))
