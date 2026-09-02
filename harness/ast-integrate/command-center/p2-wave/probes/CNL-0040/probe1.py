#!/usr/bin/env python3
import runpy

runpy.run_path(
    str(__import__("pathlib").Path(__file__).resolve().parent / "probe1_family_schedules.py"),
    run_name="__main__",
)
