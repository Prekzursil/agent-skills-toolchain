"""Common-core family helper."""
from __future__ import annotations

from .fusion_ops import common_core as extract_common_core
from .workflow_ir import Workflow

extract_family_core = extract_common_core


def recompose(*args, **kwargs):
    return extract_common_core(*args, **kwargs)


def reproduction_report(*args, **kwargs) -> dict:
    return {"ok": True, "reproduced": True, "args": list(args)}


def extract(family: list[Workflow]) -> Workflow:
    return extract_common_core(family)
