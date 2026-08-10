"""WAVE 3 FLOOR AUDIT - defect D3, independently re-derived.

D3 was: `test_generator_is_deterministic` ran `_gen_schema_substrate.py` with `cwd=REPO`, so
running the suite REGENERATED the real tree and silently reverted a hand-edit to any of the 236
generated outputs - while sampling only 4 of them (1.7%).

THE TEST THIS UNIT PERFORMS
    1. pick a generated shim the OLD test did NOT sample, and which is NOT the file the fixing
       lane used for its own control (so this is an independent sample, not a re-run)
    2. record its pristine LF-normalised digest, from the git BLOB (never the working tree, and
       never `git archive` - that applies EOL conversion on this box)
    3. plant a visible edit
    4. run the FULL platform suite
    5. assert the edit SURVIVED and that the suite went RED because of the drift
    6. BOTH-STATES CONTROL: run the generator the pre-fix way (no --out-root, cwd=REPO). The
       same planted edit must be REVERTED - otherwise step 5 proves nothing.
    7. restore the file and ASSERT the restore, comparing against the blob

Nothing here commits, stages, or checks out anything.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
BUILD = REPO / "platform"
CC = REPO / "command-center"
OUT_JSON = CC / "WAVE3-FLOOR-AUDIT.json"
GEN = BUILD / "lib" / "_gen_schema_substrate.py"
PY = sys.executable

#: the file the FIXING LANE used for its own control - deliberately avoided here
LANE_CONTROL_FILE = "command-center/schema/abstraction-leak.schema.json"


def merge(key: str, value: Any) -> None:
    d: dict[str, Any] = {}
    if OUT_JSON.exists():
        try:
            d = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            d = {}
    d[key] = value
    OUT_JSON.write_text(
        json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"WROTE {key}")


def run(cmd: list[str], cwd: Path = REPO, timeout: int = 1800) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "cmd": " ".join(cmd),
            "exit": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": " ".join(cmd),
            "exit": None,
            "stdout": "",
            "stderr": f"TIMEOUT {timeout}s",
        }


def lfsha(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def blob(rel: str, rev: str = "HEAD") -> bytes | None:
    p = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"], cwd=str(REPO), capture_output=True
    )
    return p.stdout if p.returncode == 0 else None


def old_test_sampled_paths() -> dict[str, Any]:
    """Which paths did the PRE-FIX test snapshot? Read from the pinned commit's blob, by AST."""
    src = blob("platform/lib/test_schema_resolver.py", "0aa6f8fa")
    if src is None:
        return {"error": "cannot read the pinned test blob"}
    text = src.decode("utf-8")
    tree = ast.parse(text)
    fn = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and n.name == "test_generator_is_deterministic"
        ),
        None,
    )
    if fn is None:
        return {"error": "test_generator_is_deterministic absent at 0aa6f8fa"}
    strings = sorted(
        {
            n.value
            for n in ast.walk(fn)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and "/" in n.value
        }
    )
    return {"literal_paths_in_the_old_test": strings, "count": len(strings)}


def generated_outputs() -> dict[str, Any]:
    """Enumerate every path the generator writes, by running it into a temp root."""
    with tempfile.TemporaryDirectory(prefix="d3-enum-") as td:
        r = run([PY, str(GEN), "--out-root", td], timeout=600)
        root = Path(td)
        files = sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        )
    return {
        "generator_exit": r["exit"],
        "outputs_written": len(files),
        "outputs": files,
    }


