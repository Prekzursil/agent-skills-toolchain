#!/usr/bin/env python3
"""Emit CNF-0122 confirmation artifact and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import walker as W  # noqa: E402

OUT = "command-center/confirmation/CNF-0122-manifest-vs-disk.json"
SCHEMA = "command-center/schema/manifest-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0122/probe1_independence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0122/probe2_unmanifested_control.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0122 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the walker is independent "
    "of the manifest writer and the unmanifested-file control was reported. "
    "Any other terminal state is FAILED:CNF-0122 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Does the artifact manifest describe reality? Walk the disk independently "
    "of the manifest writer and compare both ways, and answer: what is on disk "
    "but unmanifested, what is manifested but absent, and does any manifested "
    "hash disagree with the file it names?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0122/walker.py",
    "command-center/p2-wave/probes/CNF-0122/probe1_independence.py",
    "command-center/p2-wave/probes/CNF-0122/probe2_unmanifested_control.py",
    "command-center/p2-wave/probes/CNF-0122/emit.py",
    "tools/command-center/render.py",
]
RETRY_POLICY = (
    "zero retries. This unit's first observation IS the verdict; a later run "
    "that disagrees is a DISCREPANCY to record (spec 11039), never an error "
    "to retry away"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def snippet(path: Path, line: int, width: int = 3) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    i = max(0, line - 1)
    lo = max(0, i - width)
    hi = min(len(lines), i + width + 1)
    return "\n".join(lines[lo:hi])[:500]


def schema_validator():
    """Draft 2020-12 validator with disk-only $ref store (no network)."""
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        "https://ast-integrate.invalid/command-center/schema/manifest-audit.schema.json": shim,
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=(
            "https://ast-integrate.invalid/command-center/schema/"
            "manifest-audit.schema.json"
        ),
        referrer=shim,
        store=store,
    )
    return jsonschema.Draft202012Validator(shim, resolver=resolver)


def find_charter_paths(repo: Path) -> list[str]:
    """POSIX find over the charter tree. Not walker.walk_disk."""
    cc = repo / "command-center"
    events = cc / "events"
    paths: list[str] = []
    top = subprocess.run(
        [
            "find",
            str(cc),
            "-maxdepth",
            "1",
            "-type",
            "f",
            "-printf",
            "command-center/%f\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if top.returncode == 0:
        paths.extend(p.strip() for p in top.stdout.splitlines() if p.strip())
    if events.is_dir():
        ev = subprocess.run(
            [
                "find",
                str(events),
                "-maxdepth",
                "1",
                "-type",
                "f",
                "-printf",
                "command-center/events/%f\n",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if ev.returncode == 0:
            paths.extend(p.strip() for p in ev.stdout.splitlines() if p.strip())
    return sorted(set(paths))


def probe(
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int = 0,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[-65536:],
        "fingerprint": fingerprint[:128],
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    digest, n = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": n,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    indep = W.independence_report()
    if not indep.get("independent"):
        print("FAILED:CNF-0122 walker is not independent of the writer")
        return 1
    live = W.walk_and_compare(REPO)
    broken = W.run_unmanifested_control()
    clean = W.run_clean_control()
    if not broken.get("reported"):
        print("FAILED:CNF-0122 unmanifested-file control did not fire")
        return 1
    if not clean.get("silent_on_clean"):
        print("FAILED:CNF-0122 clean fixture was not silent")
        return 1

    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:CNF-0122 probes c1={rc1} c2={rc2}")
        print(out1[-1500:])
        print(out2[-1500:])
        return 1

    find_paths = find_charter_paths(REPO)
    walker_disk = sorted(
        [e["path"] for e in live["on_disk_but_unmanifested"]]
        + [e["path"] for e in live["matching"]]
        + [e["path"] for e in live["self_referential"]]
        + [e["path"] for e in live["hash_mismatches"]]
    )
    manifested_live = sorted(
        [e["path"] for e in live["matching"]]
        + [e["path"] for e in live["self_referential"]]
        + [e["path"] for e in live["hash_mismatches"]]
        + [e["path"] for e in live["manifested_but_absent"]]
    )
    find_set = set(find_paths)
    walker_set = set(walker_disk)
    if find_set != walker_set:
        print("FAILED:CNF-0122 find-vs-walker disk set mismatch")
        print("only-find", sorted(find_set - walker_set)[:20])
        print("only-walker", sorted(walker_set - find_set)[:20])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    walker_line = W.walk_and_compare.__code__.co_firstlineno
    render_path = REPO / "tools/command-center/render.py"
    render_line = 1
    for i, line in enumerate(render_path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("def render_manifest"):
            render_line = i
            break

    unman = live["on_disk_but_unmanifested"]
    absent = live["manifested_but_absent"]
    mismatches = live["hash_mismatches"]
    matching = live["matching"]
    describes = bool(live.get("manifest_describes_reality"))
    unman_paths = [e["path"] for e in unman]
    absent_paths = [e["path"] for e in absent]
    mismatch_paths = [e["path"] for e in mismatches]

    tests = [
        {
            "id": "T1-walker-must-not-import-writer",
            "name": (
                "the walker must not import the manifest writer, or a shared "
                "bug certifies itself"
            ),
            "command": P1,
            "result": "PASS" if rc1 == 0 and indep["independent"] else "FAIL",
        },
        {
            "id": "T2-hash-basis-stated",
            "name": (
                "hash comparison must state whether it hashes worktree bytes "
                "or committed bytes, because the two differ on this platform"
            ),
            "command": P1,
            "result": "PASS" if live.get("hash_basis") == W.HASH_BASIS else "FAIL",
        },
        {
            "id": "T3-unmanifested-file-control",
            "name": (
                "control: add one unmanifested file and confirm the "
                "comparison reports it"
            ),
            "command": P2,
            "result": (
                "PASS"
                if broken.get("reported") and clean.get("silent_on_clean")
                else "FAIL"
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0122 a required test did not pass")
        return 1

    summary = (
        "ARTIFACT-MANIFEST.json is present and parses. Independent walk of "
        f"the charter tree found {len(unman)} on-disk file(s) unmanifested, "
        f"{len(absent)} manifested-but-absent path(s), {len(mismatches)} hash "
        f"mismatch(es), {len(matching)} matching hash(es), and "
        f"{len(live.get('self_referential') or [])} self-referential "
        f"ARTIFACT-MANIFEST.json row(s). Charter files present="
        f"{len(live.get('charter_files_present') or [])}/"
        f"{len(W.CHARTER_FILENAMES)}. "
        f"manifest_describes_reality={describes}. Hash basis is "
        f"{live.get('hash_basis')} (not committed git-blob bytes). "
        + COMPLETION_SENTINEL
    )

    validator = schema_validator()
    garbage_rejected = 0
    for garbage in (
        {},
        {"unit_id": "CNF-0122", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if list(validator.iter_errors(garbage)):
            garbage_rejected += 1
        else:
            print("FAILED:CNF-0122 schema accepted garbage")
            return 1

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0122",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0122; "
            "Prompt Two charter tree _USER-PROMPTS.md:10590-10603"
        ),
        "min_bytes_threshold": 1024,
        "profile": "manifest-audit",
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "manifest-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "walker.py does not import tools/command-center/render.py "
                    "or unit_manifest, so a shared writer bug cannot certify itself."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0122/walker.py:1",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        P1,
                        out1[-4000:],
                        "probe1-ast-independence",
                        rc1,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0122/walker.py:FORBIDDEN_IMPORT_ROOTS",
                        json.dumps(indep, sort_keys=True),
                        "file-read-forbidden-imports",
                    ),
                ],
            },
            {
                "claim": (
                    "The unmanifested-file detector control reports "
                    "command-center/UNMANIFESTED-CONTROL.txt on the known-broken "
                    "fixture and is silent on the clean fixture."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0122/walker.py:run_unmanifested_control",
                "probes": [
                    probe(
                        "source",
                        "command",
                        P2,
                        out2[-4000:],
                        "probe2-unmanifested-control",
                        rc2,
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "walker.run_unmanifested_control + walker.run_clean_control",
                        json.dumps(
                            {
                                "reported": broken.get("reported"),
                                "planted_path": broken.get("planted_path"),
                                "silent_on_clean": clean.get("silent_on_clean"),
                                "garbage_schema_rejected": garbage_rejected,
                            },
                            sort_keys=True,
                        ),
                        "emit-both-states-controls",
                    ),
                ],
            },
            {
                "claim": (
                    f"Live set difference on this worktree: {len(unman)} "
                    f"on-disk-but-unmanifested, {len(absent)} manifested-but-absent, "
                    f"{len(mismatches)} hash mismatches. POSIX find agrees with "
                    f"the walker disk set ({len(find_paths)} paths)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": live.get("walker_source") or W.walker_source_anchor(),
                "probes": [
                    probe(
                        "source",
                        "byte-compare",
                        "walker.walk_and_compare(REPO)",
                        json.dumps(
                            {
                                "on_disk_count": live["on_disk_count"],
                                "manifested_count": live["manifested_count"],
                                "unmanifested": len(unman),
                                "absent": len(absent),
                                "hash_mismatches": len(mismatches),
                                "matching": len(matching),
                            },
                            sort_keys=True,
                        ),
                        "walker-walk-and-compare",
                    ),
                    probe(
                        "verifier",
                        "command",
                        "find command-center -maxdepth 1 -type f; find command-center/events -maxdepth 1 -type f",
                        json.dumps(
                            {
                                "find_count": len(find_paths),
                                "find_equals_walker_disk": find_set == walker_set,
                                "manifested_count": len(manifested_live),
                            },
                            sort_keys=True,
                        ),
                        "posix-find-charter-tree",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "unmanifested-file-control",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant command-center/UNMANIFESTED-CONTROL.txt plus a hash "
                    "mismatch and an absent manifested path. The walker must "
                    "report the planted file as on-disk-but-unmanifested."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "planted_path": broken["planted_path"],
                        "unmanifested_paths": broken["unmanifested_paths"],
                        "absent_paths": broken["absent_paths"],
                        "hash_mismatch_paths": broken["hash_mismatch_paths"],
                    },
                    sort_keys=True,
                )[:16384],
                "good_state_output": json.dumps(
                    {
                        "unmanifested_paths": clean["unmanifested_paths"],
                        "absent_paths": clean["absent_paths"],
                        "hash_mismatch_paths": clean["hash_mismatch_paths"],
                        "silent_on_clean": True,
                    },
                    sort_keys=True,
                )[:16384],
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0122-probe2-unmanifested-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Reviewer re-ran the DETECTOR CONTROL (probe2) on the "
                "known-broken fixture and the clean fixture. Re-reading this "
                "receipt is not the review."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0122/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0122",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + Draft202012Validator(manifest-audit)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -c json.loads + jsonschema.Draft202012Validator "
                        "with disk RefResolver store for manifest-audit.schema.json"
                    ),
                    f"in-memory schema errors=0; garbage rejected={garbage_rejected}/3",
                    "schema-validate-manifest-audit",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": RETRY_POLICY,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether a later render_manifest rewrite of "
                    "ARTIFACT-MANIFEST.json would shrink the unmanifested set "
                    "is not measured here; this unit must not run the writer."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run tools/command-center/render.py:render_manifest in a "
                    "separate unit, then re-run walker.walk_and_compare and "
                    "diff the two on_disk_but_unmanifested lists."
                ),
            }
        ],
        "report": {
            "kind": "manifest-audit",
            "observations": [
                {
                    "name": "manifest_present",
                    "measured": bool(live.get("manifest_present")),
                    "method": "json.loads of command-center/ARTIFACT-MANIFEST.json",
                    "anchor": "command-center/ARTIFACT-MANIFEST.json:1",
                },
                {
                    "name": "on_disk_but_unmanifested_count",
                    "measured": len(unman),
                    "method": "walker.walk_and_compare set difference",
                    "anchor": live.get("walker_source") or W.walker_source_anchor(),
                },
                {
                    "name": "manifested_but_absent_count",
                    "measured": len(absent),
                    "method": "walker.walk_and_compare set difference",
                    "anchor": live.get("walker_source") or W.walker_source_anchor(),
                },
                {
                    "name": "hash_mismatch_count",
                    "measured": len(mismatches),
                    "method": "worktree-bytes-lf-normalized SHA-256 vs manifest sha256",
                    "anchor": live.get("walker_source") or W.walker_source_anchor(),
                },
                {
                    "name": "manifest_describes_reality",
                    "measured": describes,
                    "method": "empty unmanifested, absent, and mismatch lists and manifest_status=ok",
                    "anchor": live.get("walker_source") or W.walker_source_anchor(),
                },
                {
                    "name": "walker_independent_of_writer",
                    "measured": True,
                    "method": "AST import scan of walker.py",
                    "anchor": "command-center/p2-wave/probes/CNF-0122/probe1_independence.py",
                },
                {
                    "name": "unmanifested_file_control_reported",
                    "measured": True,
                    "method": "known-broken fixture plant",
                    "anchor": "command-center/p2-wave/probes/CNF-0122/probe2_unmanifested_control.py",
                },
                {
                    "name": "find_agrees_with_walker_disk_set",
                    "measured": True,
                    "method": "POSIX find -maxdepth 1 -type f",
                    "anchor": "command-center/p2-wave/probes/CNF-0122/emit.py:find_charter_paths",
                },
            ],
            "control_ids": [
                "unmanifested-file-control",
                "clean-fixture-silent",
                "walker-independence",
            ],
            "question": QUESTION,
            "answers": {
                "manifest_present": live.get("manifest_present"),
                "manifest_status": live.get("manifest_status"),
                "manifest_describes_reality": describes,
                "on_disk_but_unmanifested_count": len(unman),
                "on_disk_but_unmanifested_paths": unman_paths,
                "manifested_but_absent_count": len(absent),
                "manifested_but_absent_paths": absent_paths,
                "hash_mismatch_count": len(mismatches),
                "hash_mismatch_paths": mismatch_paths,
                "matching_count": len(matching),
                "charter_files_present": live.get("charter_files_present"),
                "charter_files_absent": live.get("charter_files_absent"),
                "summary": summary,
            },
            "hash_basis": {
                "mode": live.get("hash_basis"),
                "committed_bytes_used": False,
                "note": live.get("hash_basis_note"),
            },
            "walker": {
                "path": "command-center/p2-wave/probes/CNF-0122/walker.py",
                "function": "walk_and_compare",
                "line": walker_line,
                "source": live.get("walker_source"),
                "imports_manifest_writer": False,
                "writer_path": "tools/command-center/render.py",
                "writer_function": "render_manifest",
                "writer_line": render_line,
                "snippet": snippet(HERE / "walker.py", walker_line),
            },
            "live_comparison": live,
            "unmanifested_file_control": {
                "planted_path": broken["planted_path"],
                "reported": True,
                "unmanifested_paths": broken["unmanifested_paths"],
                "also_reported_absent": broken["absent_paths"],
                "also_reported_hash_mismatches": broken["hash_mismatch_paths"],
                "clean_fixture_silent": True,
            },
            "independence": indep,
            "posix_find_verifier": {
                "path_count": len(find_paths),
                "equals_walker_disk_set": True,
            },
        },
        "extensions": {
            "completion_sentinel": COMPLETION_SENTINEL,
            "named_probes": [
                {
                    "id": "probe1",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1[-4000:],
                },
                {
                    "id": "probe2",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2[-4000:],
                },
            ],
        },
    }

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:CNF-0122 schema " + errors[0].message)
        for err in errors[:20]:
            print(" ", list(err.path), err.message)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0122 completion sentinel missing from artifact")
        return 1
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    post = sorted(validator.iter_errors(loaded), key=lambda e: list(e.path))
    if post:
        print("FAILED:CNF-0122 on-disk schema " + post[0].message)
        return 1
    sha, size = digest_file(out_path)
    if size <= 0:
        print("FAILED:CNF-0122 empty artifact")
        return 1
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0122 artifact {size}B below floor")
        return 1

    def man_row(rel: str, role: str) -> dict:
        path = REPO / rel
        digest, n = digest_file(path)
        return {
            "path": rel,
            "sha256": digest,
            "bytes": n,
            "present": True,
            "unit_id": "CNF-0122",
            "receipt_path": "command-center/p2-wave/probes/CNF-0122/SUBAGENT-RETURN.json",
            "role": role,
        }

    primary = man_row(OUT, "primary")
    artifacts = [primary] + [man_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "CNF-0122",
        "unit_id": "CNF-0122",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0122",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
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
        "manifest_path": "command-center/p2-wave/probes/CNF-0122/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0122-probe2-unmanifested-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0122: live named probes exit 0, "
            "CNF-0122-manifest-vs-disk.json state=SUCCESS, per-unit manifest row. "
            "Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0122",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"unmanifested={len(unman)} absent={len(absent)} "
        f"mismatches={len(mismatches)} matching={len(matching)}"
    )
    print("SUCCESS:CNF-0122 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
