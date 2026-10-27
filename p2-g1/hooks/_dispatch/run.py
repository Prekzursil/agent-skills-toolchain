#!/usr/bin/env python3
"""Dispatch runner used as a production surface for IMP-0404 AST scan."""
from __future__ import annotations

from router.hook_contract import handle, main

__all__ = ["handle", "main"]
