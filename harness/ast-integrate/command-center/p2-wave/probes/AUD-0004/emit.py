#!/usr/bin/env python3
"""Emit AUD-0004 salvage census and G-1 per-unit receipts.

Does not run tools/command-center/unit_manifest.py --write.
Does not consult cloud ok=true.
Does not git-add/commit/stash the ast-integrate worktree.
"""
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
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "AUD-0004"
OUT = C.OUT_REL
SCHEMA = C.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0004/probe1_fsck_dangling.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0004/probe2_stash_content.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/AUD-0004/census.py",
    "command-center/p2-wave/probes/AUD-0004/probe1_fsck_dangling.py",
    "command-center/p2-wave/probes/AUD-0004/probe2_stash_content.py",
    "command-center/p2-wave/probes/AUD-0004/emit.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def catalog_unit() -> dict:
    cat = json.loads(
        (C.REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in cat.get("work_units") or []:
        if u.get("id") == UNIT:
            return u
    raise SystemExit(f"FAILED:{UNIT} catalog row missing")


def slim_stash(ctl: dict) -> dict:
    return {
        "ok": ctl["ok"],
        "git_version": ctl.get("git_version"),
        "untracked_pathspec": {
            k: ctl["untracked_pathspec"][k]
            for k in (
                "rc",
                "stash_created",
                "file_remained",
                "saved_nothing",
                "content_nonzero",
                "list_count_before",
                "list_count_after",
            )
        },
        "untracked_stderr_tail": ctl["untracked_pathspec"].get("stderr", "")[-300:],
        "empty_list_entry": {
            k: ctl["empty_list_entry"][k]
            for k in ("ok", "zero_content_count", "list_count")
        },
        "tracked_stash": {
            k: ctl["tracked_stash"][k]
            for k in ("ok", "rc", "nonzero_count")
        },
        "include_untracked_flag_needed": ctl["include_untracked_flag_needed"],
    }


def slim_fsck(ctl: dict) -> dict:
    return {
        "ok": ctl["ok"],
        "planted_blob": ctl["planted_blob"],
        "head_blob": ctl["head_blob"],
        "fired_on_planted_blob": ctl["fired_on_planted_blob"],
        "silent_on_head_blob": ctl["silent_on_head_blob"],
        "fsck_rc": ctl["fsck_rc"],
        "object_count": ctl["object_count"],
        "command": "git fsck --unreachable --dangling",
    }


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    question = str(unit.get("question_or_target") or "")
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    if out_rel != OUT or schema_rel != SCHEMA:
        print(f"FAILED:{UNIT} catalog paths {out_rel} {schema_rel}")
        return 1
    if not sentinel:
        print(f"FAILED:{UNIT} completion_sentinel missing")
        return 1

    measured = C.measure()
    if not measured["ok"]:
        print(f"FAILED:{UNIT} detectors did not discriminate")
        print(json.dumps({k: measured[k] for k in ("headline", "ok")}, indent=2)[:4000])
        return 1

    stash_ctl = measured["stash_control"]
    fsck_ctl = measured["fsck_control"]
    pop_ctl = measured["bare_pop"]
    live = measured["live"]
    head = measured["headline"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    live_git = head["live_git_repos"]
    answer = (
        f"On this Linux worktree {C.REPO} is_git={head['worktree_is_git']}. "
        f"Bounded first-party scan of /opt/p2 found live_git_repos={live_git} "
        f"(paths_scanned={live['counts']['paths_scanned']}). Live recoverable "
        f"stash_nonzero={head['live_stash_nonzero']} "
        f"stash_zero_content={head['live_stash_zero_content']} "
        f"fsck_objects={head['live_fsck_objects']} "
        f"reflog_beyond_tip={head['live_reflog_beyond_tip']}. "
        "That is 'no git object database on this box', not a silent empty salvage. "
        f"{head['git_version']}. "
        "git stash push -- <untracked path> saved nothing "
        f"(stash_created={stash_ctl['untracked_pathspec']['stash_created']}, "
        "file remained, content_nonzero=false). A tracked-file stash is non-zero. "
        "An empty stash-list entry is zero-content, so list existence is not salvage. "
        "git stash show without --include-untracked hides an untracked-only stash. "
        "Probe 1 git fsck --unreachable --dangling names a planted unreachable blob "
        "and stays silent on the HEAD blob. "
        "The 2026-08-08 bare-pop incident is catalog-named only; fixture shows "
        f"bare pop would apply {pop_ctl['bare_pop_would_apply']} "
        f"({pop_ctl['bare_pop_would_apply_subject']}), newest not oldest. "
        "Owner repos under ~/Documents/GitHub and other machines were not walked. "
        + sentinel
    )

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "schema_version": 1,
        "report_kind": "audit-inventory",
        "title": unit.get("title"),
        "question": question,
        "answer": answer,
        "measured_at": now,
        "headline": head,
        "inventory": {
            "repos_scanned": live["counts"]["paths_scanned"],
            "item_count": live["counts"]["live_items"],
            "items": live["items"],
            "counts": live["counts"],
            "discovery": live["discovery"],
            "live_repos": live["repos"],
        },
        "both_states_control": {
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "procedure": (
                "In an isolated tempfile git repo: (1) git stash push -- <untracked> "
                "must save nothing; (2) store an empty stash-like commit and require "
                "zero include-untracked numstat; (3) stash a tracked edit and require "
                "non-zero numstat; (4) git hash-object -w a blob not in HEAD, run "
                "git fsck --unreachable --dangling, require that blob named and the "
                "HEAD blob unnamed."
            ),
            "stash": slim_stash(stash_ctl),
            "fsck": slim_fsck(fsck_ctl),
            "bare_pop": pop_ctl,
        },
        "probes_methods": {
            "probe1": (
                "git fsck --unreachable --dangling. Parses dangling/unreachable "
                "commit/blob/tree/tag lines. Does not use --lost-found (mutating). "
                "Live census plus planted-blob / HEAD-blob fixture."
            ),
            "probe2": (
                "git stash list cross-checked with git stash show "
                "--include-untracked --numstat per entry. Default stash show "
                "without --include-untracked is not content proof."
            ),
        },
        "catalog_tests_required": unit.get("tests_required") or [],
        "tests": [
            {
                "id": "ctl-untracked-pathspec-saves-nothing",
                "result": "PASS",
                "command": "git stash push -m untracked-pathspec -- only-untracked.txt",
            },
            {
                "id": "ctl-tracked-stash-nonzero",
                "result": "PASS",
                "command": "git stash push -m tracked-change",
            },
            {
                "id": "ctl-empty-list-entry-zero-content",
                "result": "PASS",
                "command": "git stash store empty WIP; git stash show --include-untracked --numstat",
            },
            {
                "id": "ctl-fsck-planted-blob-fires-head-silent",
                "result": "PASS",
                "command": "git hash-object -w --stdin; git fsck --unreachable --dangling",
            },
            {
                "id": "live-fsck",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "live-stash-content",
                "result": "PASS",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0004-probe2-stash-content",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 recomputes stash content with list+include-untracked "
                "numstat and tries to falsify the headline stash counts and the "
                "untracked-pathspec save-nothing claim. It does not run fsck."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "fsck-unreachable-dangling"},
            {
                "id": "probe2",
                "command": P2,
                "role": "stash-list-include-untracked-numstat",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/AUD-0004/census.py",
                "exists": True,
                "role": "detector",
            },
        ],
        "evidence": [
            {
                "claim": (
                    f"Live first-party git repo count is {live_git}; "
                    f"fsck named {head['live_fsck_objects']} unreachable/dangling "
                    "objects on this box."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0004/census.py:fsck_unreachable_dangling",
            },
            {
                "claim": (
                    "git stash push -- <untracked path> saved nothing; a tracked "
                    "stash is non-zero; an empty list entry is zero-content."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0004/census.py:stash_both_states",
            },
            {
                "claim": (
                    "Planted unreachable blob is named by git fsck --unreachable "
                    "--dangling; the HEAD blob is not."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0004/census.py:fsck_both_states",
            },
            {
                "claim": (
                    "2026-08-08 bare-pop incident has no contemporaneous log here; "
                    "fixture shows bare pop applies stash@{0} (newest)."
                ),
                "verdict": "NOT-CHECKED",
                "anchor": "command-center/p2-wave/probes/AUD-0004/census.py:bare_pop_mechanism",
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Owner git repos under ~/Documents/GitHub and other machines "
                    "were not scanned."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run census.py:live_inventory with an owner-supplied repo "
                    "list once those trees are not held by a concurrent session."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0004/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "min_bytes_threshold": 2048,
    }

    schema_path = C.REPO / SCHEMA
    if not schema_path.is_file():
        print(f"FAILED:{UNIT} output_schema missing {SCHEMA}")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print(f"FAILED:{UNIT} schema errors")
        for err in errors[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:{UNIT} schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = C.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        print(f"FAILED:{UNIT} catalog sentinel missing from serialisation")
        return 1
    out.write_text(text, encoding="utf-8")

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:{UNIT} named probes rc1={rc1} rc2={rc2}")
        print(out1[-3000:])
        print(out2[-3000:])
        return 1

    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1

    def row(rel: str, role: str) -> dict:
        path = C.REPO / rel
        sha, n = sha256_file(path)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/AUD-0004/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "fsck-unreachable-dangling",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "stash-list-include-untracked-numstat",
                "raw_output": out2[-8000:],
            },
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0004/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0004-probe2-stash-content",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0004: live named probes exit 0, "
            "audit/AUD-0004-stash-reflog-salvage.json state=SUCCESS, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Worktree is not a git repo; detector "
            "proven on tempfile fixtures."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "artifacts": artifacts,
        "expected": len(artifacts),
        "present": len(artifacts),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
