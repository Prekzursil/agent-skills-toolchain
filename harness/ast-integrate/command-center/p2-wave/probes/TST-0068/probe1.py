#!/usr/bin/env python3
"""Thin alias so probe1.py exists beside the named script."""
from probe1_every_entry_declares_interpreter import main

if __name__ == "__main__":
    raise SystemExit(main())
