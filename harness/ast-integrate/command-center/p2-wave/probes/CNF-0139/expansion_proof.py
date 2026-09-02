"""Load the live confirmation expansion_proof without shadowing it."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_REAL = Path(__file__).resolve().parents[3] / "confirmation" / "expansion_proof.py"
_spec = importlib.util.spec_from_file_location("cnf0139_expansion_proof_real", _REAL)
if _spec is None or _spec.loader is None:
    raise ImportError(f"missing {_REAL}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

antithrash = _mod.antithrash
both_states = _mod.both_states
boundary = _mod.boundary
denominator_control = _mod.denominator_control
reviewer_slip_attempts = _mod.reviewer_slip_attempts
run_all = _mod.run_all
