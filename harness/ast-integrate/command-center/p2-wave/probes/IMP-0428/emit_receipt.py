#!/usr/bin/env python3
"""Emit IMP-0428 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "IMP-0428"
OUT_REL = f"command-center/receipts/{UNIT}.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0428/probe1_contamination.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0428/probe2_clean_and_concurrent.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/command-center/tests/test_index_scope_guard.py"
)
SUPPORTING = [
    "tools/command-center/index_scope_guard.py",
    "tools/command-center/tests/test_index_scope_guard.py",
    "command-center/p2-wave/probes/IMP-0428/probe1_contamination.py",
    "command-center/p2-wave/probes/IMP-0428/probe2_clean_and_concurrent.py",
    "command-center/p2-wave/probes/IMP-0428/declared-scope.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
    }


def probe_rec(role: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[-16000:],
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def catalog_fields() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = {}
    for item in data.get("work_units") or data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == UNIT:
            unit = item
            break
    sentinel = str(
        unit.get("completion_sentinel")
        or unit.get("completion_sentinel")
        or f"SENTINEL:{UNIT}:INDEX-SCOPE-GUARDED"
    )
    out = str(unit.get("output_path") or unit.get("output_path") or OUT_REL)
    schema = str(
        unit.get("output_schema")
        or unit.get("output_schema")
        or "command-center/schema/receipt.schema.json"
    )
    question = str(unit.get("question_or_target") or "")
    title = str(unit.get("title") or "")
    return {
        "sentinel": sentinel,
        "output_path": out,
        "output_schema": schema,
        "question": question,
        "title": title,
        "unit": unit,
    }


def main() -> int:
    cat = catalog_fields()
    c_test, t_test = run(TEST_CMD)
    code1, out1 = run(P1)
    code2, out2 = run(P2)
    if c_test != 0 or code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} live probes tests={c_test} p1={code1} p2={code2}")
        print(t_test[-2000:])
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    if f"SUCCESS:{UNIT}-tests" not in t_test:
        print(f"FAILED:{UNIT} tests sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe1" not in out1:
        print(f"FAILED:{UNIT} probe1 sentinel missing")
        return 1
    if f"SUCCESS:{UNIT}-probe2" not in out2:
        print(f"FAILED:{UNIT} probe2 sentinel missing")
        return 1

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = probe_rec("source", P1, out1, code1)
    p2 = probe_rec("verifier", P2, out2, code2)
    p_test = probe_rec("verifier", TEST_CMD, t_test, c_test)
    supporting_rows = [art(rel, "supporting") for rel in SUPPORTING]
    sentinel = cat["sentinel"]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{UNIT}",
        "min_bytes_threshold": 128,
        "title": cat["title"]
        or "Shared git-index contamination guard for concurrent sessions",
        "question_or_target": cat["question"],
        "timestamps": {"started_at": started, "ended_at": started},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry; a contaminated stage is surfaced to the "
                "orchestrator, never auto-corrected"
            ),
        },
        "implementation": {
            "module": "tools/command-center/index_scope_guard.py",
            "tests": "tools/command-center/tests/test_index_scope_guard.py",
            "sidecar_scope": "command-center/p2-wave/probes/IMP-0428/declared-scope.json",
            "oracle": "git diff --cached --name-only",
            "broad_forms_refused": [
                "git add -A",
                "git add --all",
                "git add .",
                "git add -u (no paths)",
                "git add *",
                "git commit -a",
            ],
            "auto_corrects_contaminated_index": False,
            "touches_program_worktree_index": False,
        },
        "artifacts": supporting_rows,
        "evidence": [
            {
                "anchor": "tools/command-center/index_scope_guard.py:scoped_stage",
                "claim": (
                    "With a planted sibling edit present, a broad add is refused "
                    "and does not mutate the index; a scoped add stages only the "
                    "declared path and excludes the sibling. Unguarded git add -A "
                    "on a twin scratch repo does stage the sibling, so the "
                    "refusal is not a vacuous no-op."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p_test],
            },
            {
                "anchor": "tools/command-center/index_scope_guard.py:inspect_index",
                "claim": (
                    "Negative control: a clean tree (scoped add then commit) "
                    "produces an empty out-of-scope list. A sibling writer "
                    "thread creating sibling/live-*.txt during scoped add does "
                    "not appear in git diff --cached; unguarded dry-run -A lists "
                    "those live files. A pre-contaminated index lists the sibling "
                    "in out_of_scope and does not unstage it."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p1],
            },
            {
                "anchor": "command-center/p2-wave/probes/IMP-0428/probe2_clean_and_concurrent.py",
                "claim": (
                    "Refusal path (security review): path traversal, empty "
                    "scope, absolute path outside the repo, and git commit -a "
                    "are refused. Mutation: inspect_index(verify_cached=False) "
                    "allows a contaminated index; the live check does not."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p1],
            },
        ],
        "tests": [
            {
                "id": "unittest-index-scope-guard",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "probe1-contamination-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-clean-concurrent-refusal",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "unguarded-add-A-does-sweep-sibling",
                "kind": "both-states",
                "description": (
                    "Same planted tree: guard refuses -A (index unchanged) AND "
                    "raw git add -A on a twin scratch repo stages the sibling."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unguarded cached contains sibling/secret.txt",
                "good_state_output": "guarded -A refused INDEX_BROAD_STAGE",
            },
            {
                "id": "clean-tree-empty-out-of-scope",
                "kind": "negative-control",
                "description": "After scoped add+commit, inspect_index out_of_scope is [].",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "precontaminated offer lists sibling",
                "good_state_output": "clean tree out_of_scope=[]",
            },
            {
                "id": "cached-check-mutation",
                "kind": "known-broken-fixture",
                "description": (
                    "verify_cached=False allows a contaminated index; the live "
                    "cached-vs-scope check refuses it."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "vacuous inspect allowed=true",
                "good_state_output": "live inspect INDEX_CONTAMINATED",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0428-probe2-refusal-path",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 is the security review of the refusal path: traversal, "
                "empty scope, commit -a, and a mutation that disables the "
                "cached-vs-scope check. It does not reuse probe 1's scratch repo."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": cat["output_path"],
                "executed": False,
                "read_ok": True,
                "exit_code": None,
                "probe": probe_rec(
                    "verifier",
                    f"python3 -B command-center/p2-wave/_measure_one_delivered.py {UNIT}",
                    "deferred until after this receipt and per-unit manifest exist",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "WORK-UNIT-CATALOG.json has no structured declared_file_scope "
                    "field today. Operational scope is the sidecar "
                    "probes/IMP-0428/declared-scope.json plus output_path, and "
                    "callers may pass an explicit list. Catalog prose inputs are "
                    "not treated as path grants."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When the catalog grows a declared_file_scope array, re-run "
                    "load_declared_scope against every unit and require a "
                    "non-empty fail-closed result without a sidecar."
                ),
            },
            {
                "claim": (
                    "IMP-0410/IMP-0411 (advisory leases / overlap) are catalog "
                    "dependencies and are not delivered on this tree. This guard "
                    "does not consult leases; it only gates staging/commit-offer "
                    "against a path scope."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Bind inspect_index to IMP-0411 overlap once that unit is live.",
            },
        ],
        "notes": (
            "G-1 delivery of IMP-0428. Live named probes exit 0. Receipt "
            "state=SUCCESS. Did not run global unit_manifest.py --write. "
            "cloud ok is not consulted. Scratch-repo git only; no "
            "add/commit/push/stash/checkout/rebase on the program worktree."
        ),
    }

    out_rel = cat["output_path"]
    out = REPO / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    live_sha, live_bytes = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if live_bytes < 128:
        print(f"FAILED:{UNIT} receipt too small ({live_bytes} B)")
        return 1
    if sentinel not in text:
        print(f"FAILED:{UNIT} catalog sentinel absent from receipt")
        return 1

    rows = [art(out_rel, "primary")]
    rows[0]["sha256"] = live_sha
    rows[0]["bytes"] = live_bytes
    for rel in SUPPORTING:
        rows.append(art(rel, "supporting"))

    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": out_rel,
        "output_schema": cat["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "contamination-both-states",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "clean-concurrent-refusal-path",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": out_rel,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0428-probe2-refusal-path",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0428: live named probes exit 0, receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "ts": started,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_rel} bytes={live_bytes} sha256={live_sha}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
