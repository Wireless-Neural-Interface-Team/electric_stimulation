# -*- coding: utf-8 -*-
"""Compatibility shim — prefer electric_stimulation.gui."""

from .gui import TriggerGeneratorWindow, main

__all__ = ["TriggerGeneratorWindow", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
