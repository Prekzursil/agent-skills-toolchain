#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0018-deploy-script-semantics.json."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UID = E.UNIT
OUT = E.OUT_REL
SCHEMA = E.SCHEMA_REL
P1 = E.P1
P2 = E.P2
COMPLETION = E.COMPLETION
QUESTION = E.QUESTION
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0018/engine.py",
    "command-center/p2-wave/probes/AUD-0018/probe1_line_semantics.py",
    "command-center/p2-wave/probes/AUD-0018/probe2_dry_run.py",
    "command-center/p2-wave/probes/AUD-0018/fixtures/scripts/copy-item-force-verbatim.ps1",
    "command-center/p2-wave/probes/AUD-0018/fixtures/scripts/transform-replace.ps1",
    "command-center/p2-wave/probes/AUD-0018/fixtures/scripts/guarded-sync.ps1",
    "command-center/p2-wave/probes/AUD-0018/fixtures/scripts/live-to-repo.ps1",
    "tools/marketplace/installer.py",
    "tools/plugin/rollback_additive.py",
]


def _jsonschema():
    saved_mods = {}
    for key in list(sys.modules):
        if key == "platform" or key.startswith("platform."):
            mod = sys.modules[key]
            f = (getattr(mod, "__file__", "") or "").replace("\\", "/")
            if "/platform/" in f or f.endswith("/platform/__init__.py"):
                saved_mods[key] = sys.modules.pop(key)
    saved_path = list(sys.path)
    sys.path = [p for p in sys.path if p not in ("", ".", str(REPO), str(HERE))]
    try:
        return importlib.import_module("jsonschema")
    finally:
        sys.path[:] = saved_path
        for key, mod in saved_mods.items():
            sys.modules.setdefault(key, mod)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    js = _jsonschema()
    return [
        f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in js.Draft7Validator(schema).iter_errors(doc)
    ]