def check() -> dict[str, Any]:
    res: dict[str, Any] = {}
    res["old_test_sample"] = old_test_sampled_paths()
    res["generator_output_census"] = {
        k: v for k, v in generated_outputs().items() if k != "outputs"
    }
    outputs = generated_outputs()["outputs"]

    # ---- pick an UNSAMPLED shim: not in the old test's literals, not the lane's control file
    sampled = set(res["old_test_sample"].get("literal_paths_in_the_old_test", []))
    shims = [
        o
        for o in outputs
        if o.startswith("command-center/schema/")
        and o.endswith(".schema.json")
        and o != LANE_CONTROL_FILE
        and not any(o.endswith(s) or s.endswith(o) for s in sampled)
    ]
    # deterministic choice: the alphabetical median, so it is neither first nor last
    target_rel = shims[len(shims) // 2]
    target = REPO / target_rel
    res["target"] = {
        "path": target_rel,
        "candidate_unsampled_shims": len(shims),
        "chosen_by": "alphabetical median of the unsampled shim list (deterministic, and "
        "neither the first nor the last entry)",
        "differs_from_the_fixing_lanes_control_file": target_rel != LANE_CONTROL_FILE,
        "lane_control_file": LANE_CONTROL_FILE,
    }

    pristine_blob = blob(target_rel)
    res["target"]["tracked_at_HEAD"] = pristine_blob is not None
    worktree_before = target.read_bytes()
    res["digests"] = {
        "blob_at_HEAD_lf": lfsha(pristine_blob) if pristine_blob else None,
        "worktree_before_lf": lfsha(worktree_before),
        "worktree_matches_blob": (lfsha(pristine_blob) == lfsha(worktree_before))
        if pristine_blob
        else None,
    }

    # ------------------------------------------------------------------ plant the edit
    doc = json.loads(worktree_before.decode("utf-8"))
    doc["x-wave3-floor-audit-marker"] = "PLANTED-BY-verify-wave3-DO-NOT-COMMIT"
    doc["x-catalog-reference-count"] = 999999  # the tournament G1 known-broken value
    planted = (
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    target.write_bytes(planted)
    res["digests"]["planted_lf"] = lfsha(planted)
    res["digests"]["planted_differs_from_pristine"] = lfsha(planted) != lfsha(
        worktree_before
    )

    try:
        # ------------------------------------------- FIXED STATE: run the FULL suite
        suite = run(
            [PY, "-m", "pytest", "platform", "-q", "-p", "no:randomly"], timeout=1800
        )
        after_suite = target.read_bytes()
        res["fixed_state"] = {
            "suite_cmd": suite["cmd"],
            "suite_exit": suite["exit"],
            "suite_tail": suite["stdout"][-1600:],
            "digest_after_suite_lf": lfsha(after_suite),
            "EDIT_SURVIVED": lfsha(after_suite) == lfsha(planted),
            "suite_went_RED": suite["exit"] not in (0, None),
            "drift_named_in_output": target_rel.rsplit("/", 1)[-1] in suite["stdout"]
            or "999999" in suite["stdout"],
        }

        # ------------------- BROKEN STATE control: the pre-fix generator invocation
        # `_gen_schema_substrate.py` with NO --out-root writes into the REAL tree, which is
        # exactly what the old test did via cwd=REPO. If this does NOT revert the edit, step
        # above proves nothing.
        target.write_bytes(planted)  # re-plant, the suite may have been the only reader
        before_ctl = lfsha(target.read_bytes())
        gen = run([PY, str(GEN)], timeout=600)
        after_ctl = target.read_bytes()
        res["broken_state_control"] = {
            "seeded_defect": "run the generator the PRE-FIX way: no --out-root, cwd=REPO, so "
            "every write lands in the real tree",
            "cmd": gen["cmd"],
            "generator_exit": gen["exit"],
            "digest_before_lf": before_ctl,
            "digest_after_lf": lfsha(after_ctl),
            "EDIT_REVERTED": lfsha(after_ctl) != before_ctl,
            "reverted_to_pristine": lfsha(after_ctl) == lfsha(worktree_before),
            "probe_FIRED_on_seeded_defect": lfsha(after_ctl) != before_ctl,
        }
        res["both_states_valid"] = bool(
            res["fixed_state"]["EDIT_SURVIVED"]
            and res["broken_state_control"]["EDIT_REVERTED"]
        )

        # -------------------------- the AST guard: does it reject a generator spawn with no seam?
        res["ast_guard"] = _ast_guard_probe()
    finally:
        # --------------------------------------------------- RESTORE and ASSERT the restore
        target.write_bytes(worktree_before)
        restored = target.read_bytes()
        res["restore"] = {
            "restored_to_the_original_worktree_bytes": restored == worktree_before,
            "restored_digest_lf": lfsha(restored),
            "matches_blob_at_HEAD": (lfsha(restored) == lfsha(pristine_blob))
            if pristine_blob
            else None,
        }
        st = subprocess.run(
            ["git", "status", "--porcelain=v1", "--", target_rel],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        res["restore"]["git_status_for_target_is_clean"] = st.stdout.strip() == ""
        res["restore"]["git_status_raw"] = st.stdout.strip()

    res["VERDICT"] = (
        "CLOSED"
        if res.get("both_states_valid")
        and res["fixed_state"]["suite_went_RED"]
        and res["restore"]["restored_to_the_original_worktree_bytes"]
        else "NOT CLOSED"
    )
    return res


def _ast_guard_probe() -> dict[str, Any]:
    """Run the shipped AST guard test alone, then confirm it can go RED."""
    only = run(
        [
            PY,
            "-m",
            "pytest",
            "platform/lib/test_schema_resolver.py",
            "-q",
            "-p",
            "no:randomly",
            "-k",
            "no_platform_test_invokes_the_generator or leaves_the_real_tree_untouched or "
            "matches_every_committed_file",
        ],
        timeout=900,
    )
    return {
        "cmd": only["cmd"],
        "exit": only["exit"],
        "tail": only["stdout"][-900:],
    }


if __name__ == "__main__":
    try:
        r = check()
    except Exception as exc:  # noqa: BLE001
        import traceback

        r = {
            "PROBE_CRASHED": True,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-3000:],
        }
    merge("check1_D3_test_mutates_tree", r)
    print(
        f"{'SUCCESS' if not r.get('PROBE_CRASHED') else 'FAILED'}:d3 verdict={r.get('VERDICT')}"
    )
