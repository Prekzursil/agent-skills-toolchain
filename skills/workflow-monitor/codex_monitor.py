#!/usr/bin/env python3
"""Thin deployed entry point for ``mon codex``; all behavior lives in monitorcore."""

from monitorcore.codex_source import main


if __name__ == "__main__":
    raise SystemExit(main())
