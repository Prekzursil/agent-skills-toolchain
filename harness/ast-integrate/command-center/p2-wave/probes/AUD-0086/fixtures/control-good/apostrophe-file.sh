#!/bin/sh
# Control-good: same payload arrives as a file path / positional arg, not
# interpolated into single quotes.
python3 argv_echo.py "$1"
