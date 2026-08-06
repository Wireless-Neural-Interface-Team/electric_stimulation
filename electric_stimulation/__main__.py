# -*- coding: utf-8 -*-
"""python -m electric_stimulation"""

import os
import sys


def _is_daq_session() -> bool:
    if "--daq-session" in sys.argv:
        return True
    return os.environ.get("TG_DAQ_SESSION", "").strip() == "1"


if _is_daq_session():
    from .daq.cli_session import main as daq_main

    argv = [a for a in sys.argv[1:] if a != "--daq-session"]
    raise SystemExit(daq_main(argv))

from .gui import main

raise SystemExit(main())
