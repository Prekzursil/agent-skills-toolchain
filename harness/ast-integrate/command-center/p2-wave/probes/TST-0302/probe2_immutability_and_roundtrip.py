#!/usr/bin/env python3
"""Named probe 2: immutability + SHA rematerialization within the B03 floor.

Mechanically different from probe 1: does not use DirtyTreeRejected as the
pass predicate. Rebuilds payload_sha256 from git cat-file independently of
bench.metrics, refuses a second write of the same id, and requires a worktree
mutation to leave SHA rematerialization inside the floor while a worktree
walk falls outside it.
"""
from __future__ import annotations

import ast
import hashlib
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
    KIND,
    REQUIRED,
    STATUS_IMMUTABLE,
    BaselineImmutableError,
    BaselineStore,
    capture_baseline,
    rematerialize_from_sha,
    schema_errors,
    unsafe_overwrite,
)
from fixtures import MUTATED_ROUTER, PHASE0_FILES, seed_phase0_repo  # noqa: E402
from gitutil import cat_file_p, ls_tree_paths  # noqa: E402
from metrics import measure_worktree, numeric_metrics  # noqa: E402
from variance import B03_VARIANCE_FLOOR, within_floor  # noqa: E402

UNIT = "TST-0302"
SENTINEL = "SUCCESS:TST-0302"
ART = REPO / "command-center" / "receipts" / "TST-0302.json"
CLI = ANCHOR / "cli.py"
BASELINE_PY = ANCHOR / "baseline.py"

