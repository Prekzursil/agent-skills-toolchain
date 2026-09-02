"""Argv-array process launcher. No shell=True on the shipped path."""
from __future__ import annotations

from .explicit_interpreter import argv_for, launch

__all__ = ["argv_for", "launch"]
