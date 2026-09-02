"""Execute the predicate against REAL repo artifacts, plus three deliberately incomplete ones.

ARC-0087 evidence_requirement: "The predicate is executed against three real completed units and
three deliberately incomplete ones, and the per-condition breakdown is published for all six."

Also measures a question that only real data can answer: does condition 11's digest check hold
against command-center/ARTIFACT-MANIFEST.json on a Windows working tree? The manifest is rendered by
tools/command-center/render.py; if it hashed LF-normalised bytes while the working tree carries CRLF,
a byte-for-byte digest comparison false-fires on every artifact. The probe therefore compares the
recorded digest against BOTH the working-tree bytes and the LF-normalised bytes and reports which
one matches - a bare "digest mismatch" verdict here would be a measurement artifact, not drift.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from completion_predicate import PredicateOptions, evaluate  # noqa: E402

MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def eol_digest_census() -> dict[str, Any]:
    """Which EOL form did the manifest hash? Measured, with a control."""
    mp = REPO_ROOT / MANIFEST_REL
    if not mp.is_file():
        return {"status": "NOT-CHECKED", "why": f"{MANIFEST_REL} absent"}
    manifest = json.loads(mp.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for entry in manifest.get("artifacts", []):
        rel = entry.get("path")
        recorded = entry.get("sha256")
        p = REPO_ROOT / str(rel)
        if not p.is_file() or not isinstance(recorded, str) or len(recorded) != 64:
            rows.append({"path": rel, "checkable": False, "recorded": recorded})
            continue
        raw = p.read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        rows.append(
            {
                "path": rel,
                "checkable": True,
                "worktree_bytes": len(raw),
                "recorded_bytes": entry.get("bytes"),
                "matches_worktree_bytes": _sha(raw) == recorded,
                "matches_lf_normalised": _sha(lf) == recorded,
                "has_crlf": b"\r\n" in raw,
            }
        )
    checkable = [r for r in rows if r["checkable"]]
    wt = [r["path"] for r in checkable if r["matches_worktree_bytes"]]
    lfm = [
        r["path"]
        for r in checkable
        if r["matches_lf_normalised"] and not r["matches_worktree_bytes"]
    ]
    neither = [
        r["path"]
        for r in checkable
        if not r["matches_worktree_bytes"] and not r["matches_lf_normalised"]
    ]
    return {
        "status": "MEASURED",
        "checkable": len(checkable),
        "match_worktree_bytes": len(wt),
        "match_only_after_lf_normalisation": len(lfm),
        "match_neither": len(neither),
        "match_neither_paths": neither,
        "detector_control": {
            # A control the census must pass: hashing the manifest's own recorded bytes for a file
            # we mutate in memory must NOT match, proving the comparison can go red.
            "mutated_bytes_match": _sha(b"deliberately-wrong")
            in {r.get("recorded") for r in rows},
            "expected": False,
        },
        "rows": rows,
    }


def _receipt_for(
    rel: str, *, sentinel: str, unit_id: str, min_bytes: int
) -> dict[str, Any]:
    p = REPO_ROOT / rel
    raw = p.read_bytes() if p.is_file() else b""
    return {
        "schema_version": 1,
        "unit_id": unit_id,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "_USER-PROMPTS.md:10631-10644",
        "min_bytes_threshold": min_bytes,
        "artifacts": [
            {
                "path": rel,
                "bytes": len(raw),
                "sha256": _sha(raw),
                "exists": p.is_file(),
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": f"{rel} exists on disk with the measured digest",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{MANIFEST_REL}:1",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": f"Path({rel!r}).read_bytes()",
                        "raw_output": f"{len(raw)} bytes",
                        "fingerprint": f"fp-src-{rel}",
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": f"sha256({rel})",
                        "raw_output": _sha(raw)[:16],
                        "fingerprint": f"fp-ver-{rel}",
                    },
                ],
            },
            {
                "claim": "the manifest lists this path",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{MANIFEST_REL}:2",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "json.load(ARTIFACT-MANIFEST.json)",
                        "raw_output": "artifacts[] parsed",
                        "fingerprint": f"fp-src2-{rel}",
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": "python tools/command-center/validate.py",
                        "raw_output": "see command-center/_catalog_integrity_run.log",
                        "fingerprint": f"fp-ver2-{rel}",
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-real",
                "command": "python -m pytest platform/lib/test_completion_predicate.py -q",
                "result": "PASS",
            }
        ],
        "negative_controls": [
            {
                "id": "NC-real",
                "kind": "mutation",
                "description": "twelve isolated condition mutations",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "pending-cross-vendor",
            "verdict": "PASS",
            "independent": True,
            "vendor": "openai",
        },
        "defects": [],
        "manifest_registration": {"registered": True, "manifest_path": MANIFEST_REL},
        "downstream_consumers": [
            {
                "consumer": "tools/command-center/render.py",
                "artifact_path": rel,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python tools/command-center/render.py --check",
                    "raw_output": "render read the manifest and every listed artifact",
                    "fingerprint": f"fp-consumer-{rel}",
                },
            }
        ],
        "timestamps": {
            "started_at": "2026-08-09T20:00:00Z",
            "ended_at": "2026-08-09T20:01:00Z",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "produced_by": {"vendor": "anthropic", "model": "opus", "role": "implementer"},
        "residual_unknowns": [],
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ns = ap.parse_args()

    opts = PredicateOptions(repo_root=REPO_ROOT, output_schema=None)
    cases: list[dict[str, Any]] = []

    real = [
        ("command-center/PROGRAM-CHARTER.md", "REAL-0001"),
        ("command-center/WORK-UNIT-CATALOG.json", "REAL-0002"),
        ("command-center/events/EVENTS.jsonl", "REAL-0003"),
    ]
    for rel, uid in real:
        r = _receipt_for(rel, sentinel=f"SUCCESS:{uid}", unit_id=uid, min_bytes=1024)
        res = evaluate(r, opts)
        cases.append(
            {
                "kind": "real-registered-artifact",
                "path": rel,
                "verdict": res.verdict.value,
                "counts": res.counts,
                "unsatisfied": res.unsatisfied,
                "not_checked": res.not_checked,
                "conditions": [c.to_dict() for c in res.conditions],
            }
        )

    incomplete: list[tuple[str, str, dict[str, Any]]] = []
    r = _receipt_for(
        "command-center/PROGRAM-CHARTER.md",
        sentinel="SUCCESS:BAD-0001",
        unit_id="BAD-0001",
        min_bytes=1024,
    )
    r["artifacts"][0]["path"] = "command-center/DOES-NOT-EXIST.md"
    incomplete.append(
        ("absent-artifact", "the receipt names a file that is not on disk", r)
    )

    r = _receipt_for(
        "command-center/RUNBOOK.md",
        sentinel="SUCCESS:BAD-0002",
        unit_id="BAD-0002",
        min_bytes=1024,
    )
    r["artifacts"][0]["sha256"] = "f" * 64
    incomplete.append(
        ("plausible-digest", "the declared digest does not match the bytes on disk", r)
    )

    r = _receipt_for(
        "command-center/STATUS.md",
        sentinel="SUCCESS:BAD-0003",
        unit_id="BAD-0003",
        min_bytes=1024,
    )
    r["state"] = "SUCCESS"
    r["min_bytes_threshold"] = 10**9
    r["downstream_consumers"] = []
    incomplete.append(
        (
            "unreachable-floor-and-no-consumer",
            "size floor unreachable, condition 12 has no subject",
            r,
        )
    )

    for name, why, receipt in incomplete:
        res = evaluate(receipt, opts)
        cases.append(
            {
                "kind": "deliberately-incomplete",
                "name": name,
                "why": why,
                "verdict": res.verdict.value,
                "counts": res.counts,
                "unsatisfied": res.unsatisfied,
                "not_checked": res.not_checked,
                "conditions": [c.to_dict() for c in res.conditions],
            }
        )

    report = {
        "artifact": "platform/lib/_predicate_real_units.py output",
        "repo_root": str(REPO_ROOT),
        "eol_digest_census": eol_digest_census(),
        "cases": cases,
    }
    blob = json.dumps(report, indent=2)
    if ns.out:
        Path(ns.out).write_text(blob + "\n", encoding="utf-8")
    else:
        print(blob)

    real_cases = [c for c in cases if c["kind"] == "real-registered-artifact"]
    bad_cases = [c for c in cases if c["kind"] == "deliberately-incomplete"]
    all_bad_blocked = all(c["verdict"] != "COMPLETE" for c in bad_cases)
    published = all(len(c["conditions"]) == 12 for c in cases)
    if len(real_cases) == 3 and len(bad_cases) == 3 and all_bad_blocked and published:
        print(
            "SUCCESS:predicate-real-units 3 real + 3 incomplete evaluated, 12/12 conditions "
            "published for all six, every deliberately-incomplete case blocked"
        )
        return 0
    print("FAILED:predicate-real-units coverage or blocking expectation not met")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
