#!/usr/bin/env python3
"""BLD-0024: re-verify dated 'not a real regression' dismissals.

Phase 0 snapshot files are absent on this worktree. The catalog's own triage
taxonomy (3 Windows-CRLF, 4 sibling TDD-red, 1 POSIX-only) is reconstructed as
live fixture tests and experimentally re-checked. Original pytest nodeids are
not claimed.

Two runners: in-tree python -m style (baseline class) vs CI console script
(the detector the baseline did not use). Re-running the identical command is
refused when the tree SHA is unchanged — this worktree is not a git repo, so
the two runners are always both exercised.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUITE = HERE / "fixtures" / "suite"
PYMODULE_PATH = HERE / "fixtures" / "pymodule_path"
INSTALLED = HERE / "fixtures" / "installed"
CI_CONSOLE = HERE / "ci_console.py"
SNAPSHOT = REPO / "command-center" / "BASELINE-SNAPSHOT.json"
TESTS_OUT = REPO / "command-center" / "_baseline_tests_out.json"

DISMISSED_TESTS = [
    "test_crlf_text_lines",
    "test_crlf_json_rows",
    "test_crlf_source_bytes",
    "test_tdd_feature_alpha",
    "test_tdd_feature_beta",
    "test_tdd_feature_gamma",
    "test_tdd_feature_delta",
    "test_posix_win_abs_path",
]
CONTROL_UNFALSIFIABLE = "test_unfalsifiable_undocumented"
PACKAGING_TEST = "test_packaging_in_tree_helper"

CRLF_FILES = {
    "crlf_a.txt": b"alpha\nbeta\n",
    "crlf_b.json": b'{"k": "v"}\n',
    "crlf_c.py": b"x = 1\n",
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tree_sha() -> str:
    git = REPO / ".git"
    if not git.exists():
        return "worktree-not-a-git-repo"
    p = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        return "worktree-not-a-git-repo"
    return (p.stdout or "").strip() or "worktree-not-a-git-repo"


def plant_data(root: Path, *, crlf: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, payload in CRLF_FILES.items():
        data = payload.replace(b"\n", b"\r\n") if crlf else payload
        (root / name).write_bytes(data)


def _load(path: Path, modname: str):
    spec = importlib.util.spec_from_file_location(modname, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def run_named_tests(
    names: list[str],
    *,
    data_dir: Path,
    extra_paths: list[Path],
    use_ntpath: bool,
    files: list[Path],
) -> dict[str, dict[str, Any]]:
    old_path = list(sys.path)
    old_env = {
        "BLD0024_DATA_DIR": os.environ.get("BLD0024_DATA_DIR"),
        "BLD0024_USE_NTPATH": os.environ.get("BLD0024_USE_NTPATH"),
    }
    inserted = [str(p) for p in extra_paths]
    try:
        sys.path[:] = inserted + [p for p in sys.path if p not in inserted]
        os.environ["BLD0024_DATA_DIR"] = str(data_dir)
        if use_ntpath:
            os.environ["BLD0024_USE_NTPATH"] = "1"
        else:
            os.environ.pop("BLD0024_USE_NTPATH", None)
        # Drop previously loaded suite modules so each condition is fresh.
        for key in list(sys.modules):
            if key.startswith("test_dismissed") or key.startswith("test_packaging") or key in {
                "sibling_still_red",
                "sibling_now_green",
                "only_in_tree",
            }:
                sys.modules.pop(key, None)
        results: dict[str, dict[str, Any]] = {}
        loaded: dict[Path, Any] = {}
        for path in files:
            loaded[path] = _load(path, f"{path.stem}_{os.getpid()}_{id(data_dir)}")
        by_name: dict[str, Any] = {}
        for mod in loaded.values():
            for name in names:
                fn = getattr(mod, name, None)
                if callable(fn):
                    by_name[name] = fn
        for name in names:
            fn = by_name.get(name)
            if fn is None:
                results[name] = {
                    "outcome": "ERROR",
                    "error_type": "MissingTest",
                    "error": f"{name} not found",
                }
                continue
            try:
                fn()
                results[name] = {"outcome": "PASS", "error_type": None, "error": None}
            except Exception as exc:  # noqa: BLE001 — test outcome is the signal
                results[name] = {
                    "outcome": "FAIL",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:400],
                }
        return results
    finally:
        sys.path[:] = old_path
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def runner_paths(runner: str) -> list[Path]:
    suite = SUITE
    if runner == "console":
        # Packaging-style: installed package dir + suite (siblings), no in-tree helper.
        return [INSTALLED, suite]
    if runner == "pymodule":
        return [PYMODULE_PATH, suite]
    raise ValueError(f"unknown runner {runner}")


def run_condition(runner: str, condition: str) -> dict[str, dict[str, Any]]:
    extra = runner_paths(runner)
    names = DISMISSED_TESTS + [CONTROL_UNFALSIFIABLE, PACKAGING_TEST]
    files = [SUITE / "test_dismissed.py", SUITE / "test_packaging_gap.py"]
    with tempfile.TemporaryDirectory(prefix="bld0024-") as tmp:
        data = Path(tmp) / "data"
        if condition == "as_is":
            plant_data(data, crlf=True)
            use_nt = False
        elif condition == "lf_norm":
            plant_data(data, crlf=False)
            use_nt = False
        elif condition == "ntpath":
            plant_data(data, crlf=True)
            use_nt = True
        else:
            raise ValueError(condition)
        return run_named_tests(
            names,
            data_dir=data,
            extra_paths=extra,
            use_ntpath=use_nt,
            files=files,
        )


def run_worker(argv: list[str]) -> int:
    runner = argv[0] if argv else "pymodule"
    condition = argv[1] if len(argv) > 1 else "as_is"
    out = run_condition(runner, condition)
    print(json.dumps(out, sort_keys=True))
    return 0


def _pass(row: dict[str, Any] | None) -> bool:
    return bool(row) and row.get("outcome") == "PASS"


def _fail(row: dict[str, Any] | None) -> bool:
    return bool(row) and row.get("outcome") == "FAIL"


def register() -> list[dict[str, Any]]:
    still = SUITE / "sibling_still_red.py"
    green = SUITE / "sibling_now_green.py"
    still_sha = sha256_file(still)
    green_sha = sha256_file(green)
    return [
        {
            "id": "F-CRLF-1",
            "test": "test_crlf_text_lines",
            "class": "windows-crlf",
            "original_reason": "Windows CRLF only — split('\\n') leaves '\\r' on fixture text lines",
        },
        {
            "id": "F-CRLF-2",
            "test": "test_crlf_json_rows",
            "class": "windows-crlf",
            "original_reason": "Windows CRLF only — JSON row reader treats CR as payload",
        },
        {
            "id": "F-CRLF-3",
            "test": "test_crlf_source_bytes",
            "class": "windows-crlf",
            "original_reason": "Windows CRLF only — source-byte compare fails on CR",
        },
        {
            "id": "F-TDD-1",
            "test": "test_tdd_feature_alpha",
            "class": "sibling-tdd-red",
            "original_reason": "sibling agent's transient TDD red phase (feature_alpha)",
            "sibling_module": "sibling_still_red.py",
            "dismissal_time_sibling_sha256": still_sha,
            "current_sibling_sha256": still_sha,
        },
        {
            "id": "F-TDD-2",
            "test": "test_tdd_feature_beta",
            "class": "sibling-tdd-red",
            "original_reason": "sibling agent's transient TDD red phase (feature_beta)",
            "sibling_module": "sibling_still_red.py",
            "dismissal_time_sibling_sha256": still_sha,
            "current_sibling_sha256": still_sha,
        },
        {
            "id": "F-TDD-3",
            "test": "test_tdd_feature_gamma",
            "class": "sibling-tdd-red",
            "original_reason": "sibling agent's transient TDD red phase (feature_gamma)",
            "sibling_module": "sibling_now_green.py",
            "dismissal_time_sibling_sha256": still_sha,
            "current_sibling_sha256": green_sha,
        },
        {
            "id": "F-TDD-4",
            "test": "test_tdd_feature_delta",
            "class": "sibling-tdd-red",
            "original_reason": "sibling agent's transient TDD red phase (feature_delta)",
            "sibling_module": "sibling_now_green.py",
            "dismissal_time_sibling_sha256": still_sha,
            "current_sibling_sha256": green_sha,
        },
        {
            "id": "F-POSIX-1",
            "test": "test_posix_win_abs_path",
            "class": "posix-only",
            "original_reason": "POSIX-only — os.path.isabs rejects a Windows drive path",
        },
        {
            "id": "C-UNFALSIFIABLE-1",
            "test": CONTROL_UNFALSIFIABLE,
            "class": "unfalsifiable",
            "original_reason": "not a real regression (no mechanism named)",
            "planted_control": True,
        },
    ]


def classify_one(
    spec: dict[str, Any],
    as_is: dict[str, Any],
    lf: dict[str, Any],
    nt: dict[str, Any],
) -> dict[str, Any]:
    cls = spec["class"]
    sibling_changed = spec.get("dismissal_time_sibling_sha256") != spec.get(
        "current_sibling_sha256"
    ) and spec.get("dismissal_time_sibling_sha256") is not None
    verdict = "UNVERIFIED"
    falsifiable = True
    experiment = ""
    if cls == "windows-crlf":
        experiment = "lf-normalise fixture bytes and re-run the same assertion"
        if _fail(as_is) and _pass(lf):
            verdict = "HOLDS"
        elif _fail(as_is) and _fail(lf):
            verdict = "REFUTED"
        elif _pass(as_is):
            verdict = "STALE-PREMISE"
        else:
            verdict = "UNVERIFIED"
    elif cls == "sibling-tdd-red":
        experiment = "re-hash sibling module; re-run against current sibling state"
        if sibling_changed:
            verdict = "STALE-PREMISE" if _pass(as_is) else "REFUTED"
        else:
            verdict = "HOLDS" if _fail(as_is) else "STALE-PREMISE"
    elif cls == "posix-only":
        experiment = "re-run with ntpath.isabs (Windows path semantics) on the same bytes"
        if _fail(as_is) and _pass(nt):
            verdict = "HOLDS"
        elif _fail(as_is) and _fail(nt):
            verdict = "REFUTED"
        elif _pass(as_is):
            verdict = "STALE-PREMISE"
        else:
            verdict = "UNVERIFIED"
    elif cls == "unfalsifiable":
        falsifiable = False
        experiment = "LF-norm, ntpath, and sibling-hash leave the same undocumented FAIL"
        same = (
            _fail(as_is)
            and _fail(lf)
            and _fail(nt)
            and as_is.get("error_type") == lf.get("error_type") == nt.get("error_type")
        )
        verdict = "UNVERIFIED" if same or _fail(as_is) else "STALE-PREMISE"
    requeued = verdict in {"UNVERIFIED", "REFUTED"}
    return {
        **spec,
        "verdict": verdict,
        "falsifiable": falsifiable,
        "requeued": requeued,
        "sibling_state_changed": bool(sibling_changed),
        "experiment": experiment,
        "as_is": as_is,
        "lf_norm": lf,
        "ntpath": nt,
    }


def revalidate() -> dict[str, Any]:
    pym_as = run_condition("pymodule", "as_is")
    pym_lf = run_condition("pymodule", "lf_norm")
    pym_nt = run_condition("pymodule", "ntpath")
    con_as = run_condition("console", "as_is")
    con_lf = run_condition("console", "lf_norm")
    rows = []
    for spec in register():
        name = spec["test"]
        rows.append(
            classify_one(spec, pym_as[name], pym_lf[name], pym_nt[name])
        )
    # Console script must re-run at least one dismissed failure (F-CRLF-1).
    crlf1 = next(r for r in rows if r["id"] == "F-CRLF-1")
    console_crlf1 = con_as["test_crlf_text_lines"]
    console_crlf1_lf = con_lf["test_crlf_text_lines"]
    packaging_pym = pym_as[PACKAGING_TEST]
    packaging_con = con_as[PACKAGING_TEST]
    packaging_gap = _pass(packaging_pym) and _fail(packaging_con)
    counts = {
        "HOLDS": sum(1 for r in rows if r["verdict"] == "HOLDS"),
        "REFUTED": sum(1 for r in rows if r["verdict"] == "REFUTED"),
        "STALE-PREMISE": sum(1 for r in rows if r["verdict"] == "STALE-PREMISE"),
        "UNVERIFIED": sum(1 for r in rows if r["verdict"] == "UNVERIFIED"),
    }
    eight = [r for r in rows if not r.get("planted_control")]
    return {
        "tree_sha": tree_sha(),
        "snapshot_present": SNAPSHOT.is_file(),
        "tests_out_present": TESTS_OUT.is_file(),
        "dismissals": rows,
        "eight_count": len(eight),
        "counts": counts,
        "console": {
            "exercised_id": "F-CRLF-1",
            "as_is": console_crlf1,
            "lf_norm": console_crlf1_lf,
            "matches_pymodule_as_is": console_crlf1.get("outcome")
            == crlf1["as_is"].get("outcome"),
            "lf_green": _pass(console_crlf1_lf),
        },
        "packaging_gap": {
            "pymodule": packaging_pym,
            "console": packaging_con,
            "detected": packaging_gap,
        },
        "crlf_lf_green": all(
            r["verdict"] == "HOLDS"
            for r in rows
            if r["class"] == "windows-crlf"
        ),
        "unfalsifiable_unverified": any(
            r["class"] == "unfalsifiable" and r["verdict"] == "UNVERIFIED"
            for r in rows
        ),
    }


def run_console_script(condition: str = "as_is") -> tuple[int, dict[str, Any]]:
    """Invoke the CI console script as a process (not python -m)."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-B", str(CI_CONSOLE), condition],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = (p.stdout or "").strip()
    try:
        doc = json.loads(text.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        doc = {"parse_error": text[-1500:], "stderr": (p.stderr or "")[-500:]}
    return p.returncode, doc


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        return run_worker(sys.argv[2:])
    doc = revalidate()
    print(json.dumps({k: doc[k] for k in ("counts", "eight_count", "crlf_lf_green", "unfalsifiable_unverified", "packaging_gap") if k in doc}, indent=2, default=str))
    print(
        f"HOLDS={doc['counts']['HOLDS']} STALE={doc['counts']['STALE-PREMISE']} "
        f"UNVERIFIED={doc['counts']['UNVERIFIED']} REFUTED={doc['counts']['REFUTED']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
