#!/usr/bin/env python3
"""Named probe 1: dirty-tree capture is rejected or marked PROVISIONAL.

Both-states: a clean capture is IMMUTABLE; a dirty capture is either refused
or written with status=PROVISIONAL in the record itself. A mutant that stamps
IMMUTABLE on a dirty tree is the detector control.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ANCHOR = REPO / "tools" / "bench" / "sha_anchor"
sys.path.insert(0, str(ANCHOR))

from baseline import (  # noqa: E402
    STATUS_IMMUTABLE,
    STATUS_PROVISIONAL,
    BaselineStore,
    DirtyTreeRejected,
    EmptyInputRefused,
    NoCommitAnchorError,
    capture_baseline,
    mutant_ignore_dirty_status,
    schema_errors,
)
from fixtures import PHASE0_FILES, seed_phase0_repo  # noqa: E402
from gitutil import inspect_repo  # noqa: E402
from metrics import measure_at_sha, measure_worktree  # noqa: E402

UNIT = "TST-0302"
SENTINEL = "SUCCESS:TST-0302"
ART = REPO / "command-center" / "receipts" / "TST-0302.json"
CLI = ANCHOR / "cli.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def run_cli(repo: Path, store: Path, baseline_id: str, accept_dirty: bool) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(CLI),
        "capture",
        "--repo",
        str(repo),
        "--store",
        str(store),
        "--id",
        baseline_id,
    ]
    if accept_dirty:
        cmd.append("--accept-dirty")
    p = subprocess.run(
        cmd, cwd=str(REPO), capture_output=True, text=True, env=env
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("catalog sentinel absent from receipt")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {st}")

    with tempfile.TemporaryDirectory(prefix="tst0302-p1-") as tmp:
        tmp_path = Path(tmp)
        repo = tmp_path / "repo"
        sha = seed_phase0_repo(repo)
        store = BaselineStore(tmp_path / "baselines.jsonl")

        clean = capture_baseline(repo, store, "phase0-clean")
        clean_ok = (
            clean["status"] == STATUS_IMMUTABLE
            and clean["tree_state"] == "clean"
            and clean["dirty"] is False
            and clean["commit_sha"] == sha
            and isinstance(clean.get("environment"), dict)
            and "python_version" in clean["environment"]
            and "platform" in clean["environment"]
            and int(clean["metrics"]["input_cardinality"]) >= 1
            and clean["measure_source"] == "git-cat-file-at-sha"
        )

        (repo / "cases" / "router.json").write_bytes(
            (repo / "cases" / "router.json").read_bytes() + b"DIRTY\n"
        )
        insp = inspect_repo(repo)
        if not insp.dirty:
            return fail("deliberate dirty tree was not dirty")

        rejected = False
        reject_cls = ""
        try:
            capture_baseline(repo, store, "phase0-dirty-default")
        except DirtyTreeRejected as exc:
            rejected = True
            reject_cls = type(exc).__name__

        provisional = capture_baseline(
            repo, store, "phase0-dirty-accepted", accept_dirty=True
        )
        provisional_in_record = (
            provisional.get("status") == STATUS_PROVISIONAL
            and provisional.get("tree_state") == "dirty"
            and provisional.get("dirty") is True
            and provisional.get("commit_sha") == sha
            and isinstance(provisional.get("environment"), dict)
        )
        # The word PROVISIONAL must be the record field, not surrounding prose.
        blob = json.dumps(provisional, sort_keys=True)
        field_not_prose = (
            '"status": "PROVISIONAL"' in blob or '"status":"PROVISIONAL"' in blob
        )

        planted_bad = dict(provisional)
        planted_bad["status"] = STATUS_IMMUTABLE
        planted_errs = schema_errors(planted_bad)
        schema_flags_dirty_immutable = "dirty-must-be-provisional" in planted_errs

        mutant_status = mutant_ignore_dirty_status(True)
        mutant_fires = (
            mutant_status == STATUS_IMMUTABLE
            and provisional["status"] == STATUS_PROVISIONAL
        )

        sha_metrics = measure_at_sha(repo, sha)
        wt_metrics = measure_worktree(repo)
        worktree_diverges = (
            sha_metrics["payload_sha256"] != wt_metrics["payload_sha256"]
            and sha_metrics["measure_source"] == "git-cat-file-at-sha"
            and wt_metrics["measure_source"] == "worktree-walk"
        )

        cli_store = tmp_path / "cli-dirty.jsonl"
        cli_rc, cli_out = run_cli(repo, cli_store, "cli-dirty", accept_dirty=False)
        cli_rejected = cli_rc != 0 and "DirtyTreeRejected" in cli_out

        empty_repo = tmp_path / "empty"
        from gitutil import commit_files, init_repo

        init_repo(empty_repo)
        commit_files(empty_repo, {"README.txt": b"no cases\n"}, "empty")
        empty_refused = False
        try:
            capture_baseline(
                empty_repo, BaselineStore(tmp_path / "empty.jsonl"), "empty-id"
            )
        except EmptyInputRefused:
            empty_refused = True

        this_tree = inspect_repo(REPO)
        no_anchor_here = this_tree.reason == "no-git-anchor" or not this_tree.is_git
        this_refused = False
        try:
            capture_baseline(
                REPO, BaselineStore(tmp_path / "here.jsonl"), "this-worktree"
            )
        except NoCommitAnchorError:
            this_refused = True

        out = {
            "probe": "probe1-dirty-tree",
            "unit_id": UNIT,
            "clean": {
                "status": clean["status"],
                "tree_state": clean["tree_state"],
                "commit_sha": clean["commit_sha"],
                "env_keys": sorted(clean["environment"]),
                "input_cardinality": clean["metrics"]["input_cardinality"],
            },
            "dirty_default_rejected": rejected,
            "reject_class": reject_cls,
            "provisional": {
                "status": provisional["status"],
                "tree_state": provisional["tree_state"],
                "dirty": provisional["dirty"],
                "commit_sha": provisional["commit_sha"],
                "field_in_record": field_not_prose,
            },
            "schema_flags_dirty_immutable": schema_flags_dirty_immutable,
            "mutant_ignore_dirty_status": mutant_status,
            "mutant_fires": mutant_fires,
            "worktree_diverges": worktree_diverges,
            "cli_rejected": cli_rejected,
            "cli_rc": cli_rc,
            "empty_refused": empty_refused,
            "this_worktree_no_git": no_anchor_here,
            "this_worktree_capture_refused": this_refused,
            "pass": bool(
                clean_ok
                and rejected
                and provisional_in_record
                and field_not_prose
                and schema_flags_dirty_immutable
                and mutant_fires
                and worktree_diverges
                and cli_rejected
                and empty_refused
                and this_refused
            ),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"clean={clean['status']} dirty_rejected={rejected} "
            f"provisional={provisional['status']} mutant_fires={mutant_fires} "
            f"wt_div={worktree_diverges} cli_rc={cli_rc}"
        )
        if not out["pass"]:
            print(cli_out[-1500:])
            return fail("dirty-tree contract not proven")
        print("SUCCESS:TST-0302-probe1 dirty capture rejected or PROVISIONAL")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
