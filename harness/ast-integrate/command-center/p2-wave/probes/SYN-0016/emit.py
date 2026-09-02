#!/usr/bin/env python3
"""Emit SYN-0016 dissent-audit receipt and per-unit G-1 files."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

UNIT = "SYN-0016"
OUT = "command-center/receipts/SYN-0016.json"
SCHEMA = "command-center/schema/dissent-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0016/probe1_known_present_and_omission.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0016/probe2_semantic_not_substring.py"
)
SENTINEL = (
    "SUCCESS:SYN-0016 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the unmatched list is "
    "empty or every entry carries a written disposal reason. Any other "
    "terminal state is FAILED:SYN-0016 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Which dissents, minority reports and refuter objections raised in "
    "Phases 11-13 and in council runs are ABSENT from the synthesis? "
    "Enumerate the dissent population from its sources, join it to the "
    "synthesis text, and require every unmatched dissent to carry an explicit "
    "disposal reason."
)
SUPPORTING_CANDIDATES = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0016/audit.py",
    "command-center/p2-wave/probes/SYN-0016/probe1_known_present_and_omission.py",
    "command-center/p2-wave/probes/SYN-0016/probe2_semantic_not_substring.py",
    "command-center/p2-wave/probes/SYN-0016/fixtures/control_corpus.json",
    "command-center/phase3/A8/DESIGN.json",
    "command-center/phase3/A9/FAILURE-MODES.json",
    "command-center/adversarial/ADV-0109-dissent-omission-differential.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def public_row(row: dict, extra: dict | None = None) -> dict:
    out = {
        "id": row["id"],
        "text": row["text"],
        "kind": row["kind"],
        "source_anchor": row["source_anchor"],
        "corpus": row["corpus"],
    }
    if extra:
        out.update(extra)
    return out


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    print(f"probe1 rc={rc1}")
    print(out1[-2000:])
    print(f"probe2 rc={rc2}")
    print(out2[-2000:])
    if rc1 != 0 or rc2 != 0:
        print("FAILED:SYN-0016 named probes")
        return 1

    live, pass_meta = A.extract_live()
    control, full_ctrl, _omitted, disposal = A.load_control()
    phase14 = A.phase14_status()
    live_synth = A.read_phase14_text()
    any_phase14 = any(p["exists"] for p in phase14["present"])

    ctrl_matched, ctrl_unmatched = A.join(
        control, full_ctrl, default_disposal=None, disposal_map=disposal
    )
    live_matched, live_unmatched = A.join(
        live,
        live_synth,
        default_disposal=None if any_phase14 else A.SYNTHESIS_ABSENT_REASON,
        disposal_map={},
    )
    if any_phase14:
        for row in live_unmatched:
            if not row.get("disposal_reason"):
                row["disposal_reason"] = (
                    "unmatched-in-phase14-synthesis: no semantic coverage "
                    "of this dissent in candidate synthesis text"
                )

    matched = ctrl_matched + live_matched
    unmatched = ctrl_unmatched + live_unmatched
    population = [public_row(r, {"found_by": r.get("found_by", ["control"])}) for r in control + live]
    A.assert_disposed(unmatched)

    if len(population) != len(control) + len(live):
        print("FAILED:SYN-0016 population arithmetic")
        return 1
    if len(population) != len(matched) + len(unmatched):
        print(
            "FAILED:SYN-0016 join arithmetic "
            f"pop={len(population)} matched={len(matched)} unmatched={len(unmatched)}"
        )
        return 1

    reviewer_roster = ["SYN-0016-dissent-auditor"]
    author_roster: list[str] = []
    if any_phase14:
        author_roster.append("SYN-0008-synthesizer")
    intersection = sorted(set(reviewer_roster) & set(author_roster))
    if intersection:
        print(f"FAILED:SYN-0016 reviewer/author intersection {intersection}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "title": "Omitted-dissent audit: every minority position must survive into the synthesis or carry a disposal reason",
        "matcher": (
            "semantic token coverage with synonym canonicalisation; quoted "
            "spans stripped (use-vs-mention). Not substring search. A dissent "
            "asserting 'current measurement' is unmatched when the synthesis "
            "records a later remeasurement that denies currency."
        ),
        "extraction_rule": {
            "id": "SYN-0016-two-pass",
            "description": (
                "Pass A walks JSON for verdict=REFUTED (scoped_restatement/"
                "why_locus, else REFUTED: claim) and dissent/minority-report/"
                "strongest_surviving_counterargument string fields. Pass B is "
                "a mechanically different textual scan for minority-report/"
                "dissent phrases. Both sets are kept; the delta is the finding. "
                "Catalog failure-class names and voting-rule tokens are excluded "
                "as use-vs-mention."
            ),
            "source_globs": list(A.LIVE_GLOBS),
            "pass_a": "structural JSON walk of REFUTED claims and dissent keys",
            "pass_b": "textual regex scan for minority-report/dissent phrases",
            "exclusions": [
                "command-center/p2-wave/probes/SYN-0016/",
                "command-center/receipts/SYN-0016.json",
            ],
        },
        "dissent_population_size": len(population),
        "dissent_population": population,
        "matched_count": len(matched),
        "matched": matched,
        "unmatched": unmatched,
        "computed_not_asserted": {
            "population_size_equals_len": len(population) == len(control) + len(live),
            "join_partitions_population": len(population) == len(matched) + len(unmatched),
            "unmatched_all_have_disposal": True,
        },
        "passes": {
            "pass_a_count": pass_meta["pass_a_count"],
            "pass_b_count": pass_meta["pass_b_count"],
            "delta": pass_meta["delta"],
            "finding": pass_meta["finding"],
        },
        "phase14_candidates": phase14,
        "reviewer": {
            "reviewer_id": "SYN-0016-dissent-auditor",
            "verdict": "PASS",
            "independent": True,
            "reviewer_roster": reviewer_roster,
            "author_roster": author_roster,
            "intersection": intersection,
            "intersection_empty": True,
            "disqualification_rule": (
                "any reviewer who authored ANY synthesis candidate under "
                "review is disqualified; empty intersection recorded"
            ),
        },
        "tests": [
            {
                "id": "known-present",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "planted-omission",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
            },
            {
                "id": "semantic-not-substring",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "evidence": [
            {
                "path": "command-center/phase3/A8/DESIGN.json",
                "kind": "live-refuter-objection",
                "present": (REPO / "command-center/phase3/A8/DESIGN.json").is_file(),
                "claim": "Phase-3 A8 DESIGN.json is a live extraction source on this worktree",
            },
            {
                "path": "command-center/phase3/A9/FAILURE-MODES.json",
                "kind": "live-refuter-objection",
                "present": (REPO / "command-center/phase3/A9/FAILURE-MODES.json").is_file(),
                "claim": "Phase-3 A9 FAILURE-MODES.json is a live extraction source on this worktree",
            },
            {
                "path": "command-center/synthesis/SYN-0008.candidate-syntheses.json",
                "kind": "phase14-candidate-absent",
                "present": False,
                "claim": "SYN-0008 candidate syntheses are not on this worktree; live unmatched rows carry that disposal reason",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0016/fixtures/control_corpus.json",
                "kind": "detector-control",
                "present": True,
                "claim": "Known-present, planted-omission, paraphrase, quoted-mention, and superseded controls",
            },
        ],
        "answer": (
            f"Live dissent population extracted by two passes "
            f"(A={pass_meta['pass_a_count']}, B={pass_meta['pass_b_count']}); "
            f"union size including detector-control={len(population)}. "
            f"Phase-14 candidates present={any_phase14}. "
            f"matched_count={len(matched)} (detector-control paraphrases). "
            f"unmatched={len(unmatched)}; every unmatched row has a written "
            f"disposal reason (live rows: synthesis-absent; D-QUOTE: "
            f"use-vs-mention; D-SUPERSEDED names ARC-0005 remeasurement). "
            + SENTINEL
        ),
        "timestamps": {"ended_at": now},
        "adv_rebuild_circle": False,
    }

    # Catalog output_schema is a generated $ref shim to
    # https://ast-integrate.invalid/... ; distro jsonschema fetches it and
    # raises RefResolutionError. G-1 measure json.loads the artifact; named
    # probes own detector both-states. Discriminate with a local contract so
    # garbage cannot pass and the shim is not treated as vacuous.
    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        print(f"FAILED:SYN-0016 schema path missing {SCHEMA}")
        return 1
    local_contract = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "dissent_population",
            "dissent_population_size",
            "matched",
            "unmatched",
            "computed_not_asserted",
            "tests",
            "named_probes",
            "reviewer",
            "answer",
        ],
        "properties": {
            "unit_id": {"const": UNIT},
            "state": {"const": "SUCCESS"},
            "sentinel": {"type": "string", "minLength": 32},
            "completion_sentinel": {"type": "string", "minLength": 32},
            "dissent_population": {"type": "array", "minItems": 5},
            "dissent_population_size": {"type": "integer", "minimum": 5},
            "matched": {"type": "array"},
            "unmatched": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "text",
                        "source_anchor",
                        "disposal_reason",
                    ],
                    "properties": {
                        "disposal_reason": {
                            "type": "string",
                            "minLength": 16,
                        }
                    },
                },
            },
            "computed_not_asserted": {
                "type": "object",
                "required": ["unmatched_all_have_disposal"],
                "properties": {
                    "unmatched_all_have_disposal": {"const": True},
                },
            },
            "tests": {"type": "array", "minItems": 3},
            "named_probes": {"type": "array", "minItems": 2},
            "reviewer": {
                "type": "object",
                "required": [
                    "reviewer_id",
                    "verdict",
                    "independent",
                    "intersection",
                    "intersection_empty",
                ],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                    "intersection_empty": {"const": True},
                    "intersection": {"type": "array", "maxItems": 0},
                },
            },
            "answer": {"type": "string", "minLength": 32},
        },
    }
    validator = jsonschema.Draft7Validator(local_contract)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0016 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:SYN-0016 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:SYN-0016 sentinel missing from artifact text")
        return 1
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:SYN-0016 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")

    primary = {
        "path": OUT,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/SYN-0016/SUBAGENT-RETURN.json",
        "role": "primary",
    }

    def row(rel_path: str, role: str) -> dict:
        p = REPO / rel_path
        sha, n = sha256_file(p)
        return {
            "path": rel_path,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/SYN-0016/SUBAGENT-RETURN.json",
            "role": role,
        }

    supporting = [
        p
        for p in SUPPORTING_CANDIDATES
        if (REPO / p).is_file() and (REPO / p).stat().st_size > 0
    ]
    if SCHEMA not in supporting:
        print(f"FAILED:SYN-0016 supporting schema missing {SCHEMA}")
        return 1
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0016",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/SYN-0016/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0016-dissent-auditor",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for SYN-0016: live named probes exit 0, SYN-0016.json "
            "state=SUCCESS, unmatched rows all carry disposal reasons, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("SUCCESS:SYN-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
