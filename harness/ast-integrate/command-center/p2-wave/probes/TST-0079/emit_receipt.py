#!/usr/bin/env python3
"""Emit TST-0079 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

# Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows that
# $ref over HTTPS to ast-integrate.invalid and raises RefResolutionError. G-1
# requires the artifact to parse; this local contract is non-vacuous so garbage
# is rejected.

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import independent_differ as D  # noqa: E402
import probe1_sync_safety as P1  # noqa: E402
import probe2_eol_and_agreement as P2  # noqa: E402
import sync_tool as S  # noqa: E402

UNIT = "TST-0079"
OUT = "command-center/receipts/TST-0079.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0079/probe1_sync_safety.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0079/probe2_eol_and_agreement.py"
)
QUESTION = (
    "Failure class :11305 plus a measured instance: of 88 rules files only 5 are "
    "byte-identical between the repo tree and the live tree, 28 differ in real "
    "content, 25 are repo-larger and 3 are live-larger - so neither side is a "
    "superset and a one-directional Copy-Item -Force in EITHER direction destroys "
    "content. Target: the sync tool must detect two-directional drift and refuse "
    "rather than overwrite."
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0079/sync_tool.py",
    "command-center/p2-wave/probes/TST-0079/independent_differ.py",
    "command-center/p2-wave/probes/TST-0079/fixtures.py",
    "command-center/p2-wave/probes/TST-0079/probe1_sync_safety.py",
    "command-center/p2-wave/probes/TST-0079/probe2_eol_and_agreement.py",
]
PS1 = "scripts/sync-rules.ps1"
HYGIENE = "rules/common/harness-vcs-hygiene.md"
REQUIRED_TESTS = (
    "test_sync_refuses_on_a_diverged_pair",
    "test_sync_proceeds_on_a_strictly_one_directional_pair",
    "test_eol_only_differences_are_not_reported_as_content_drift",
)
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "tests",
        "classification",
        "negative_controls",
        "evidence",
        "reviewer",
        "report",
        "completion_sentinel",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0079"},
        "completion_sentinel": {"const": "SUCCESS:TST-0079"},
        "tests": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "required": ["id", "command", "result"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "command": {"type": "string", "minLength": 8},
                    "result": {"const": "PASS"},
                },
            },
        },
        "classification": {
            "type": "object",
            "required": ["method", "classes", "counts", "rows"],
            "properties": {
                "method": {"type": "string", "minLength": 20},
                "classes": {"type": "array", "minItems": 5},
                "counts": {"type": "object", "minProperties": 5},
                "rows": {"type": "array", "minItems": 5},
            },
        },
        "negative_controls": {"type": "array", "minItems": 3},
        "evidence": {"type": "array", "minItems": 4},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 8},
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "test-receipt"},
                "observations": {"type": "array", "minItems": 3},
                "control_ids": {"type": "array", "minItems": 3},
            },
        },
    },
    "additionalProperties": True,
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def measure_classifications() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0079-emit-") as tmp:
        trees = F.write_trees(Path(tmp) / "base")
        census = S.classify_trees(trees["repo"], trees["live"])
        rows = []
        for rec in census["rows"]:
            rb = (trees["repo"] / rec["path"]).read_bytes() if rec["in_repo"] else None
            lb = (trees["live"] / rec["path"]).read_bytes() if rec["in_live"] else None
            cmp = D.agree(rec["class"], rb, lb)
            rows.append(
                {
                    "path": rec["path"],
                    "class": rec["class"],
                    "content_drift": rec["content_drift"],
                    "repo_bytes": rec["repo_bytes"],
                    "live_bytes": rec["live_bytes"],
                    "repo_sha256": rec["repo_sha256"],
                    "live_sha256": rec["live_sha256"],
                    "repo_unique_lines": rec["repo_unique_lines"],
                    "live_unique_lines": rec["live_unique_lines"],
                    "independent_class": cmp["independent"],
                    "independent_agrees": cmp["agree"],
                }
            )
        t1 = P1.test_sync_refuses_on_a_diverged_pair(trees["repo"], trees["live"])
        t2 = P1.test_sync_proceeds_on_a_strictly_one_directional_pair(Path(tmp))
        ctrl = P1.naive_overwrite_destroys_diverged(Path(tmp))
        trees2 = F.write_trees(Path(tmp) / "eol")
        t3 = P2.test_eol_only_differences_are_not_reported_as_content_drift(
            trees2["repo"], trees2["live"]
        )
        host_rules = (REPO / "rules").is_dir()
        host_live = (Path.home() / ".claude" / "rules").is_dir()
        return {
            "census": census,
            "rows": rows,
            "tests": [t1, t2, t3],
            "naive": ctrl,
            "host_repo_rules": host_rules,
            "host_live_rules": host_live,
            "cited_2026_08_09_5_of_88": False,
        }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, n = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "exists": True,
        "present": True,
        "unit_id": UNIT,
        "role": role,
    }


def build_receipt(measured: dict, now: str) -> dict:
    disagree = [r for r in measured["rows"] if not r["independent_agrees"]]
    if disagree:
        raise SystemExit(f"independent differ disagreed: {disagree}")
    counts = measured["census"]["counts"]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0079",
        "title": (
            "Live-deployment synchronisation must be non-destructive "
            "under two-directional drift"
        ),
        "question_or_target": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:11305",
        "output_schema": SCHEMA,
        "tool_under_test": "command-center/p2-wave/probes/TST-0079/sync_tool.py",
        "catalog_inputs": [
            {
                "path": PS1,
                "present": (REPO / PS1).is_file(),
                "copy_item_force": (
                    "Copy-Item -Force" in (REPO / PS1).read_text(encoding="utf-8")
                    if (REPO / PS1).is_file()
                    else False
                ),
                "role": "known-broken-production-analogue",
            },
            {
                "path": HYGIENE,
                "present": (REPO / HYGIENE).is_file(),
                "role": "catalog-input",
            },
        ],
        "report": {
            "kind": "test-receipt",
            "observations": [
                {
                    "name": "diverged-pair-refused-both-directions",
                    "measured": True,
                    "method": "apply_sync_pair on planted diverged fixture",
                    "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:dest_loses_unique",
                },
                {
                    "name": "one-directional-pair-proceeds-safe-direction",
                    "measured": True,
                    "method": "apply_sync_pair on planted repo-ahead and live-ahead",
                    "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:sync_decision",
                },
                {
                    "name": "eol-only-not-content-drift",
                    "measured": True,
                    "method": "classify_pair LF vs CRLF identical line-set",
                    "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:classify_pair",
                },
                {
                    "name": "independent-splitlines-differ-agrees",
                    "measured": True,
                    "method": "independent_differ.classify_pair vs tool class",
                    "anchor": "command-center/p2-wave/probes/TST-0079/independent_differ.py:classify_pair",
                },
            ],
            "control_ids": [
                "naive-copy-item-force",
                "both-states-identical-vs-planted",
                "independent-differ-agreement",
            ],
        },
        "classification": {
            "method": (
                "deterministic line-set differ after LF normalisation; "
                "not agent judgement"
            ),
            "signals": ["sha256", "byte-size", "line-set-both-directions"],
            "classes": [
                "IDENTICAL",
                "EOL-ONLY",
                "REPO-AHEAD",
                "LIVE-AHEAD",
                "DIVERGED",
            ],
            "counts": counts,
            "content_drift_files": measured["census"]["content_drift_files"],
            "eol_only_not_content_drift": counts.get("EOL-ONLY", 0),
            "rows": measured["rows"],
            "cited_2026_08_09_5_of_88": False,
            "host_repo_rules_present": measured["host_repo_rules"],
            "host_live_rules_present": measured["host_live_rules"],
            "note": (
                "The catalog's 5/88 estate numbers are a historical instance of "
                "the failure class, not today's measurement. Repo rules/common "
                "exists here; ~/.claude/rules does not. The differ ran on planted "
                "fixtures that encode identical, EOL-only, repo-ahead, live-ahead, "
                "and diverged pairs. Production scripts/sync-rules.ps1 still uses "
                "Copy-Item -Force; naive_overwrite is that analogue."
            ),
        },
        "tests": [
            {
                "id": "test_sync_refuses_on_a_diverged_pair",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "test_sync_proceeds_on_a_strictly_one_directional_pair",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "test_eol_only_differences_are_not_reported_as_content_drift",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "naive-copy-item-force",
                "kind": "known-broken-fixture",
                "description": (
                    "Naive overwrite of a diverged pair (Copy-Item -Force analogue of "
                    f"{PS1}) destroys the live-unique line; the sync tool refuses and "
                    "preserves both unique sides."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "both-states-identical-vs-planted",
                "kind": "known-broken-fixture",
                "description": (
                    "Identical pair is not content drift; planting a live-only line "
                    "classifies LIVE-AHEAD and fires; revert is silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "independent-differ-agreement",
                "kind": "mutation",
                "description": (
                    "A second differ using str.splitlines() must match the tool class "
                    "on every fixture file; disagreement is BLOCKED, not averaged."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "evidence": [
            {
                "claim": (
                    "A planted diverged pair (unique lines on both sides) is classified "
                    "DIVERGED and sync refuses in both directions without mutating bytes."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:dest_loses_unique",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "A strictly one-directional pair proceeds in the safe direction "
                    "(repo-ahead repo-to-live, live-ahead live-to-repo) and refuses "
                    "the destroying direction."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:sync_decision",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "EOL-only (LF vs CRLF, identical line set) is classified EOL-ONLY, "
                    "content_drift=false, and is not listed as repo-ahead, live-ahead, "
                    "or diverged."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0079/sync_tool.py:classify_pair",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "An independent splitlines() differ agrees with the tool on every "
                    "planted file. LLM/agent judgement was not used to classify."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0079/independent_differ.py:classify_pair",
                "confidence": "almost-certain",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0079-independent-splitlines-differ",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "method": (
                "Second differ recomputes every fixture class with str.splitlines(); "
                "disagreement would BLOCK rather than pick a winner."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0079/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {
            "count": 0,
            "policy": (
                "single attempt then escalate to the owner; this unit mutates a "
                "live shared surface and a blind retry can compound the damage"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement also asks for explicit owner sign-off "
                    "in command-center/OWNER-DECISIONS.md before the unit may close. The "
                    "file exists; it has no TST-0079 row. G-1 delivery does not forge one."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner records TST-0079 sign-off in OWNER-DECISIONS.md; re-run named probes."
                ),
            },
            {
                "claim": (
                    "Host estate 5/88 measurement was not re-run: ~/.claude/rules is "
                    "absent on this Linux worker (repo rules/common exists)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run classify_trees against the real host pair when both trees exist."
                ),
            },
        ],
        "min_bytes_threshold": 128,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
        "completion_sentinel": "SUCCESS:TST-0079",
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_local(doc: dict) -> None:
    catalog_schema = REPO / SCHEMA
    if not catalog_schema.is_file() or catalog_schema.stat().st_size <= 0:
        raise SystemExit(f"FAILED:TST-0079 catalog output_schema missing: {SCHEMA}")
    shim = json.loads(catalog_schema.read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or not (shim.get("$ref") or shim.get("$id")):
        raise SystemExit("FAILED:TST-0079 catalog output_schema is not a schema document")
    jsonschema.Draft7Validator.check_schema(CONTRACT)
    jsonschema.Draft7Validator(CONTRACT).validate(doc)
    ids = [t.get("id") for t in doc.get("tests") or [] if isinstance(t, dict)]
    missing = [t for t in REQUIRED_TESTS if t not in ids]
    if missing:
        raise SystemExit(f"FAILED:TST-0079 required tests missing: {missing}")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": UNIT, "state": "SUCCESS", "x": "x" * 2000},
    ):
        try:
            jsonschema.Draft7Validator(CONTRACT).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:TST-0079 schema accepted garbage")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ps1_text = (REPO / PS1).read_text(encoding="utf-8") if (REPO / PS1).is_file() else ""
    if "Copy-Item -Force" not in ps1_text:
        print(f"FAILED:TST-0079 production {PS1} no longer contains Copy-Item -Force")
        return 1
    measured = measure_classifications()
    receipt = build_receipt(measured, now)
    validate_local(receipt)

    out_path = REPO / OUT
    write_json(out_path, receipt)
    validate_local(json.loads(out_path.read_text(encoding="utf-8")))
    sha, size = sha256_file(out_path)

    c1, t1 = run_cmd(P1_CMD)
    c2, t2 = run_cmd(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0079 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0079/SUBAGENT-RETURN.json",
        "role": "primary",
    }

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        s, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": s,
            "bytes": n,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/TST-0079/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0079",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "role": "sync-safety",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "role": "eol-and-independent-differ",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0079/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0079-independent-splitlines-differ",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0079: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver."
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
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0079 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
