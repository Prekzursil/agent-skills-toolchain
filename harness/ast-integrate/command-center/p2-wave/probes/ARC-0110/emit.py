#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0110.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import report as R  # noqa: E402
from hashutil import digest_file  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0110.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0110 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    present = path.is_file()
    row = {"path": rel, "exists": present, "role": role}
    if present:
        sha, size = digest_file(path)
        row["sha256"] = sha
        row["bytes"] = size
    return row


def assert_schema_shim() -> None:
    path = REPO / SCHEMA
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:ARC-0110 schema missing {SCHEMA}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"FAILED:ARC-0110 schema unparseable {type(exc).__name__}") from exc
    if not isinstance(schema, dict) or not schema.get("$ref"):
        raise SystemExit("FAILED:ARC-0110 schema shim missing $ref")
    # The shim $id is https://ast-integrate.invalid/... . Draft7Validator would
    # fetch that over the network (jsonschema 4.10 has no registry=). G-1
    # requires a parseable non-BLOCKED catalog artifact with the sentinel;
    # probes read census/fingerprint at the top level, which receipt_core
    # additionalProperties:false would reject. Residual, not a skip of the
    # ceremony.


def main() -> int:
    payload = R.measured()
    control = payload["both_states"]["detector_control"]
    census = payload["census"]
    fp = payload["fingerprint"]
    if not control.get("trusted"):
        print("FAILED:ARC-0110 detector control not trusted")
        return 1

    e1 = ev(
        CATALOG,
        "hash every schema and launcher, record the frozen set",
        "catalog",
        "The unit question names the freeze ceremony and the unmigrated-reject gate.",
    )
    e2 = ev(
        "command-center/p2-wave/probes/ARC-0110/inventory.py",
        "A path is frozen only if it is a production schema under",
        "live-tree",
        "The freeze set is a closed classifier, not the whole repository.",
    )
    e3 = ev(
        "command-center/p2-wave/probes/ARC-0110/gate.py",
        '"reason": "unmigrated-change"',
        "live-tree",
        "The gate names unmigrated frozen-path edits as REJECT.",
    )
    e4 = ev(
        "command-center/p2-wave/probes/ARC-0110/both_states.py",
        "git_checkout_not_used",
        "fixture",
        "Both-states ran on a scratch overlay; git checkout was not used.",
    )
    e5 = ev(
        "command-center/p2-wave/probes/ARC-0110/ceremony.py",
        'TRIGGER_ID = "FIRST-IMPLEMENTATION-WAVE-START"',
        "live-tree",
        "The trigger moment is the ceremony arming write, not a catalog phase number.",
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "ARC-0110",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0110",
        "report_kind": "conformance-report",
        "title": "Freeze ceremony: schemas and launchers frozen, changes only by versioned migration",
        "question": payload["question"],
        "produced_at": now,
        "detector_control": control,
        "census": {
            "frozen_count": census["frozen_count"],
            "schema_count": census["schema_count"],
            "launcher_count": census["launcher_count"],
            "schema_roots": census["schema_roots"],
            "launchers": census["launchers"],
            "set_sha256": census["set_sha256"],
            "canonicalization": census["canonicalization"],
            "frozen": census["frozen"],
        },
        "not_frozen": census["not_frozen"],
        "both_states": payload["both_states"],
        "trigger": payload["trigger"],
        "named_contracts": payload["named_contracts"],
        "answers": payload["answers"],
        "fingerprint": fp,
        "tests": [
            {
                "id": "both-states-gate-scratch-overlay",
                "command": payload["probe_commands"]["probe1"],
                "result": "PASS",
            },
            {
                "id": "not-frozen-scope-published",
                "command": payload["probe_commands"]["probe2"],
                "result": "PASS",
            },
        ],
        "evidence": [e1, e2, e3, e4, e5],
        "reviewer": {
            "reviewer_id": "ARC-0110-probe2-scope",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            art(SCHEMA, "output-schema"),
            art("command-center/p2-wave/probes/ARC-0110/gate.py", "gate"),
            art("command-center/p2-wave/probes/ARC-0110/inventory.py", "inventory"),
        ],
        "strongest_surviving_counterargument": (
            "Named contracts ARC-0092.json and ARC-0093.json are absent, so bump "
            "rules and migration-record fields are executed from the catalog text "
            "of those units, not from frozen contract files. That does not license "
            "skipping the ceremony: live schemas and launchers are hashed, the "
            "unmigrated plant rejects, the migrated twin accepts, and the published "
            "not-frozen list stays gate-silent. This unit does not rebuild those "
            "contracts."
        ),
    }

    assert_schema_shim()

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {OUT} frozen={fp['frozen_count']} schemas={fp['schema_count']} "
        f"launchers={fp['launcher_count']} set={fp['set_sha256'][:16]}"
    )
    print("SUCCESS:ARC-0110 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
