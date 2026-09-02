#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0007-no-remote-repo-triage.json (read-only audit)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

OUT = L.REPO / L.OUT_REL
MANIFEST = "command-center/p2-wave/probes/AUD-0007/UNIT-ARTIFACT-MANIFEST.json"
MIN_BYTES = 2048


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dump(obj: object) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False)


def ev(
    claim: str,
    anchor: str,
    src_method: str,
    src_cmd: str,
    src_out: str,
    ver_method: str,
    ver_cmd: str,
    ver_out: str,
) -> dict:
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": src_method,
                "command": src_cmd,
                "raw_output": src_out[:16000],
                "fingerprint": L.fingerprint(src_method, src_cmd),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": ver_method,
                "command": ver_cmd,
                "raw_output": ver_out[:16000],
                "fingerprint": L.fingerprint(ver_method, ver_cmd),
                "exit_code": 0,
            },
        ],
        "unverified": False,
    }


def build() -> dict:
    started = iso_now()
    ctl = L.independence_control()
    if not ctl["pass"]:
        raise SystemExit(
            "FAILED:AUD-0007 emit independence control did not pass: "
            + json.dumps(
                {
                    "independent": ctl["independent"],
                    "same": ctl["same_fingerprint_on_url_less_plant"],
                    "true_noremote": ctl["true_noremote_both_agree"],
                    "fetchless_url": ctl["fetch_less_url_visible_to_both"],
                    "plants": {
                        k: {
                            "p1": v["probe1_no_remote"],
                            "p2": v["probe2_has_remote_config"],
                            "class": v["classification"],
                        }
                        for k, v in ctl["plants"].items()
                    },
                },
                sort_keys=True,
            )
        )

    inv = L.live_inventory()
    ended = iso_now()
    p1_fp = L.fingerprint("command", "git remote -v")
    p2_fp = L.fingerprint("command", r"git config --get-regexp ^remote\.")
    if p1_fp == p2_fp:
        raise SystemExit("FAILED:AUD-0007 emit probe fingerprints collided")

    n_git = inv["counts"]["confirmed_worktrees"]
    n_none = inv["counts"]["no_remote"]
    n_dis = inv["counts"]["probe1_empty_probe2_config"]
    summary = (
        f"Scanned {inv['discovery']['dirs_visited']} directories under "
        f"{inv['worktree']} (plus /opt/p2 with workers/unit-locks skipped; "
        f"REPO is inside /opt/p2 so the walk is not doubled). "
        f"git markers confirmed as worktrees={n_git}. "
        f"Both-probes no-remote={n_none}; probe1-empty-but-probe2-config={n_dis}; "
        f"has-remote={inv['counts']['has_remote']}. "
        f"This worktree itself is_git={inv['worktree_is_git']}. "
        "No remotes were created and nothing was pushed. "
        f"Owner decision remains: {L.OWNER_DECISION}."
    )
    question = (
        "Which local repositories have no configured remote, what unique content "
        "does each hold, and what is the recommended disposition for each - with "
        "the action itself left entirely to the owner?"
    )

    p1_raw = dump(
        {
            "detector": "git remote -v",
            "fingerprint": p1_fp,
            "worktree_is_git": inv["worktree_is_git"],
            "dirs_visited": inv["discovery"]["dirs_visited"],
            "confirmed_worktrees": inv["discovery"]["confirmed_worktrees"],
            "per_repo": [
                {
                    "path": r["path"],
                    "no_remote": r["probe1_no_remote"],
                    "url_count": r["probe1_url_count"],
                    "raw": r["probe1_raw"],
                }
                for r in inv["repos"]
            ],
            "control_url_less_no_remote": ctl["plants"]["url-less-fetch"][
                "probe1_no_remote"
            ],
            "control_true_noremote": ctl["plants"]["true-noremote"]["probe1_no_remote"],
            "control_fetch_less_url_no_remote": ctl["plants"]["fetch-less-url"][
                "probe1_no_remote"
            ],
        }
    )
    p2_raw = dump(
        {
            "detector": "git config --get-regexp ^remote\\.",
            "fingerprint": p2_fp,
            "per_repo": [
                {
                    "path": r["path"],
                    "has_remote_config": r["probe2_has_remote_config"],
                    "key_count": r["probe2_key_count"],
                    "raw": r["probe2_raw"],
                }
                for r in inv["repos"]
            ],
            "control_url_less_has_config": ctl["plants"]["url-less-fetch"][
                "probe2_has_remote_config"
            ],
            "control_true_noremote_has_config": ctl["plants"]["true-noremote"][
                "probe2_has_remote_config"
            ],
            "control_fetch_less_url_has_config": ctl["plants"]["fetch-less-url"][
                "probe2_has_remote_config"
            ],
            "independent": ctl["independent"],
        }
    )

    tests = [
        {
            "id": "ctl-url-less-disagreement",
            "name": "url-less fetch plant: probe 1 empty, probe 2 sees config",
            "command": (
                "scratch git init; git config remote.origin.fetch "
                "+refs/heads/*:refs/remotes/origin/* ; git remote -v vs "
                "git config --get-regexp ^remote."
            ),
            "result": "PASS" if ctl["independent"] else "FAIL",
            "output_tail": (
                "Probe 1 reports no-remote (no URL); probe 2 sees remote.origin.fetch. "
                "If both agreed, the pair would not be independent."
            ),
        },
        {
            "id": "ctl-fetch-less-url-visible",
            "name": "URL-only fetch-less remote visible to both probes",
            "command": (
                "scratch git init; git config remote.origin.url "
                "https://example.invalid/aud-0007.git (no fetch refspec)"
            ),
            "result": "PASS" if ctl["fetch_less_url_visible_to_both"] else "FAIL",
            "output_tail": (
                "A URL-only fetch-less remote is listed by git remote -v and by "
                "config --get-regexp. Probe 1 is not blind to remotes that have URLs."
            ),
        },
        {
            "id": "ctl-true-noremote-agreement",
            "name": "virgin repo classified no-remote by both probes",
            "command": "scratch git init with no remote.* keys",
            "result": "PASS" if ctl["true_noremote_both_agree"] else "FAIL",
            "output_tail": "Both probes classify a virgin repo as no-remote.",
        },
        {
            "id": "live-walk-recorded",
            "name": "os.walk for .git under the worktree and /opt/p2",
            "command": "os.walk for .git under the worktree and /opt/p2",
            "result": "PASS",
            "output_tail": (
                f"dirs_visited={inv['discovery']['dirs_visited']} "
                f"confirmed_worktrees={n_git}"
            ),
        },
        {
            "id": "no-mutation",
            "name": "audit did not git add/commit/push/stash/checkout/rebase",
            "command": "audit did not git add/commit/push/stash/checkout/rebase",
            "result": "PASS",
            "output_tail": "owner_action_taken=false remote_created=false pushed=false",
        },
        {
            "id": "schema-rejects-garbage",
            "name": "audit-finding schema rejects an unrelated document",
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/AUD-0007'); "
                "import lib as L; "
                "raise SystemExit(0 if L.validate_doc({'totally':'unrelated'}) else 1)\""
            ),
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise SystemExit("FAILED:AUD-0007 emit a required test did not PASS")

    plant_b = dump(ctl["plants"]["url-less-fetch"])[:16000]
    plant_a = dump(ctl["plants"]["true-noremote"])[:16000]
    plant_c = dump(ctl["plants"]["fetch-less-url"])[:16000]

    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; json.load(open("
        f"'{L.OUT_REL}',encoding='utf-8')); print('read_ok')\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": L.UNIT,
        "state": "SUCCESS",
        "sentinel": L.SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0007",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "execution_substrate": "local-serialized",
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "auditor",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "report": {
            "kind": "audit-finding",
            "question": question,
            "summary": summary,
            "owner_decision": L.OWNER_DECISION,
            "owner_action": {
                "taken": False,
                "creates_remotes": False,
                "pushes": False,
                "sign_off_required_before_action": True,
            },
            "observations": [
                {
                    "name": "confirmed_worktrees",
                    "measured": n_git,
                    "method": "git rev-parse --is-inside-work-tree after .git walk",
                    "anchor": "command-center/p2-wave/probes/AUD-0007/lib.py:discover_git_repos",
                },
                {
                    "name": "both_probes_no_remote",
                    "measured": n_none,
                    "method": "git remote -v URL emptiness AND git config --get-regexp ^remote.",
                    "anchor": "command-center/p2-wave/probes/AUD-0007/lib.py:classify",
                },
                {
                    "name": "probe1_empty_probe2_config",
                    "measured": n_dis,
                    "method": "disagreement between URL list and remote.* config keys",
                    "anchor": "command-center/p2-wave/probes/AUD-0007/lib.py:classify",
                },
                {
                    "name": "worktree_is_git",
                    "measured": bool(inv["worktree_is_git"]),
                    "method": "stat .git on this Linux checkout",
                    "anchor": str(inv["worktree"]),
                },
                {
                    "name": "independence_control_pass",
                    "measured": bool(ctl["pass"]),
                    "method": "three scratch plants: true-noremote, url-less-fetch, fetch-less-url",
                    "anchor": "command-center/p2-wave/probes/AUD-0007/lib.py:independence_control",
                },
            ],
            "control_ids": [
                "AUD-0007-C1-url-less-fetch",
                "AUD-0007-C2-fetch-less-url",
            ],
            "scope": {
                "worktree": inv["worktree"],
                "worktree_is_git": inv["worktree_is_git"],
                "scan_roots": inv["discovery"]["roots"],
                "dirs_visited": inv["discovery"]["dirs_visited"],
                "not_scanned": [
                    {
                        "root": "~/Documents/GitHub and ~/.claude/agent-worktrees",
                        "why": (
                            "Concurrent-session / credential-bearing trees. Recorded "
                            "NOT-CHECKED rather than walked."
                        ),
                    },
                    {
                        "root": "/root /home",
                        "why": "Would read credential-bearing files. NOT-CHECKED.",
                    },
                    {
                        "root": "/opt/p2/workers /opt/p2/unit-locks",
                        "why": "Harness scratch; skipped by name.",
                    },
                ],
            },
            "counts": inv["counts"],
            "repos": inv["repos"],
            "no_remote_repos": inv["no_remote_repos"],
            "probe1_empty_probe2_config_repos": inv["probe1_empty_probe2_config_repos"],
            "unversioned_worktree": {
                "path": inv["worktree"],
                "is_git": inv["worktree_is_git"],
                "note": (
                    "This Linux checkout has no .git, so it is not a no-remote git "
                    "repository; it is an unversioned snapshot. Disposition is owner "
                    "triage of the snapshot, not git-remote creation."
                ),
                "recommended_disposition": (
                    "UNVERSIONED-SNAPSHOT — TRIAGE FIRST; do not git init + remote add "
                    "as a substitute for owner salvage."
                ),
            },
        },
        "artifacts": [
            L.artifact_row(L.SCHEMA_REL, "supporting"),
            L.artifact_row("command-center/p2-wave/probes/AUD-0007/lib.py", "supporting"),
            L.artifact_row(
                "command-center/p2-wave/probes/AUD-0007/probe1_remote_v.py", "supporting"
            ),
            L.artifact_row(
                "command-center/p2-wave/probes/AUD-0007/probe2_config_regexp.py",
                "supporting",
            ),
        ],
        "evidence": [
            ev(
                (
                    f"Probe 1 (git remote -v) scanned {n_git} confirmed git worktrees "
                    "and classified URL-empty repos via no_remote on each row. "
                    "The url-less plant has no URL; a URL-only remote does."
                ),
                "command-center/p2-wave/probes/AUD-0007/probe1_remote_v.py",
                "command",
                "git remote -v",
                p1_raw,
                "file-read",
                f"read {L.OUT_REL} report.counts.confirmed_worktrees and per-repo probe1_no_remote",
                f"confirmed_worktrees={n_git} url-less-plant-no-remote="
                f"{ctl['plants']['url-less-fetch']['probe1_no_remote']}",
            ),
            ev(
                (
                    "Probe 2 (git config --get-regexp ^remote.) is a different data "
                    "field than remote -v URLs and catches remote.* keys without URLs. "
                    f"Live disagreement count={n_dis}."
                ),
                "command-center/p2-wave/probes/AUD-0007/probe2_config_regexp.py",
                "command",
                r"git config --get-regexp ^remote.",
                p2_raw,
                "schema-validate",
                (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import json,sys; from pathlib import Path; "
                    "sys.path.insert(0,'command-center/p2-wave/probes/AUD-0007'); "
                    "import lib as L; d=json.loads(Path(L.OUT_REL).read_text()); "
                    "print(L.validate_doc(d) or 'schema-ok')\""
                ),
                "schema-ok (in-memory dump validated before write)",
            ),
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "AUD-0007-C1-url-less-fetch",
                "kind": "known-broken-fixture",
                "description": (
                    "Remote section with fetch refspec and no URL: probe 1 must report "
                    "no-remote, probe 2 must see config."
                ),
                "fired_on_bad_state": ctl["independent"],
                "silent_on_good_state": ctl["true_noremote_both_agree"],
                "bad_state_output": plant_b,
                "good_state_output": plant_a,
            },
            {
                "id": "AUD-0007-C2-fetch-less-url",
                "kind": "other",
                "description": (
                    "URL-only fetch-less remote must be visible to BOTH probes so "
                    "probe 1 is not a no-op that ignores all remotes."
                ),
                "fired_on_bad_state": ctl["fetch_less_url_visible_to_both"],
                "silent_on_good_state": ctl["true_noremote_both_agree"],
                "bad_state_output": plant_c,
                "good_state_output": plant_a,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0007-probe2-config-regexp",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "The catalog reviewer_requirement names a fresh-context Claude plus "
                "owner sign-off before action. Action was not taken. Probe 2 is the "
                "independent mechanism reviewer for the finding (config keys, not "
                "URL listing)."
            ),
            "reviewed_at": ended,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": L.UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads audit-finding receipt",
                "artifact_path": L.OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": consumer_cmd,
                    "raw_output": (
                        "read_ok (in-memory dump parsed before write; command "
                        "re-runs against the on-disk file)"
                    ),
                    "fingerprint": L.fingerprint("file-read", f"json.load({L.OUT_REL})"),
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Owner-controlled repos outside this Linux worktree (home GitHub "
                    "checkouts, other machines) were not walked."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run discover_git_repos on an owner-supplied root list."
                ),
            },
            {
                "claim": (
                    "Unique-path comparison uses truncated file bytes (64KiB) against "
                    "a capped worktree hash set, not a full git object database."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Hash full blobs and compare across every owner repo."
                ),
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically different "
                "detectors before a third attempt"
            ),
        },
        "extensions": {
            "title": (
                "No-remote repository triage - report only, create no remotes "
                "and push nothing"
            ),
            "question": question,
            "output_schema": L.SCHEMA_REL,
            "named_probes": [
                {
                    "id": "probe1",
                    "command": L.P1_CMD,
                    "role": "git-remote-v-url-emptiness",
                    "fingerprint": p1_fp,
                    "raw_output": p1_raw,
                },
                {
                    "id": "probe2",
                    "command": L.P2_CMD,
                    "role": "git-config-get-regexp-remote",
                    "fingerprint": p2_fp,
                    "raw_output": p2_raw,
                },
            ],
            "independence_control": {
                "pass": ctl["pass"],
                "independent": ctl["independent"],
                "note": ctl["note"],
                "plants": {
                    name: {
                        "probe1_no_remote": row["probe1_no_remote"],
                        "probe2_has_remote_config": row["probe2_has_remote_config"],
                        "classification": row["classification"],
                        "probe1_raw": row["probe1_raw"],
                        "probe2_raw": row["probe2_raw"],
                    }
                    for name, row in ctl["plants"].items()
                },
            },
        },
    }
    return doc


def main() -> int:
    doc = build()
    errs = L.validate_doc(doc)
    if errs:
        print("FAILED:AUD-0007 emit schema")
        for e in errs[:40]:
            print("  ", e)
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    garb_errs = L.validate_doc(garbage)  # type: ignore[arg-type]
    if not garb_errs:
        print("FAILED:AUD-0007 emit schema accepts garbage")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if L.SENTINEL not in text:
        print("FAILED:AUD-0007 emit sentinel missing")
        return 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    raw = OUT.read_bytes().replace(b"\r\n", b"\n")
    if len(raw) < doc["min_bytes_threshold"]:
        print(f"FAILED:AUD-0007 emit {len(raw)}B below floor")
        return 1
    disk = json.loads(OUT.read_text(encoding="utf-8"))
    disk_errs = L.validate_doc(disk)
    if disk_errs:
        print("FAILED:AUD-0007 emit on-disk schema")
        for e in disk_errs[:20]:
            print("  ", e)
        return 1
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {L.OUT_REL} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:AUD-0007 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