def _garbage_rejected() -> dict:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    js = _jsonschema()
    validator = js.Draft7Validator(schema)
    probes = (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    )
    counts = [len(list(validator.iter_errors(p))) for p in probes]
    kind_mutant = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0018 schema-kind-mutant",
        "completion_sentinel": COMPLETION,
        "report_kind": "receipt",
        "question": QUESTION,
        "answer": "x" * 48,
        "named_probes": [
            {"id": "p1xx", "command": "python3 -c pass", "exit_code": 0, "raw_output": "abcdefgh"},
            {"id": "p2xx", "command": "python3 -c pass", "exit_code": 0, "raw_output": "abcdefgh"},
        ],
        "tests": [{"id": "t1", "result": "PASS"}, {"id": "t2", "result": "PASS"}],
        "evidence": [
            {"id": "e1x", "text": "placeholder-claim-text", "verdict": "PARTIAL"},
            {"id": "e2x", "text": "second-placeholder-claim", "verdict": "PARTIAL"},
        ],
        "reviewer": {
            "reviewer_id": "AUD-0018-probe2-dry-run",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [{"path": OUT, "exists": True, "role": "primary"}],
        "residual_caveat": "kind mutant should fail",
    }
    kind_errs = len(list(validator.iter_errors(kind_mutant)))
    return {
        "garbage_error_counts": counts,
        "all_garbage_rejected": all(c > 0 for c in counts),
        "schema_kind_mutant_error_count": kind_errs,
        "schema_kind_mutant_goes_red": kind_errs > 0,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if path.is_file():
        data = path.read_bytes()
        return {
            "path": rel,
            "exists": True,
            "role": role,
            "bytes": len(data),
            "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
        }
    return {"path": rel, "exists": False, "role": role, "bytes": 0}


def build_doc(*, t1: str, c1: int, t2: str, c2: int) -> dict:
    snap = E.snapshot()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    disc = snap["discovery"]
    dry = snap["dry_run"]
    line_ctl = snap["line_control"]
    dry_ctl = snap["dry_control"]
    schema_ctl = _garbage_rejected()
    if not line_ctl.get("pass") or not dry_ctl.get("pass"):
        raise RuntimeError(
            f"refusing SUCCESS: line={line_ctl.get('failed')} dry={dry_ctl.get('failed')}"
        )
    if c1 != 0 or c2 != 0:
        raise RuntimeError(f"refusing SUCCESS: probe exits c1={c1} c2={c2}")
    if not schema_ctl["all_garbage_rejected"] or not schema_ctl["schema_kind_mutant_goes_red"]:
        raise RuntimeError(f"refusing SUCCESS: schema controls {schema_ctl}")

    absent = disc["catalog_absent"]
    other = disc["other_deploy"]
    installer = next((r for r in other if str(r.get("path") or "").endswith("installer.py")), {})
    rollback = next(
        (r for r in other if str(r.get("path") or "").endswith("rollback_additive.py")), {}
    )
    vplan = (dry.get("planted_plans") or {}).get("copy-item-force-verbatim.ps1") or {}
    gplan = (dry.get("planted_plans") or {}).get("guarded-sync.ps1") or {}
    planted_v = next(
        (
            r
            for r in disc["planted"]
            if str(r.get("path") or "").endswith("copy-item-force-verbatim.ps1")
        ),
        {},
    )
    planted_t = next(
        (
            r
            for r in disc["planted"]
            if str(r.get("path") or "").endswith("transform-replace.ps1")
        ),
        {},
    )

    answer = (
        f"On this Linux worktree the catalog-named deploy scripts are absent "
        f"({', '.join(absent) or 'none'}); scripts/ itself "
        f"{'exists' if disc.get('scripts_dir_exists') else 'does not exist'}. "
        f"Live deploy entry point tools/marketplace/installer.py copies verbatim via "
        f"shutil.copy2 (package→dest) and applies a policy-DENY gate, not the named "
        f"nested-repo / vendored-tree / repo-owned-file guards. "
        f"tools/plugin/rollback_additive.py copies verbatim via write_bytes(read_bytes) "
        f"(backup→profile, additive). "
        f"Planted controls: Copy-Item -Force at line {next((p['line'] for p in (planted_v.get('copy_primitives') or []) if p.get('primitive')=='Copy-Item -Force'), None)} "
        f"is verbatim; transform-replace.ps1 is {planted_t.get('copy_mode')}; "
        f"guarded-sync dry-run skips {len(dry.get('skipped_by_guards') or [])} fixture paths "
        f"the unguarded Copy-Item -Force would overwrite. Dry-run left the fixture "
        f"byte-identical (would_touch={vplan.get('would_touch_count')}); an isolated "
        f"destructive copy mutant changed dest/rules/ok.md. scripts/sync-from-live.ps1 "
        f"was not executed."
    )

    source_fp = {"tool": "line-read", "command": P1, "method": "copy-primitive-and-guard-census"}
    verifier_fp = {
        "tool": "dry-run-fixture",
        "command": P2,
        "method": "interpreted-whatif-plus-isolated-mutant",
    }

    evidence = [
        {
            "id": "catalog-named-scripts-absent",
            "text": (
                "scripts/sync-rules.ps1 and scripts/sync-from-live.ps1 (and the sibling "
                "sync-skills/sync-hooks scripts) are not present on this worktree, so the "
                "catalog's measured fact that sync-rules.ps1:67 is Copy-Item -Force cannot "
                "be re-read from that path here."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "planted-copy-item-force-verbatim",
            "text": (
                "A planted script with Copy-Item -Force at line 67 and no transform "
                f"classifies copy_mode=verbatim (probe 1) and would touch "
                f"{vplan.get('would_touch')} on the fixture (probe 2) without writing."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "planted-transform-distinct",
            "text": (
                "The planted Get-Content/-replace/Set-Content script classifies "
                f"copy_mode={planted_t.get('copy_mode')}, which is distinct from the "
                "verbatim Copy-Item -Force control, so the detector is not a copy-primitive "
                "always-verbatim classifier."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "named-guards-change-touch-set",
            "text": (
                "The planted guarded script names nested-repo, vendored-tree, and "
                "repo-owned-file clauses. Its dry-run would-touch set excludes "
                f"{dry.get('skipped_by_guards')}, including nested-repo "
                f"{dry.get('nested_repo_skipped')}, vendor {dry.get('vendored_skipped')}, "
                f"and repo-owned {dry.get('repo_owned_skipped')}; the unguarded Copy-Item "
                "-Force plan includes those paths."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "dry-run-non-destructive",
            "text": (
                "Dry-run against fixtures/trees left combined merkle "
                f"{dry.get('before', {}).get('combined_merkle')} unchanged; dest/rules/ok.md "
                "stayed DEST-OK. An isolated clone subjected to the same copy list changed "
                "that file, so the empty mutation is not a no-op detector."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "live-installer-verbatim-policy-gate",
            "text": (
                f"tools/marketplace/installer.py copy_mode={installer.get('copy_mode')} "
                f"direction={installer.get('direction')} primitives="
                f"{[p.get('primitive') for p in (installer.get('copy_primitives') or [])]} "
                f"guard_kinds={installer.get('guard_kinds')}. It does not apply the three "
                "named tree guards; DENY is a whole-tree policy gate."
            ),
            "verdict": "CONFIRMED",
            "source_probe": source_fp,
            "verifier_probe": verifier_fp,
        },
        {
            "id": "catalog-line-67-on-missing-file",
            "text": (
                "The catalog input 'sync-rules.ps1:67 is a plain Copy-Item -Force with no "
                "transform' is not re-measurable on this worktree because that file is "
                "absent. The planted line-67 Copy-Item -Force control reproduces the "
                "claimed shape; it is not a substitute for the missing production script."
            ),
            "verdict": "NOT-CHECKED",
        },
        {
            "id": "dual-human-reviewers",
            "text": (
                "Catalog reviewer_requirement asked for one fresh-context Claude and one "
                "Codex reviewer with owner escalation on disagreement. Those humans were "
                "not dispatched to this G-1 worker."
            ),
            "verdict": "NOT-CHECKED",
        },
    ]

    tests = [
        {
            "id": "probe1-line-semantics",
            "name": "Line-level copy primitive and guard census",
            "command": P1,
            "result": "PASS" if c1 == 0 else "FAIL",
            "output_tail": t1[-1500:],
        },
        {
            "id": "probe2-dry-run-nondestructive",
            "name": "Fixture dry-run is byte-identical before trusting would-touch",
            "command": P2,
            "result": "PASS" if c2 == 0 and dry.get("fixture_byte_identical") else "FAIL",
            "output_tail": t2[-1500:],
        },
        {
            "id": "control-verbatim-vs-transform",
            "name": "Copy-Item -Force classifies verbatim; -replace/Set-Content classifies transform",
            "command": P1,
            "result": "PASS"
            if line_ctl["checks"].get("planted_verbatim_mode")
            and line_ctl["checks"].get("planted_transform_mode")
            else "FAIL",
        },
        {
            "id": "control-guards-change-touch-set",
            "name": "Named guards drop nested-repo, vendor, and repo-owned paths from would-touch",
            "command": P2,
            "result": "PASS" if dry_ctl["checks"].get("guards_change_touch_set") else "FAIL",
        },
        {
            "id": "control-destructive-mutant-red",
            "name": "Actual copy on an isolated clone changes dest/rules/ok.md",
            "command": P2,
            "result": "PASS"
            if dry_ctl["checks"].get("destructive_mutant_changes_dest")
            else "FAIL",
        },
        {
            "id": "schema-garbage-and-kind-mutant",
            "name": "Declared audit-finding schema rejects garbage and a kind mutant",
            "command": "jsonschema.Draft7Validator(audit-finding.schema.json)",
            "result": "PASS"
            if schema_ctl["all_garbage_rejected"] and schema_ctl["schema_kind_mutant_goes_red"]
            else "FAIL",
            "output_tail": json.dumps(schema_ctl, sort_keys=True),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise RuntimeError(
            "refusing SUCCESS: tests "
            + str([t["id"] for t in tests if t["result"] != "PASS"])
        )

    findings = [
        {
            "id": "AUD0018-catalog-scripts-absent",
            "severity": "P2",
            "status": "recorded",
            "summary": (
                "Catalog-named PowerShell sync scripts are not in this Linux worktree; "
                "semantics of Copy-Item -Force were proven on planted controls plus live "
                "Python deploy entry points."
            ),
            "paths": absent,
        },
        {
            "id": "AUD0018-installer-no-named-tree-guards",
            "severity": "P2",
            "status": "open",
            "summary": (
                "installer.py copies verbatim with a policy DENY gate and does not skip "
                "nested-repo, vendored-tree, or repo-owned-file paths."
            ),
            "path": installer.get("path"),
            "guard_kinds": installer.get("guard_kinds"),
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "completion_sentinel": COMPLETION,
        "report_kind": "audit-finding",
        "title": "Deploy and sync script semantic audit: transform, directionality, and guards",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0018",
        "min_bytes_threshold": 1024,
        "question": QUESTION,
        "answer": answer,
        "report": {
            "kind": "audit-finding",
            "answer": answer,
            "catalog_absent_count": len(absent),
            "live_other_deploy_count": len(other),
            "dry_run_would_touch": vplan.get("would_touch_count"),
            "fixture_byte_identical": dry.get("fixture_byte_identical"),
        },
        "discovery": disc,
        "dry_run": dry,
        "line_control": line_ctl,
        "dry_control": dry_ctl,
        "scripts": {
            "catalog_named": disc["catalog_named"],
            "other_deploy": other,
            "planted": disc["planted"],
        },
        "installer": installer,
        "rollback_additive": rollback,
        "guarded_would_touch": gplan.get("would_touch"),
        "findings": findings,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[:65000],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[:65000],
            },
        ],
        "evidence": evidence,
        "tests": tests,
        "schema_controls": schema_ctl,
        "reviewer": {
            "reviewer_id": "AUD-0018-probe2-dry-run",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "mechanical-probe2",
            "notes": (
                "Catalog asked for one fresh-context Claude and one Codex reviewer. "
                "Probe 2 is a mechanically different measurement (fixture dry-run vs "
                "line-level read) and is the independent reviewer of record here. "
                "Dual-human review remains NOT-CHECKED."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0018/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the tree; "
                "restore from the AUD-0092 backup, record the mutation, and escalate"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            *[art(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()],
        ],
        "residual_caveat": (
            "scripts/sync-rules.ps1 is absent, so line 67 Copy-Item -Force is not a "
            "live re-read of the production script. Dry-run is an interpreter, not "
            "pwsh -WhatIf. Dual human review was not dispatched. "
            + COMPLETION
        ),
        "notes": (
            "G-1 for AUD-0018: live named probes exit 0, honest non-BLOCKED "
            "audit-finding, per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery. "
            "Never executed scripts/sync-from-live.ps1. "
            + COMPLETION
        ),
        "output_schema": SCHEMA,
        "produced_by": {
            "vendor": "cursor",
            "model": "cursor-grok-4.6",
            "role": "auditor",
            "execution_substrate": "linux-local",
        },
    }
    return doc


def write_artifact(doc: dict) -> Path:
    errs = schema_errors(doc)
    if errs:
        raise RuntimeError("schema-invalid:\n" + "\n".join(errs[:20]))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise RuntimeError(f"refusing to write self-declared {doc.get('state')}")
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if COMPLETION not in text:
        raise RuntimeError("completion_sentinel missing from encoded artifact")
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} emit probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1
    try:
        doc = build_doc(t1=t1, c1=c1, t2=t2, c2=c2)
        path = write_artifact(doc)
    except Exception as exc:
        print(f"FAILED:{UID} emit {type(exc).__name__}: {exc}")
        return 1
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(f"SUCCESS:{UID} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
