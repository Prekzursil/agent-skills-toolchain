#!/bin/sh
# Control-bad: apostrophe interpolated into POSIX single quotes.
# The value o'reilly breaks the quoting; argv must NOT match.
python3 argv_echo.py 'o'reilly'