# Duplicated on purpose: independent of bench.baseline.REQUIRED.
PROBE2_REQUIRED = (
    "kind",
    "baseline_id",
    "commit_sha",
    "tree_state",
    "status",
    "dirty",
    "environment",
    "metrics",
    "variance_floor",
    "captured_at",
    "measure_source",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def independent_payload_sha(repo: Path, sha: str) -> tuple[str, int, int]:
    """cat-file digest; must not import bench.metrics hashing helpers."""
    h = hashlib.sha256()
    total = 0
    n = 0
    for rel in sorted(p for p in ls_tree_paths(repo, sha) if p.startswith("cases/")):
        blob = cat_file_p(repo, f"{sha}:{rel}")
        n += 1
        total += len(blob)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(blob)
        h.update(b"\n")
    return h.hexdigest(), total, n


def independent_schema_errors(obj: object) -> list[str]:
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["not-object"]
    for key in PROBE2_REQUIRED:
        if key not in obj:
            errs.append(f"missing:{key}")
    if obj.get("kind") != "bench-baseline-v1":
        errs.append("kind")
    sha = obj.get("commit_sha")
    if not isinstance(sha, str) or len(sha) != 40:
        errs.append("commit_sha")
    if obj.get("tree_state") == "dirty" and obj.get("status") != "PROVISIONAL":
        errs.append("dirty-must-be-provisional")
    env = obj.get("environment")
    if not isinstance(env, dict) or "python_version" not in env:
        errs.append("environment")
    return errs


def ast_raises_named(src: str) -> dict:
    tree = ast.parse(src)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            func = node.exc.func
            if isinstance(func, ast.Name):
                names.add(func.id)
    return {
        "DirtyTreeRejected": "DirtyTreeRejected" in names,
        "BaselineImmutableError": "BaselineImmutableError" in names,
        "NoCommitAnchorError": "NoCommitAnchorError" in names,
        "EmptyInputRefused": "EmptyInputRefused" in names,
    }


def run_cli_rematerialize(repo: Path, store: Path, baseline_id: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(CLI),
            "rematerialize",
            "--repo",
            str(repo),
            "--store",
            str(store),
            "--id",
            baseline_id,
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
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

    src = BASELINE_PY.read_text(encoding="utf-8")
    raises = ast_raises_named(src)
    if not all(raises.values()):
        return fail(f"ast raises incomplete {raises}")
    if REQUIRED != PROBE2_REQUIRED:
        # Independent list must cover the live required tuple.
        missing = [k for k in REQUIRED if k not in PROBE2_REQUIRED]
        if missing:
            return fail(f"probe2 required list missed {missing}")

    with tempfile.TemporaryDirectory(prefix="tst0302-p2-") as tmp:
        tmp_path = Path(tmp)
        repo = tmp_path / "repo"
        sha = seed_phase0_repo(repo)
        store_path = tmp_path / "baselines.jsonl"
        store = BaselineStore(store_path)

        first = capture_baseline(repo, store, "phase0")
        second_failed = False
        second_cls = ""
        try:
            capture_baseline(repo, store, "phase0")
        except BaselineImmutableError as exc:
            second_failed = True
            second_cls = type(exc).__name__

        after_first = store_path.read_bytes()
        mutated = dict(first)
        mutated["metrics"] = dict(first["metrics"])
        mutated["metrics"]["router_latency_ms"] = 9999.0
        unsafe_overwrite(store, mutated)
        overwritten = store_path.read_bytes() != after_first
        # Restore the honest ledger so rematerialize uses the original record.
        store_path.write_bytes(after_first)

        rebaseline = capture_baseline(
            repo, store, "phase0-rebaseline", extra={"who": "probe2", "why": "explicit"}
        )
        rebaseline_ok = (
            rebaseline["baseline_id"] == "phase0-rebaseline"
            and rebaseline["status"] == STATUS_IMMUTABLE
            and rebaseline["commit_sha"] == sha
        )

        roundtrip = rematerialize_from_sha(repo, first)
        ind_sha, ind_bytes, ind_n = independent_payload_sha(repo, sha)
        independent_match = (
            ind_sha == first["metrics"]["payload_sha256"]
            and ind_bytes == first["metrics"]["payload_bytes"]
            and ind_n == first["metrics"]["input_cardinality"]
        )
        ind_schema = independent_schema_errors(first)
        live_schema = schema_errors(first)

        (repo / "cases" / "router.json").write_bytes(MUTATED_ROUTER)
        still = rematerialize_from_sha(repo, first)
        wt = measure_worktree(repo)
        wt_cmp = within_floor(
            numeric_metrics(first["metrics"]),
            numeric_metrics(wt),
            B03_VARIANCE_FLOOR,
        )
        sha_holds_after_dirty = still["ok"] is True
        worktree_outside_floor = wt_cmp["ok"] is False

        cli_rc, cli_out = run_cli_rematerialize(repo, store_path, "phase0")

        planted_empty = dict(PHASE0_FILES)
        # Both-states: original nonempty capture succeeded; empty is probe1.
        nonempty = int(first["metrics"]["input_cardinality"]) >= 4

        out = {
            "probe": "probe2-immutability-roundtrip",
            "unit_id": UNIT,
            "commit_sha": sha,
            "second_write_refused": second_failed,
            "second_class": second_cls,
            "unsafe_overwrite_mutated_bytes": overwritten,
            "rebaseline_ok": rebaseline_ok,
            "roundtrip_ok": bool(roundtrip.get("ok")),
            "roundtrip_source": roundtrip.get("measure_source"),
            "independent_payload_match": independent_match,
            "independent_schema_errs": ind_schema,
            "live_schema_errs": live_schema,
            "sha_holds_after_worktree_mutation": sha_holds_after_dirty,
            "worktree_outside_floor": worktree_outside_floor,
            "cli_rc": cli_rc,
            "ast_raises": raises,
            "kind": first.get("kind"),
            "status": first.get("status"),
            "variance_floor_keys": sorted(first.get("variance_floor") or {}),
            "input_cardinality": first["metrics"]["input_cardinality"],
            "pass": bool(
                first["kind"] == KIND
                and second_failed
                and overwritten
                and rebaseline_ok
                and roundtrip.get("ok")
                and independent_match
                and not ind_schema
                and not live_schema
                and sha_holds_after_dirty
                and worktree_outside_floor
                and cli_rc == 0
                and nonempty
                and all(raises.values())
            ),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"immutable={second_failed} overwrite_fires={overwritten} "
            f"roundtrip={roundtrip.get('ok')} ind_match={independent_match} "
            f"sha_after_dirty={sha_holds_after_dirty} "
            f"wt_out={worktree_outside_floor} cli_rc={cli_rc}"
        )
        if not out["pass"]:
            print(cli_out[-1500:])
            return fail("immutability/round-trip contract not proven")
        print("SUCCESS:TST-0302-probe2 second write refused; SHA rematerialize in floor")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
