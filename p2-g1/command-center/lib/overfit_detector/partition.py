"""Independent held-out / visible partition from case hash."""
from __future__ import annotations

import hashlib

HELD_OUT = "held-out"
VISIBLE = "visible"


def independent_slice(case_id: str) -> str:
    digest = hashlib.sha256(str(case_id).encode("utf-8")).digest()
    return HELD_OUT if digest[0] & 1 else VISIBLE


def slice_of(case_id: str) -> str:
    return independent_slice(case_id)
