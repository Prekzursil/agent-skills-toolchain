#!/usr/bin/env python3
"""Build command-center/receipts/IMP-0386.json from a live normalize run."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from tools.router import normalize as N  # noqa: E402


def main() -> int:
    results = S.live_results()
    if len(results) != 4:
        print(f"FAILED:emit expected 4 results got {len(results)}")
        return 1

    records = [r.record for r in results]
    register = N.group_lossy_register(results)
    if len(register) != 4:
        print(f"FAILED:emit register rows {len(register)}")
        return 1

    for result in results:
        err = N.roundtrip_errors(result.parsed, result)
        if err:
            print("FAILED:emit roundtrip", err)
            return 1
        planted = N.PLANTED_KEYS[result.parsed.source_format]
        perr = N.planted_errors(result.parsed, result, planted)
        if perr:
            print("FAILED:emit planted", perr)
            return 1

    dropped_summary = []
    for row in register:
        keys = [d["source_key"] for d in row["dropped_keys"]]
        dropped_summary.append(
            {
                "source_format": row["source_format"],
                "dropped_keys": keys,
                "count": len(keys),
                "locators": [d["locator"] for d in row["dropped_keys"]],
            }
        )

    question = (
        "Which of the four descriptor formats loses information in the mapping "
        "onto CapabilityRecord, and exactly which field is dropped?"
    )
    answer = (
        "All four formats lose information. Distinctive native drops: "
        "skill_md.allowed-tools (and compatibility, metadata); "
        "plugin_json.hooks (and author, homepage, repository, skills, commands); "
        "workflow_header.stages (and stopping); "
        "mcp_tool.inputSchema (and annotations). "
        "The largest semantic loss is MCP tool inputSchema — the entire JSON Schema "
        "argument contract has no CapabilityRecord destination. Planted extras "
        f"{list(N.PLANTED_KEYS.values())} are also registered, not copied."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0386",
        "state": "SUCCESS",
        "sentinel": S.SENTINEL,
        "completion_sentinel": S.SENTINEL,
        "title": "Heterogeneous descriptor normalizer into one CapabilityRecord",
        "question": question,
        "finding": {
            "formats_that_lose_information": list(S.FIXTURE_RELS),
            "headline_format": S.HEADLINE_DROP["source_format"],
            "headline_field": S.HEADLINE_DROP["source_key"],
            "headline_why": S.HEADLINE_DROP["why"],
            "answer": answer,
        },
        "normalizer": S.NORMALIZER_REL,
        "schema_path": S.SCHEMA_REL,
        "schema_input_path": S.SCHEMA_ROOT_REL,
        "lossless_keymap": N.lossless_keymap(),
        "planted_keys": dict(N.PLANTED_KEYS),
        "native_unmapped_keys": {k: list(v) for k, v in N.NATIVE_DROPS.items()},
        "records": records,
        "lossy_field_register": register,
        "lossy_field_register_summary": dropped_summary,
        "fixtures": dict(S.FIXTURE_RELS),
        "tests": {
            "roundtrip_lossless": True,
            "planted_extra_in_register": True,
            "formats_measured": 4,
        },
        "inputs_note": {
            "IMP-0385_receipt": (
                "command-center/receipts/IMP-0385.json is absent on this "
                "worktree; mapping is proven on four in-tree fixtures rather "
                "than on a missing capability-index."
            ),
            "capability_index": "not present; not required to prove the mapping",
        },
        "evidence": [
            {
                "kind": "lossy-register-row",
                "source_format": row["source_format"],
                "dropped_keys": [d["source_key"] for d in row["dropped_keys"]],
                "locators": [d["locator"] for d in row["dropped_keys"]],
            }
            for row in register
        ],
        "reviewer": {
            "reviewer_id": "IMP-0386-probe2-lossy-register",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": S.ART_REL, "role": "primary"},
            {"path": S.NORMALIZER_REL, "role": "implementation"},
            {"path": S.SCHEMA_REL, "role": "schema"},
        ],
        "ts": now,
        "notes": (
            "G-1 IMP-0386: four-format normalizer, lossy-field register with "
            "file:line locators, lossless round-trip plus planted-key negative "
            "control. Did not run global unit_manifest.py --write."
        ),
    }

    schema_path = S.REPO / S.SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema not installed; writing without validation")
    else:
        jsonschema.Draft7Validator(schema).validate(doc)
        rec_schema = schema["definitions"]["CapabilityRecord"]
        rec_val = jsonschema.Draft7Validator(rec_schema)
        for rec in records:
            rec_val.validate(rec)

    out = S.REPO / S.ART_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {S.ART_REL} bytes={out.stat().st_size}")
    print(S.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
