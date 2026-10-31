"""Import surface for completion conditions 11 and 12.

CC-0003's reducer (platform/lib/completion_predicate.py) evaluates receipt
*fields*. This module is the filesystem half: register-on-write into
command-center/ARTIFACT-MANIFEST.json and a reader that opens each row with
the consumer that claims to read it.

    from completion_c11_c12 import check_condition_11, check_condition_12

A reducer that only inspects a path string is the existence check CC-0009
forbids. Do not re-export unit_manifest.derive — that is a different corpus.
"""
from __future__ import annotations

from artifact_register import (  # noqa: F401
    CheckResult,
    check_condition_11,
    check_condition_12,
    evaluate_manifest,
    register_path,
    write_registered,
)

__all__ = [
    "CheckResult",
    "check_condition_11",
    "check_condition_12",
    "evaluate_manifest",
    "register_path",
    "write_registered",
]
