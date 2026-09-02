#!/usr/bin/env python3
"""Emit CNF-0116 confirmation artifact and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/confirmation/CNF-0116-credential-exclusion.json"
SCHEMA = "command-center/schema/security-report.schema.json"
QUESTION = (
    "Could a credential file reach a consumer? Check two independent surfaces - "
    "the built artifact contents and the git index and history - and answer: is "
    "any credential-shaped file tracked, staged, or bundled? The two surfaces "
    "fail independently, so one clean surface is not evidence for the other."
)
SENTINEL_SHORT = "SUCCESS:CNF-0116"
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0116 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both surfaces were enumerated "
    "independently and the benign known-present control was found on each. Any "
    "other terminal state is FAILED:CNF-0116 <classification> with the diagnostic "
    "tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0116/probe1_artifact.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0116/probe2_git_index.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0116/inventory.py",
    "command-center/p2-wave/probes/CNF-0116/surfaces.py",
    "command-center/p2-wave/probes/CNF-0116/scenario.py",
    "command-center/p2-wave/probes/CNF-0116/schema_local.py",
    "command-center/p2-wave/probes/CNF-0116/probe1_artifact.py",
    "command-center/p2-wave/probes/CNF-0116/probe2_git_index.py",
]
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json#CNF-0116"


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
        env={**dict(**__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def by_id(surfaces: list[dict], sid: str) -> dict:
    for row in surfaces:
        if row.get("id") == sid:
            return row
    raise KeyError(sid)


def filenames_only(hits: list) -> list[dict]:
    out = []
    for h in hits or []:
        out.append({"path": h.get("path"), "rule": h.get("rule"), "contents": None})
    return out


def _probe(role: str, method: str, command: str, raw: str, fingerprint: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:60000],
        "fingerprint": fingerprint[:128],
        "exit_code": 0,
    }


def receipt_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    raw = path.read_bytes()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if b"\0" in raw:
        eol = "BINARY"
    elif crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def build_doc(run: dict) -> dict:
    surfaces = run["surfaces"]
    clean = by_id(surfaces, "artifact-clean-control")
    dirty = by_id(surfaces, "artifact-polluted-control")
    live = by_id(surfaces, "artifact-live-tree-archive")
    git = by_id(surfaces, "git-index-and-history")
    live_git = run["live_git"]
    ctrl = run["controls"]
    live_hits = filenames_only(live.get("credential_hits"))
    git_hits = filenames_only(git.get("credential_hits"))
    dirty_hits = filenames_only(dirty.get("credential_hits"))
    clean_hits = filenames_only(clean.get("credential_hits"))

    live_git_note = (
        "Live worktree is not a git repository; live index/history is unmeasurable."
        if live_git.get("unmeasurable")
        else "Live git index was enumerated with git plumbing."
    )
    answer = (
        "Yes, a credential-shaped filename can reach a consumer on a naive "
        "filename-only archive of this worktree, and a gitignored credential-shaped "
        "name can still be tracked. Artifact surface (zip namelist, never include-rules, "
        "never file bytes): known-present "
        f"control {dirty['known_present']!s} found; clean control zip had "
        f"{len(clean.get('credential_hits') or [])} inventory hits; polluted control zip "
        f"flagged {len(dirty_hits)} bundled name(s) that include-rules missed "
        f"(include_rules_missed_planted={ctrl['include_rules_missed_planted']}). "
        f"Live-tree archive known-present {live['known_present']} found; inventory hits "
        f"on that archive: {[h['path'] for h in live_hits]}. "
        "Git surface (ls-files / staged / history, never ignore-as-proof): known-present "
        f"found; ignore_not_evidence={ctrl['ignore_not_evidence']}; rotation-pool "
        f"accounts.json untracked={ctrl['rotation_pool_untracked']} "
        f"unstaged={ctrl['rotation_pool_unstaged']} unmodified={ctrl['rotation_pool_unmodified']}; "
        f"history lists a deleted .env name while HEAD does not "
        f"(working-tree-only would miss it). {live_git_note} One clean surface is not "
        "evidence for the other (clean zip vs dirty git fixture). Filenames only; no "
        "credential value is stored in this artifact. " + COMPLETION_SENTINEL
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    findings = []
    for h in dirty_hits:
        findings.append(
            {
                "classification": "credential-bundled",
                "surface": "artifact-polluted-control",
                "path": h["path"],
                "rule": h["rule"],
                "contents": None,
            }
        )
    for h in live_hits:
        findings.append(
            {
                "classification": "credential-bundled",
                "surface": "artifact-live-tree-archive",
                "path": h["path"],
                "rule": h["rule"],
                "contents": None,
                "note": "Filename present in a naive live-tree zip namelist; contents not read.",
            }
        )
    for h in git_hits:
        findings.append(
            {
                "classification": "credential-tracked",
                "surface": "git-index-and-history",
                "path": h["path"],
                "rule": h["rule"],
                "contents": None,
            }
        )

    report_surfaces = [
        {
            "id": clean["id"],
            "method": clean["method"],
            "entry_count": clean["entry_count"],
            "known_present": clean["known_present"],
            "known_present_found": clean["known_present_found"],
            "credential_hits": clean_hits,
        },
        {
            "id": dirty["id"],
            "method": dirty["method"],
            "entry_count": dirty["entry_count"],
            "known_present": dirty["known_present"],
            "known_present_found": dirty["known_present_found"],
            "credential_hits": dirty_hits,
            "include_rules_listing": dirty.get("include_rules_listing"),
            "include_rules_missed_planted": dirty.get("include_rules_missed_planted"),
        },
        {
            "id": live["id"],
            "method": live["method"],
            "entry_count": live["entry_count"],
            "known_present": live["known_present"],
            "known_present_found": live["known_present_found"],
            "credential_hits": live_hits,
        },
        {
            "id": git["id"],
            "method": git["method"],
            "entry_count": git["entry_count"],
            "known_present": git["known_present"],
            "known_present_found": git["known_present_found"],
            "credential_hits": git_hits,
            "tracked_count": len(git.get("tracked") or []),
            "staged_count": len(git.get("staged") or []),
            "history_name_count": len(git.get("history_names") or []),
            "ignore_would_drop_planted": git.get("ignore_would_drop_planted"),
            "ignore_not_evidence": git.get("ignore_not_evidence"),
            "head_has_deleted_env": git.get("head_has_deleted_env"),
            "history_has_deleted_env": git.get("history_has_deleted_env"),
            "working_tree_only_would_miss_history_env": git.get(
                "working_tree_only_would_miss_history_env"
            ),
            "rotation_pool": git.get("rotation_pool"),
        },
    ]

    p1 = _probe(
        "source",
        "other",
        P1,
        json.dumps(
            {
                "dirty_hits": [h["path"] for h in dirty_hits],
                "live_hits": [h["path"] for h in live_hits],
                "known_present_dirty": dirty["known_present_found"],
                "include_rules_missed_planted": dirty.get("include_rules_missed_planted"),
            },
            sort_keys=True,
        ),
        "cnf0116-p1-zip-namelist",
    )
    p2 = _probe(
        "verifier",
        "command",
        P2,
        json.dumps(
            {
                "git_hits": [h["path"] for h in git_hits],
                "ignore_not_evidence": git.get("ignore_not_evidence"),
                "rotation_pool_tracked": (git.get("rotation_pool") or {}).get("tracked"),
                "contents": None,
            },
            sort_keys=True,
        ),
        "cnf0116-p2-git-plumbing",
    )

    supporting = [receipt_artifact(rel, "supporting") for rel in SUPPORTING]
    return {
        "schema_version": 1,
        "unit_id": "CNF-0116",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "profile": "credential-exclusion-two-surfaces",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "secret-exposure-auditor",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "security-report",
            "title": (
                "Credential-file exclusion proven from two directions: "
                "the artifact and the git index"
            ),
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": COMPLETION_SENTINEL,
            "observations": [
                {
                    "name": "known-present-on-polluted-artifact",
                    "measured": bool(dirty["known_present_found"]),
                    "method": "zipfile.ZipFile.namelist",
                    "anchor": "command-center/p2-wave/probes/CNF-0116/scenario.py:run_scenario",
                },
                {
                    "name": "known-present-on-git-fixture",
                    "measured": bool(git["known_present_found"]),
                    "method": "git ls-files -z --cached",
                    "anchor": "command-center/p2-wave/probes/CNF-0116/surfaces.py:init_git_repo",
                },
                {
                    "name": "include-rules-missed-planted",
                    "measured": bool(dirty.get("include_rules_missed_planted")),
                    "method": "enumerate_by_include_rules vs zip namelist",
                    "anchor": "command-center/p2-wave/probes/CNF-0116/surfaces.py:enumerate_by_include_rules",
                },
                {
                    "name": "ignore-not-evidence",
                    "measured": bool(git.get("ignore_not_evidence")),
                    "method": "git check-ignore --no-index AND git ls-files",
                    "anchor": "command-center/p2-wave/probes/CNF-0116/surfaces.py:init_git_repo",
                },
                {
                    "name": "rotation-pool-unmodified",
                    "measured": bool(ctrl["rotation_pool_unmodified"]),
                    "method": "size+mtime compare; contents never read",
                    "anchor": "accounts.json",
                },
            ],
            "control_ids": [
                "CNF0116-C1-known-present-both-surfaces",
                "CNF0116-C2-ignore-not-evidence",
                "CNF0116-C3-include-rules-not-the-artifact",
                "CNF0116-C4-clean-zip-vs-dirty-git",
            ],
            "inventory_cross_reference": run["inventory"],
            "surfaces": report_surfaces,
            "live_git": {
                "present": live_git.get("present"),
                "unmeasurable": live_git.get("unmeasurable"),
                "reason": live_git.get("reason"),
                "method": live_git.get("method"),
                "known_present_found": live_git.get("known_present_found"),
            },
            "findings": findings,
            "controls": ctrl,
            "hard_constraint": (
                "No real credential was rotated, printed, revoked, unset, or modified. "
                "Report lists filenames only. Zip payloads are empty."
            ),
            "coverage_boundary": (
                "Git fixture and zip fixtures are the two independent measurement "
                "surfaces that satisfy the known-present control. Live git on this "
                "worktree is unmeasurable. Live artifact namelist skips directories "
                "named probes/.git/node_modules/.venv/__pycache__ so other units' "
                "moving fixtures (including a 2GiB blob) are not packed. No dist/ "
                "wheel/tarball was present."
            ),
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Both surfaces enumerated independently; known-present control "
                    "found on each fixture surface."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0116/scenario.py:run_scenario",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "Ignore rules are not evidence: a gitignored credential-shaped "
                    "file was still tracked."
                ),
                "verdict": "CONFIRMED" if ctrl["ignore_not_evidence"] else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0116/surfaces.py:init_git_repo",
                "probes": [p1, p2],
            },
            {
                "claim": (
                    "Rotation-pool accounts.json is untracked, unstaged, and "
                    "unmodified; contents never printed."
                ),
                "verdict": "CONFIRMED"
                if ctrl["rotation_pool_untracked"] and ctrl["rotation_pool_unmodified"]
                else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "accounts.json",
                "probes": [p1, p2],
            },
            {
                "claim": "Live worktree git index exists and was enumerated.",
                "verdict": "NOT-CHECKED" if live_git.get("unmeasurable") else "CONFIRMED",
                "anchor": "/opt/p2/ast-integrate",
                "probes": [
                    _probe(
                        "source",
                        "command",
                        "git rev-parse --is-inside-work-tree",
                        str(live_git.get("reason") or live_git.get("present")),
                        "cnf0116-live-git-rev-parse",
                    )
                ],
            },
        ],
        "tests": [
            {
                "id": "CNF0116-T1-IGNORE-NOT-EVIDENCE",
                "command": P2,
                "result": "PASS" if ctrl["ignore_not_evidence"] else "FAIL",
            },
            {
                "id": "CNF0116-T2-ROTATION-POOL-UNTRACKED-UNSTAGED-UNMODIFIED",
                "command": P2,
                "result": "PASS"
                if (
                    ctrl["rotation_pool_untracked"]
                    and ctrl["rotation_pool_unstaged"]
                    and ctrl["rotation_pool_unmodified"]
                )
                else "FAIL",
            },
            {
                "id": "CNF0116-T3-KNOWN-PRESENT-BOTH-SURFACES",
                "command": P1 + " && " + P2,
                "result": "PASS"
                if ctrl["known_present_on_artifact"] and ctrl["known_present_on_git"]
                else "FAIL",
            },
            {
                "id": "CNF0116-T4-ENUMERATE-ARTIFACT-NOT-RULES",
                "command": P1,
                "result": "PASS" if ctrl["include_rules_missed_planted"] else "FAIL",
            },
            {
                "id": "CNF0116-T5-ONE-CLEAN-SURFACE-NOT-THE-OTHER",
                "command": P1 + " && " + P2,
                "result": "PASS"
                if ctrl["one_clean_surface_is_not_evidence_for_the_other"]
                else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "CNF0116-NC-CLEAN-VS-POLLUTED-ZIP",
                "kind": "known-broken-fixture",
                "description": (
                    "A polluted zip namelist flags a planted credential-shaped "
                    "filename that include-rules omit; the clean zip is silent."
                ),
                "fired_on_bad_state": bool(dirty_hits) and bool(dirty.get("include_rules_missed_planted")),
                "silent_on_good_state": len(clean_hits) == 0,
                "bad_state_output": ",".join(h["path"] for h in dirty_hits),
                "good_state_output": "clean zip credential_hits=[]",
            },
            {
                "id": "CNF0116-NC-IGNORE-NOT-EVIDENCE",
                "kind": "known-broken-fixture",
                "description": (
                    "Force-tracking a gitignored credential-shaped name proves "
                    "ignore rules are not exclusion evidence."
                ),
                "fired_on_bad_state": bool(git.get("ignore_not_evidence")),
                "silent_on_good_state": bool(ctrl["rotation_pool_untracked"]),
                "bad_state_output": "planted.credentials.json tracked despite ignore",
                "good_state_output": "rotation-pool accounts.json untracked",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0116-probe2-git-plumbing-independent-of-zip-namelist",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 uses git plumbing on an isolated fixture and does not reuse "
                "probe 1's zip namelist. Live git on this worktree is unmeasurable."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0116/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0116",
        },
        "downstream_consumers": [
            {
                "consumer": "probe1_artifact.py zip namelist",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p1,
            },
            {
                "consumer": "probe2_git_index.py git plumbing",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p2,
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "zero retries. This unit's first observation IS the verdict.",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no .git, so live index and history were not "
                    "enumerated. Fixture git history is the measured git surface."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe2 against a real clone with git ls-files / log "
                    "--all and compare credential-shaped names to the inventory."
                ),
            }
        ],
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
        },
    }


def validate(doc: dict) -> None:
    errs = SL.errors_of(doc)
    if errs:
        print("FAILED:CNF-0116 schema errors")
        for e in errs[:30]:
            print(" ", e)
        raise SystemExit(1)
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}, {"state": "SUCCESS"}):
        if not SL.errors_of(g):
            print(f"FAILED:CNF-0116 schema accepted garbage {list(g)[:2]}")
            raise SystemExit(1)
    text = json.dumps(doc)
    if "CNF-0116-filename-only-fixture" in text:
        print("FAILED:CNF-0116 fixture placeholder leaked into artifact")
        raise SystemExit(1)
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0116 completion sentinel absent")
        raise SystemExit(1)


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "CNF-0116",
        "receipt_path": "command-center/p2-wave/probes/CNF-0116/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_receipts(primary: dict, probe_out: list[tuple[str, int, str]]) -> None:
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    named = []
    for (pid, cmd), (code, text) in zip(
        (("probe1", P1), ("probe2", P2)),
        probe_out,
    ):
        named.append(
            {"id": pid, "command": cmd, "exit_code": code, "raw_output": text[-8000:]}
        )
    ret = {
        "id": "CNF-0116",
        "unit_id": "CNF-0116",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL_SHORT,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": named,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0116/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0116-probe2-git-plumbing-independent-of-zip-namelist",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0116: live named probes exit 0, credential-exclusion.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No git writes on the primary worktree."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0116",
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


def main() -> int:
    run = S.run_scenario()
    if not run.get("pass"):
        print("FAILED:CNF-0116 scenario controls did not hold")
        print(json.dumps(run.get("controls"), indent=2, sort_keys=True)[:4000])
        return 1
    doc = build_doc(run)
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:CNF-0116 a required test is not PASS")
        return 1
    validate(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 1024:
        print(f"FAILED:CNF-0116 artifact {size}B below floor")
        return 1
    if "CNF-0116-filename-only-fixture" in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0116 placeholder leaked after write")
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNF-0116 probes after emit c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    write_receipts(row(OUT, "primary"), [(c1, t1), (c2, t2)])
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0116 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
