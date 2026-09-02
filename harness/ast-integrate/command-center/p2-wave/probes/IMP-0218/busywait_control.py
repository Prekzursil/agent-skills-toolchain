#!/usr/bin/env python3
"""Negative-control waiter: stays resident until killed.

Used by probe1 to prove the process-table counter fires on a real waiter and
is silent after the waiter is gone. This is NOT the HumanCheckpoint executor.
"""

from __future__ import annotations

import argparse
import time

parser = argparse.ArgumentParser()
parser.add_argument("--marker", required=True)
args = parser.parse_args()
while True:
    time.sleep(30)
