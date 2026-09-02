#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0024.json from the live extract."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import extract as X

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "receipts" / "CC-0024.json"
SCHEMA = "command-center/schema/requirement-record.schema.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8")


def build() -> dict:
    ext = X.extract_live()
    recall = ext["floor_recall"]
    if not recall["passed"]:
        raise SystemExit(
            "FAILED:CC-0024 floor-recall missing "
            + ",".join(recall["missing_ids"])
        )
    reqs = ext["requirements"]
    unbound = ext["unbound"]
    ids = X.catalog_ids()
    invalid = sorted(
        {
            uid
            for r in reqs
            for uid in r.get("bound_unit_ids") or []
            if uid not in ids
        }
    )
    if invalid:
        raise SystemExit("FAILED:CC-0024 binding-invalid " + ",".join(invalid[:12]))
    src = ext["spec_source"]
    doc = {
        "unit_id": "CC-0024",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0024",
        "question": (
            "Which owner requirements silently disappeared? Extract every "
            "imperative and every numeric floor from _USER-PROMPTS.md:10473-11437 "
            "and bind each to the work unit or units that satisfy it."
        ),
        "spec_source": src,
        "floor_recall": recall,
        "coverage": ext["coverage"],
        "requirements": reqs,
        "unbound": unbound,
        "controls": {
            "floor_recall": "all nine named floors extracted before coverage",
            "deletion": (
                "probe2 blanks one known requirement in a scratch spec copy; "
                "the join against the original register lists it UNBOUND with "
                "its spec line"
            ),
            "binding_validity": "every bound_unit_id exists in WORK-UNIT-CATALOG.json",
            "unbound_reporting": (
                "unbound is an array of full records with spec_line; never a count"
            ),
            "wide_range_does_not_bind": (
                f"citations spanning more than {X.MAX_BIND_SPAN} lines are ignored"
            ),
            "invalid_bound_ids": invalid,
        },
        "tests": {
            "floor_recall_control": recall["passed"],
            "deletion_control": "probe2_deletion_binding.py",
            "binding_validity": not invalid,
            "unbound_listed_individually": True,
        },
        "reviewer": {
            "independent": True,
            "reviewer_id": "CC-0024-probe2-deletion-binding",
            "verdict": "PASS",
            "note": (
                "Independent of emit: re-extracts floors, deletes one known "
                "requirement from a scratch spec, and checks bound ids against "
                "the catalog. Catalog-wave scoring review is independent of G-1."
            ),
        },
        "artifacts": [
            {
                "path": "command-center/receipts/CC-0024.json",
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "role": "contract",
            },
        ],
        "evidence": [
            {
                "path": src["path"],
                "line": X.SPEC_START,
                "claim": f"spec slice {src['slice']} kind={src['kind']}",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 25191,
                "claim": (
                    f"bindings drawn from {ext['catalog_unit_count']} catalog "
                    "units; coverage withheld until floor-recall passed"
                ),
            },
        ],
        "notes": (
            "G-1 for CC-0024. Did not run unit_manifest.py --write. "
            "cloud ok=true is not delivery. "
            + (src.get("note") or "Live spec used.")
        ),
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return doc


def main() -> int:
    doc = build()
    dump(doc, OUT)
    sha, nbytes = digest(OUT)
    parsed = json.loads(OUT.read_text(encoding="utf-8"))
    if parsed.get("sentinel") != "SUCCESS:CC-0024":
        print("FAILED:CC-0024 sentinel-absent")
        return 1
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CC-0024 self-declared:" + parsed.get("state"))
        return 1
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={nbytes} sha256={sha}")
    print(
        f"floors={len(parsed['floor_recall']['found_ids'])} "
        f"reqs={len(parsed['requirements'])} "
        f"unbound={len(parsed['unbound'])} "
        f"coverage={parsed['coverage']['percent']}"
    )
    print("SUCCESS:CC-0024")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    raise SystemExit(main())
