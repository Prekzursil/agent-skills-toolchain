#!/usr/bin/env python3
"""Probe 2: enumerate which artifact fields are rendered into model context."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import CATALOG_FIELDS, UNIT  # noqa: E402
import common as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    names = list(dict.fromkeys(C.interpolated_names_in_prompt_for()))
    mentioned = C.catalog_keys_mentioned_in_dispatcher()
    leftover = C.leftover_rejects_beacon_uid()
    delimiter = C.estate_corpus_delimiter()
    dispatch = C.cursor_dispatch_prompt(UNIT)
    unit = C.load_live_unit()

    field_surface = []
    for key in CATALOG_FIELDS:
        live_val = unit.get(key)
        snippet = json.dumps(live_val) if not isinstance(live_val, str) else live_val
        in_prompt = bool(snippet) and str(snippet) in dispatch and key != "id"
        # Live values can coincidentally appear; require the field name as well.
        field_surface.append(
            {
                "field": key,
                "mentioned_in_dispatcher_source": key in mentioned,
                "live_value_in_prompt_for": in_prompt,
                "rendered_into_model_context_by_prompt_for": False
                if key not in mentioned
                else in_prompt,
            }
        )

    surfaces = [
        {
            "id": "cursor-dispatch-prompt_for",
            "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "interpolated_names": names,
            "includes_catalog_fields": mentioned,
            "includes_unit_id": UNIT in dispatch,
            "instructs_start_from_probe_dir": f"probes/{UNIT}/" in dispatch,
            "trust_fence_in_prompt": "BEGIN UNTRUSTED" in dispatch,
        },
        {
            "id": "catalog-executed-as-task-description",
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "note": (
                "A G-1 delivery agent looks up the catalog unit by id. Every "
                "consumer-owned field on that row is therefore model-reachable "
                "even when prompt_for interpolates only the uid."
            ),
            "fields": list(CATALOG_FIELDS),
        },
        {
            "id": "leftover-id-gate",
            "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            "uid_re": leftover["pattern"],
            "accepts": leftover["accepts"],
            "note": "Leftover ids that fail UID_RE never enter prompt_for.",
        },
        {
            "id": "owner-decisions-render",
            "path": "tools/command-center/render.py",
            "fields": ["owner_questions.text", "owner_questions.answer", "owner_questions.answer_detail"],
            "note": "render_owner_decisions copies catalog owner_questions into OWNER-DECISIONS.md.",
        },
        {
            "id": "estate-untrusted-corpus-delimiter",
            "present": delimiter["present"],
            "hits": delimiter["hits"],
            "needles": delimiter["needles"],
        },
    ]

    errors: list[str] = []
    if names != ["uid"] and set(names) != {"uid"}:
        errors.append(f"prompt_for interpolated unexpected names {names}")
    if mentioned:
        errors.append(f"dispatcher source mentions catalog fields {mentioned}")
    if leftover["accepts"].get("canonical") is not True:
        errors.append("UID_RE rejected the canonical unit id")
    if leftover["accepts"].get("beacon_in_id") or leftover["accepts"].get("instruction_as_id"):
        errors.append("UID_RE accepted a beacon-bearing leftover id")
    if any(row["rendered_into_model_context_by_prompt_for"] for row in field_surface):
        errors.append("prompt_for rendered a catalog field into the model prompt")
    if UNIT not in dispatch:
        errors.append("prompt_for omitted the unit id")

    out = {
        "probe": "probe2-context-fields",
        "unit_id": UNIT,
        "pass": not errors,
        "errors": errors,
        "prompt_for_interpolated_names": names,
        "catalog_fields": field_surface,
        "surfaces": surfaces,
        "estate_delimiter_present": delimiter["present"],
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    if errors:
        return fail("; ".join(errors))
    print(
        "interpolated_names="
        + ",".join(names)
        + " catalog_fields_in_prompt_for=0 leftover_gate=UID_RE"
    )
    print(f"SUCCESS:{UNIT}-probe2 context-fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
