"""Draft 2020-12 validation for CNL-0109 records."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema.validators import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Catalog output_schema is a generated shim without $defs.preset. The
# executable Draft 2020-12 contract for this unit lives next to the probes.
LOCAL_SCHEMA = HERE / "council-preset.schema.json"
SHARED_SCHEMA = REPO / "command-center/schema/council-preset.schema.json"
SCHEMA_PATH = LOCAL_SCHEMA if LOCAL_SCHEMA.is_file() else SHARED_SCHEMA


def load_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if "preset" not in (schema.get("$defs") or {}):
        raise RuntimeError(
            f"{SCHEMA_PATH} has no $defs.preset; expected the unit-local "
            "CNL-0109 contract (shared catalog path is a generated shim)"
        )
    return schema


def preset_validator() -> Draft202012Validator:
    schema = load_schema()
    return Draft202012Validator(schema["$defs"]["preset"] | {"$defs": schema["$defs"]})


def family_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def error_messages(validator: Draft202012Validator, instance: Any) -> list[str]:
    return [
        f"{list(err.absolute_path)}: {err.message}"
        for err in validator.iter_errors(instance)
    ]


def ranked_choice_portfolio_mutant(good: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(good)
    mutant["outcome_type"] = "budget_portfolio"
    mutant["delta"]["voting"]["rule"] = "ranked-choice"
    mutant["id"] = "council.preset.NEG.ranked-choice-on-portfolio"
    return mutant
