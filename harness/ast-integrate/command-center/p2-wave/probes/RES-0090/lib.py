"""Pre-published operators + hook oracle + mutation campaign for RES-0090."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARC5 = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0005"
HOOK_REL = "command-center/p2-wave/probes/ARC-0005/stop_hook.py"
OPS_PATH = HERE / "operators.json"
TREES = HERE / "fixtures" / "trees"
IDENTICAL_REPO = TREES / "identical" / "repo"
IDENTICAL_LIVE = TREES / "identical" / "live"
DRIFTED_REPO = TREES / "drifted" / "repo"
DRIFTED_LIVE = TREES / "drifted" / "live"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_operators() -> dict:
    return json.loads(OPS_PATH.read_text(encoding="utf-8"))


def operators_sha256() -> str:
    return sha256_file(OPS_PATH)


def original_hook_source() -> str:
    return (REPO / HOOK_REL).read_text(encoding="utf-8")


def apply_operator(source: str, op: dict) -> str:
    find = op["find"]
    n = source.count(find)
    if n != 1:
        raise ValueError(f"{op['id']}: find matches {n} times, want 1")
    return source.replace(find, op["replace"], 1)


def _load_hook(hook_dir: Path):
    for name in ("stop_hook", "detector", "trees"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        "res0090_stop_hook", hook_dir / "stop_hook.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load stop_hook")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_TREES_STUB = '''"""Minimal trees.py for isolated hook runs (no parents[3] REPO walk)."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
CTRL_LIVE = HERE / "_unused_live"
CTRL_REPO = HERE / "_unused_repo"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def census(repo_root: Path, live_root: Path) -> dict:
    repo = rel_files(repo_root)
    live = rel_files(live_root)
    keys = sorted(set(repo) | set(live))
    rows = []
    identical = repo_larger = live_larger = 0
    for rel in keys:
        rp, lp = repo.get(rel), live.get(rel)
        rec = {"path": rel, "in_repo": rp is not None, "in_live": lp is not None}
        if rp is None:
            rec["direction"] = "live-only"
            live_larger += 1
        elif lp is None:
            rec["direction"] = "repo-only"
            repo_larger += 1
        else:
            rb, lb = rp.read_bytes(), lp.read_bytes()
            if sha256_bytes(rb) == sha256_bytes(lb) and len(rb) == len(lb):
                rec["direction"] = "identical"
                identical += 1
            elif len(rb) > len(lb):
                rec["direction"] = "repo-larger"
                repo_larger += 1
            elif len(lb) > len(rb):
                rec["direction"] = "live-larger"
                live_larger += 1
            else:
                rec["direction"] = "sha-diff-same-size"
        rows.append(rec)
    return {
        "union_files": len(keys),
        "identical": identical,
        "repo_larger": repo_larger,
        "live_larger": live_larger,
        "rows": rows,
    }
'''


def isolate(source: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="res0090-hook-"))
    (tmp / "stop_hook.py").write_text(source, encoding="utf-8", newline="\n")
    shutil.copy(ARC5 / "detector.py", tmp / "detector.py")
    (tmp / "trees.py").write_text(_TREES_STUB, encoding="utf-8")
    return tmp


def _step(mod, repo: Path, live: Path) -> dict:
    result = mod.run(repo, live)
    surface = Path(result["warning_path"])
    return {
        "fired": bool(result.get("fired")),
        "silent": bool(result.get("silent")),
        "warning_present": bool(result.get("warning_present")),
        "surface_exists": surface.is_file(),
        "drifted_count": int(result.get("drifted_count") or 0),
    }


def oracle(source: str) -> dict:
    """Three-step behavioural oracle for the Stop-hook.

    1. identical trees → silent, no warning
    2. drifted trees → fire, warning present
    3. identical again → silent, warning cleared (catches stale-warning mutants)
    """
    hook_dir = isolate(source)
    failures: list[str] = []
    try:
        mod = _load_hook(hook_dir)
        s1 = _step(mod, IDENTICAL_REPO, IDENTICAL_LIVE)
        if s1["fired"] or s1["warning_present"] or s1["surface_exists"]:
            failures.append("identical-1-not-silent")
        s2 = _step(mod, DRIFTED_REPO, DRIFTED_LIVE)
        if (not s2["fired"]) or (not s2["warning_present"]) or (not s2["surface_exists"]):
            failures.append("drifted-not-fired")
        s3 = _step(mod, IDENTICAL_REPO, IDENTICAL_LIVE)
        if s3["fired"] or s3["warning_present"] or s3["surface_exists"]:
            failures.append("identical-2-stale-or-fire")
        passed = not failures
        return {
            "passed": passed,
            "failures": failures,
            "steps": {"identical_1": s1, "drifted": s2, "identical_2": s3},
        }
    finally:
        shutil.rmtree(hook_dir, ignore_errors=True)
        for name in ("stop_hook", "detector", "trees", "res0090_stop_hook"):
            sys.modules.pop(name, None)


def detector(source: str) -> dict:
    """Fires when the hook source violates the oracle (contract broken)."""
    run = oracle(source)
    return {
        "fired": not run["passed"],
        "silent": run["passed"],
        "oracle": run,
    }


def campaign() -> dict:
    ops_hash = operators_sha256()
    doc = load_operators()
    source = original_hook_source()
    target_hash = sha256_bytes(source.encode("utf-8"))
    mutants = []
    for op in doc["operators"]:
        mutant_src = apply_operator(source, op)
        run = oracle(mutant_src)
        killed = not run["passed"]
        mutants.append(
            {
                "id": op["id"],
                "is_control": bool(op.get("is_control")),
                "pit_analogue": op["pit_analogue"],
                "killed": killed,
                "survived": not killed,
                "oracle_failures": run["failures"],
                "oracle_steps": run["steps"],
            }
        )
    total = len(mutants)
    killed_n = sum(1 for m in mutants if m["killed"])
    survived_n = total - killed_n
    control_id = doc["control_operator_id"]
    control = next(m for m in mutants if m["id"] == control_id)
    return {
        "operators_sha256": ops_hash,
        "operators_hashed_before_rates": True,
        "target_path": HOOK_REL,
        "target_sha256": target_hash,
        "control_operator_id": control_id,
        "control_killed": bool(control["killed"]),
        "mutants": mutants,
        "mutants_total": total,
        "killed": killed_n,
        "survived": survived_n,
        "rate": (survived_n / total) if total else 1.0,
    }
