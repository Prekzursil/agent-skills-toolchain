#!/usr/bin/env python3
"""Consumer call site: validate a completion verdict against ARC-0087."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from evaluator import CONTRACT_PATH, load_contract


def validate_verdict(verdict: dict[str, Any], contract: dict[str, Any] | None = None) -> None:
    """Real call site: Draft 2020-12 validation of a predicate verdict instance."""
    schema = contract if contract is not None else load_contract()
    if not CONTRACT_PATH.is_file():
        raise FileNotFoundError(CONTRACT_PATH)
    Draft202012Validator(schema).validate(verdict)
