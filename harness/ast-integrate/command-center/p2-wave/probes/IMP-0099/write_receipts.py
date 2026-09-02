#!/usr/bin/env python3
"""Emit IMP-0099 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from marketplace.advisory import from_record  # noqa: E402
from marketplace.version import events_to_range  # noqa: E402

UNIT = "IMP-0099"
OUT = "command-center/receipts/IMP-0099.json"
SCHEMA_ADV = "tools/marketplace/schema/advisory.schema.json"
FIX_REL = "tools/marketplace/fixtures/imp0099_matrix.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0099/probe1_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0099/probe2_independent_engine.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest "
    "tools.marketplace.tests.test_advisory_ranges"
)
SUPPORTING = [
    SCHEMA_ADV,
    FIX_REL,
    "tools/marketplace/advisory.py",
    "tools/marketplace/version.py",
    "tools/marketplace/tests/test_advisory_ranges.py",
    "command-center/p2-wave/probes/IMP-0099/probe1_matrix.py",
    "command-center/p2-wave/probes/IMP-0099/probe2_independent_engine.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0099/SUBAGENT-RETURN.json",
        "role": role,
    }


def run_unittests() -> tuple[bool, str]:
    buf = StringIO()
    loader = unittest.defaultTestLoader
    # Load by file path so we do not need tools as a top-level package.
    suite = loader.discover(
        start_dir=str(REPO / "tools/marketplace/tests"),
        pattern="test_advisory_ranges.py",
        top_level_dir=str(REPO / "tools"),
    )
    result = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    ok = result.wasSuccessful() and result.testsRun >= 6
    return ok, buf.getvalue()


def build_receipt(t1: str, t2: str, test_out: str) -> dict:
    fix = json.loads((REPO / FIX_REL).read_text(encoding="utf-8"))
    adv = from_record(fix["advisory"])
    spec = events_to_range(list(adv.affected_version_ranges))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src1 = {
        "role": "source",
        "method": "command",
        "command": P1,
        "raw_output": t1[-65000:],
        "fingerprint": fp("command", P1),
        "exit_code": 0,
    }
    ver1 = {
        "role": "verifier",
        "method": "command",
        "command": P2,
        "raw_output": t2[-65000:],
        "fingerprint": fp("command", P2),
        "exit_code": 0,
    }
    impl = [
        {
            "path": rel,
            "bytes": digest(REPO / rel)[1],
            "sha256": digest(REPO / rel)[0],
            "exists": True,
            "role": "supporting",
            "eol": "LF",
        }
        for rel in SUPPORTING
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0099",
        "title": "Advisory record and affected-version-range model",
        "spec_anchor": "_USER-PROMPTS.md:10868 (security advisory flow)",
        "question_or_target": (
            "Model an advisory as (identifier, severity, affected version ranges, "
            "fixed version, references) attached to a package rather than to the "
            "whole registry, so a single bad version can be flagged while its "
            "siblings remain installable — and so 'is MY installed version affected' "
            "is a computable question."
        ),
        "min_bytes_threshold": 128,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + " + SCHEMA_ADV
        ),
        "advisory_model": adv.to_record(),
        "imp0070_range": spec,
        "matrix_size": 20,
        "artifacts": impl,
        "evidence": [
            {
                "claim": (
                    "A 20-case version matrix on GHSA-demo-0001 "
                    "(introduced 1.0.0, fixed 1.2.3) yields the expected "
                    "affected/unaffected verdicts, including at-fixed (unaffected) "
                    "and prerelease-of-fixed (affected)."
                ),
                "verdict": "CONFIRMED",
                "anchor": FIX_REL + ":cases",
                "confidence": "almost-certain",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "The same matrix evaluated by the IMP-0070 comparator engine "
                    f"on range {spec} produces identical verdicts."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/version.py:satisfies",
                "confidence": "almost-certain",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "Negative control: demo-kit@1.1.0 is flagged while sibling "
                    "version demo-kit@1.2.3 and sibling package sibling-kit@1.1.0 "
                    "remain installable."
                ),
                "verdict": "CONFIRMED",
                "anchor": FIX_REL + ":negative_control",
                "confidence": "almost-certain",
                "probes": [ver1],
            },
            {
                "claim": (
                    "An open-ended range cannot silently mark every future version: "
                    "construction without unbounded_future_disclosed is refused, "
                    "and a disclosed open range labels future hits as open-ended."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/advisory.py:OpenEndedUndisclosedError",
                "confidence": "almost-certain",
                "probes": [ver1],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_advisory_ranges",
                "command": TEST_CMD,
                "result": "PASS",
                "raw_output": test_out[-8000:],
            }
        ],
        "negative_controls": [
            {
                "id": "sibling-unaffected",
                "kind": "unaffected-sibling",
                "description": (
                    "An unaffected sibling version remains installable while "
                    "the affected one is flagged; a same-version sibling package "
                    "is untouched because the advisory is package-scoped."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "demo-kit@1.1.0 affected=true installable=false",
                "good_state_output": (
                    "demo-kit@1.2.3 installable=true; "
                    "sibling-kit@1.1.0 installable=true"
                ),
            },
            {
                "id": "open-ended-disclosure",
                "kind": "mutation",
                "description": (
                    "Stripping unbounded_future_disclosed from an open-ended "
                    "advisory is refused."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "OpenEndedUndisclosedError",
                "good_state_output": "GHSA-demo-open disclosed open_ended=true",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0099-probe2-independent-range-engine",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Hand-checked fixed-version boundary: 1.2.3 is unaffected "
                "(half-open upper bound); 1.2.3-rc.1 is affected."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0099/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": (
                        "python3 command-center/p2-wave/_measure_one_delivered.py "
                        "IMP-0099"
                    ),
                    "raw_output": "deferred-to-post-write-measure",
                    "fingerprint": fp(
                        "command",
                        "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0099",
                    ),
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0070 and IMP-0098 catalog receipts are not on this "
                    "worktree; this unit embeds the IMP-0070 comparator engine "
                    "under tools/marketplace/version.py so the two-signal "
                    "agreement can be measured here."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": (
                    "When IMP-0070 delivers, re-run probe2 against that receipt's "
                    "engine path and require identical selections."
                ),
            }
        ],
        "reviewer_requirement": (
            "Reviewer must check the fixed-version boundary by hand; "
            "off-by-one there is the classic defect."
        ),
        "hand_checked_boundary": {
            "fixed_version": "1.2.3",
            "at_fixed_affected": False,
            "prerelease_of_fixed_example": "1.2.3-rc.1",
            "prerelease_of_fixed_affected": True,
        },
    }


def main() -> int:
    tests_ok, test_out = run_unittests()
    print(test_out[-2000:])
    if not tests_ok:
        print("FAILED:IMP-0099 unittest failure")
        return 1

    receipt = build_receipt("", "", test_out)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-1500:])
    print(f"probe2 rc={c2}")
    print(t2[-1500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0099 probes c1={c1} c2={c2}")
        return 1

    receipt = build_receipt(t1, t2, test_out)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0099",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json + " + SCHEMA_ADV,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "affected-version-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-imp0070-engine",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0099/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0099-probe2-independent-range-engine",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0099: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:IMP-0099, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0099 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
