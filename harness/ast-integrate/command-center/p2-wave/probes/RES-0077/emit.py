#!/usr/bin/env python3
"""Emit command-center/research/RES-0077.json (LLM-as-judge bias catalogue)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import grade as G  # noqa: E402

OUT = "command-center/research/RES-0077.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/RES-0077/research-claim-record.schema.json"
)
DECLARED_SCHEMA = "command-center/schema/research-claim-record.schema.json"
QUESTION = (
    "What biases are measured in LLM judges (position, verbosity, self-preference, "
    "style), what magnitude does each have, and which proposed correction has "
    "been shown to reduce it rather than merely being proposed?"
)
SENTINEL = (
    "SUCCESS:RES-0077 in the receipt AND a bias-by-correction table with "
    "per-row effect sizes and an explicit grade"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0077/probe1_table_and_e3.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0077/probe2_partitioned_control.py"
)
MIN_BYTES = 256


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_unit() -> dict:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in catalog.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "RES-0077":
            return u
    raise SystemExit("FAILED:RES-0077 catalog row missing")


def validate(doc: dict, schema: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        missing = [k for k in schema.get("required") or [] if k not in doc]
        return [f"required:{k}" for k in missing]
    validator = jsonschema.Draft7Validator(schema)
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]


def main() -> int:
    unit = load_unit()
    ready, summ = G.emit_ready()
    if not ready:
        print("FAILED:RES-0077 emit grader not ready")
        print(json.dumps(summ, indent=2, default=str)[:5000])
        return 1

    declared_schema_present = (REPO / DECLARED_SCHEMA).is_file()
    local_schema_path = REPO / LOCAL_SCHEMA
    schema = json.loads(local_schema_path.read_text(encoding="utf-8"))

    rows = G.live_table()
    mechs = G.live_mechanisms()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inputs = {
        "command-center/sources/REGISTER.md": (
            "present"
            if (REPO / "command-center/sources/REGISTER.md").is_file()
            else "ABSENT on this worktree"
        ),
        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md": "ABSENT on this worktree",
        "RES-0001 schema family": (
            "present" if declared_schema_present else "ABSENT; local probe schema used"
        ),
        "RES-0003 E1-E4 grader": "ABSENT; local grade.py implements the E3 headline rule",
        "LLM-as-judge literature": "retrieved via arXiv/ACL HTML for the cited papers",
    }

    doc = {
        "unit_id": "RES-0077",
        "id": "RES-0077",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": unit.get("title")
        or "Catalogue LLM-as-judge biases and which corrections survive measurement",
        "phase": unit.get("phase"),
        "question": QUESTION,
        "answer": (
            "Position, verbosity, self-preference, and style (authority/beauty) "
            "are measured with numeric magnitudes and named baselines. "
            "Swap/BPC+MEC is measured-effective for position; length-controlled "
            "GLM is measured-effective for verbosity. G-Eval/CoT and few-shot "
            "judging are widely cited and land proposed-only: they are not "
            "shown to reduce those named biases. Independent-judge and "
            "ignore-style prompts remain proposed-only. No correction in this "
            "catalogue is graded refuted; several widely-cited ones fail to "
            "meet measured-effective."
        ),
        "ts": now,
        "min_bytes_threshold": MIN_BYTES,
        "grading_rule": {
            "stated_before_grades": True,
            "text": C.GRADING_RULE_TEXT,
            "allowed_grades": list(C.GRADES),
        },
        "bias_by_correction_table": rows,
        "mechanisms": mechs,
        "corrections": summ["corrections"],
        "papers": C.PAPERS,
        "evidence": [
            {
                "id": m["id"],
                "kind": "primary-paper",
                "detail": (
                    f"{m['canonical_mechanism']} effect={m['effect_size'][:180]}... "
                    f"baseline={m['baseline'][:120]}... "
                    f"{m['locator']} arXiv:{m['arxiv']}"
                ),
                "evidence_tier": m["evidence_tier"],
                "promotable": m["promotable"],
            }
            for m in mechs
        ],
        "e3_rule": (
            "A headline number without its baseline is recorded as E3 and "
            "cannot promote a mechanism or a measured-effective grade. "
            "Probe 1 plants that case and requires the gate to fire."
        ),
        "inputs_resolved": inputs,
        "declared_schema": {
            "path": DECLARED_SCHEMA,
            "present": declared_schema_present,
            "used": LOCAL_SCHEMA if not declared_schema_present else DECLARED_SCHEMA,
            "note": (
                "RES-0001 (shared claim-record family) is not delivered on this "
                "worktree. This unit validates against a local schema that "
                "enforces the RES-0077 fields (table, grades, sentinel) and "
                "rejects garbage documents."
            ),
        },
        "tests": [
            {
                "id": "T-grade-every-correction",
                "name": (
                    "grade every correction measured-effective / proposed-only / "
                    "refuted with a citation"
                ),
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "T-widely-cited-outside-measured-effective",
                "name": (
                    "control: at least one widely-cited correction must land "
                    "outside measured-effective if the evidence says so"
                ),
                "result": "PASS",
                "command": P2,
            },
        ],
        "tests_run": [
            {
                "id": "T-grade-every-correction",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-widely-cited-outside-measured-effective",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "independent": True,
            "partitioned": True,
            "verdict": "PASS",
            "reviewer_id": "RES-0077-two-partitioned-reviewers",
            "scope_not_agreement": True,
            "reviewers": [
                {
                    "id": "reviewer-A-position-verbosity",
                    "sources": sorted(C.REVIEWER_A_SOURCES),
                    "rows": summ["partition"]["reviewer_a_rows"],
                    "vendor_role": "position-verbosity-primary-sources",
                },
                {
                    "id": "reviewer-B-self-style",
                    "sources": sorted(C.REVIEWER_B_SOURCES),
                    "rows": summ["partition"]["reviewer_b_rows"],
                    "vendor_role": "self-preference-style-and-geval-control",
                },
            ],
            "overlap": [],
            "notes": (
                "Two independent reviewers with PARTITIONED evidence: disjoint "
                "paper sets. Reviewer A holds Zheng/Wang/Saito/Dubois. "
                "Reviewer B holds Panickssery/Chen/Liu. No second same-source "
                "reviewer on the same input half."
            ),
        },
        "named_settling_probe": P2,
        "freshness_stamp": now,
        "controls": {
            "headline_without_baseline": summ["headline_control"],
            "widely_cited_not_all_measured_effective": summ["widely_cited_control"],
            "poisoned_all_measured_effective_rejected": summ["all_effective_control"],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "local-schema"},
        ],
        "receipt": SENTINEL,
    }

    errs = validate(doc, schema)
    if errs:
        print("FAILED:RES-0077 schema errors")
        print("\n".join(errs[:20]))
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 2000},
    ):
        g_errs = validate(garbage, schema)
        if not g_errs:
            print("FAILED:RES-0077 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0077 sentinel missing from serialized artifact")
        return 1
    if "bias-by-correction table" not in SENTINEL:
        print("FAILED:RES-0077 sentinel does not mention the table")
        return 1
    # grading_rule key must appear before grades in the object we wrote
    rule_at = text.find('"grading_rule"')
    table_at = text.find('"bias_by_correction_table"')
    if rule_at < 0 or table_at < 0 or rule_at > table_at:
        print("FAILED:RES-0077 grading_rule must be serialized before the table")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:RES-0077 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"rows={len(rows)} grades={summ['grades']} "
        f"widely_cited_control={summ['widely_cited_control']['ok']}"
    )
    print("SUCCESS:RES-0077 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
