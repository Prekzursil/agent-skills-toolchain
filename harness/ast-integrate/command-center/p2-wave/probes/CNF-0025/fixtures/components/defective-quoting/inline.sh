#!/bin/sh
# Unfixed quoting: an interior apostrophe closes the single-quoted -c payload.
python3 -c 'print('hello')'
