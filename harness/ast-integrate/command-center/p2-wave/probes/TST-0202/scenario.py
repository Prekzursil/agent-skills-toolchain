"""Junction/symlink fixtures and live matrix for TST-0202.

On this Linux worktree an NTFS junction is unavailable; a directory symlink
is the POSIX analog (same-volume name that resolves to a longer real path).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import artifact_writer as aw  # noqa: E402

PAYLOAD = b"TST-0202-payload\n"


def independent_resolve(path: Path | str) -> str:
    """Signal (b): GNU coreutils readlink -f, not pathlib.Path.resolve."""
    proc = subprocess.run(
        ["readlink", "-f", "--", os.fspath(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"readlink -f failed rc={proc.returncode} err={proc.stderr!r}"
        )
    return (proc.stdout or "").strip()


def bash_resolve(path: Path | str) -> str:
    """Second-shell resolution (Git Bash analog on Linux: /bin/bash)."""
    proc = subprocess.run(
        ["/bin/bash", "-c", 'readlink -f -- "$1"', "bash", os.fspath(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"bash readlink -f failed rc={proc.returncode} err={proc.stderr!r}"
        )
    return (proc.stdout or "").strip()


def _grow_real(root: Path, filename: str, min_resolved: int) -> Path:
    real = root / "real"
    real.mkdir(parents=True, exist_ok=True)
    n = 0
    cursor = real
    while True:
        n += 1
        cursor = cursor / ("seg%02d" % n + "x" * 24)
        cursor.mkdir(parents=True, exist_ok=True)
        candidate = cursor / filename
        if len(os.fspath(candidate.resolve())) > min_resolved:
            return candidate
        if n > 80:
            raise RuntimeError(
                f"could not grow resolved path past {min_resolved}; "
                f"last={len(os.fspath(candidate.resolve()))}"
            )


def _direct_of_length(filename: str, target_len: int) -> tuple[Path, Path]:
    """Return (dest, scratch_root) whose resolved dest length equals target_len.

    Scratch lives under /tmp with a short prefix so in-budget lengths (far
    shorter than the fixture root) can still be matched. Nested 32-char
    components stay under NAME_MAX.
    """
    scratch = Path(tempfile.mkdtemp(prefix="d", dir="/tmp"))
    want_parent = target_len - 1 - len(filename)
    cursor = scratch.resolve()
    n = 0
    while len(os.fspath(cursor)) < want_parent:
        remaining = want_parent - len(os.fspath(cursor))
        if remaining == 1:
            break
        seglen = min(32, remaining - 1)
        n += 1
        name = ("n%02d" % n) + ("z" * 32)
        name = name[:seglen]
        cursor = cursor / name
        cursor.mkdir(parents=True, exist_ok=True)
    dest = cursor / filename
    got = len(os.fspath(dest.resolve()))
    if got == target_len - 1:
        dest = cursor / (filename + "x")
        got = len(os.fspath(dest.resolve()))
    if got != target_len:
        raise RuntimeError(
            f"direct length mismatch want={target_len} got={got} "
            f"parent={cursor} scratch={scratch}"
        )
    return dest, scratch


def build_over_budget_junction(
    root: Path, *, budget: int = aw.WINDOWS_MAX_PATH, filename: str = "payload.bin"
) -> dict[str, Any]:
    """Short alias -> long real dir. Alias length < budget < resolved length."""
    over = _grow_real(root, filename, budget)
    real_dir = over.parent
    alias_dir = root / "j"
    if alias_dir.exists() or alias_dir.is_symlink():
        alias_dir.unlink()
    os.symlink(os.fspath(real_dir), os.fspath(alias_dir), target_is_directory=True)
    alias_file = alias_dir / filename
    resolved = alias_file.resolve()
    alias_len = aw.alias_length(alias_file)
    resolved_len = len(os.fspath(resolved))
    if alias_len > budget:
        raise RuntimeError(
            f"alias is not short enough for the negative control: "
            f"alias_len={alias_len} budget={budget}"
        )
    if resolved_len <= budget:
        raise RuntimeError(
            f"resolved path is not over budget: {resolved_len} <= {budget}"
        )
    direct, direct_scratch = _direct_of_length(filename, resolved_len)
    return {
        "root": os.fspath(root),
        "budget": budget,
        "filename": filename,
        "alias_path": os.fspath(alias_file),
        "resolved_path": os.fspath(resolved),
        "direct_path": os.fspath(direct),
        "direct_scratch": os.fspath(direct_scratch),
        "alias_length": alias_len,
        "resolved_length": resolved_len,
        "direct_resolved_length": len(os.fspath(direct.resolve())),
        "independent_resolved": independent_resolve(alias_file),
        "bash_resolved": bash_resolve(alias_file),
    }


def build_in_budget_junction(
    root: Path, *, budget: int = aw.WINDOWS_MAX_PATH, filename: str = "in.txt"
) -> dict[str, Any]:
    real = root / "in-real"
    real.mkdir(parents=True, exist_ok=True)
    alias_dir = root / "in-j"
    if alias_dir.exists() or alias_dir.is_symlink():
        alias_dir.unlink()
    os.symlink(os.fspath(real), os.fspath(alias_dir), target_is_directory=True)
    alias_file = alias_dir / filename
    resolved_len = len(os.fspath(alias_file.resolve()))
    if resolved_len > budget:
        raise RuntimeError(f"in-budget fixture resolved too long: {resolved_len}")
    direct, direct_scratch = _direct_of_length(filename, resolved_len)
    return {
        "alias_path": os.fspath(alias_file),
        "resolved_path": os.fspath(alias_file.resolve()),
        "direct_path": os.fspath(direct),
        "direct_scratch": os.fspath(direct_scratch),
        "alias_length": aw.alias_length(alias_file),
        "resolved_length": resolved_len,
        "budget": budget,
    }


def _try_write(fn, path: str, data: bytes, budget: int) -> dict[str, Any]:
    try:
        row = fn(path, data, budget=budget)
        row["raised"] = False
        row["error_name"] = None
        return row
    except aw.PathBudgetExceeded as exc:
        out = dict(exc.check)
        out["raised"] = True
        out["error_name"] = type(exc).__name__
        return out


def run_both_states(root: Path | None = None) -> dict[str, Any]:
    own = root is None
    tmp = Path(root) if root else Path(tempfile.mkdtemp(prefix="tst0202-both-"))
    extra_scratches: list[str] = []
    try:
        over = build_over_budget_junction(tmp / "over")
        extra_scratches.append(over["direct_scratch"])
        under = build_in_budget_junction(tmp / "under")
        extra_scratches.append(under["direct_scratch"])
        budget = over["budget"]
        j_over = _try_write(aw.write_artifact, over["alias_path"], PAYLOAD, budget)
        d_over = _try_write(aw.write_artifact, over["direct_path"], PAYLOAD, budget)
        j_under = _try_write(aw.write_artifact, under["alias_path"], PAYLOAD, budget)
        d_under = _try_write(aw.write_artifact, under["direct_path"], PAYLOAD, budget)
        j_over_exists = Path(over["resolved_path"]).is_file()
        d_over_exists = Path(over["direct_path"]).is_file()
        identical_over = (
            j_over["raised"] is True
            and d_over["raised"] is True
            and j_over["measured_length"] == d_over["measured_length"]
            and j_over["measured_length"] == over["resolved_length"]
            and not j_over_exists
            and not d_over_exists
        )
        identical_under = (
            j_under["raised"] is False
            and d_under["raised"] is False
            and j_under["wrote"]
            and d_under["wrote"]
            and Path(under["resolved_path"]).is_file()
            and Path(under["direct_path"]).is_file()
        )
        return {
            "pass": identical_over and identical_under,
            "identical_over_budget": identical_over,
            "identical_in_budget": identical_under,
            "over": over,
            "under": under,
            "junction_over": j_over,
            "direct_over": d_over,
            "junction_under": j_under,
            "direct_under": d_under,
            "junction_over_residue": j_over_exists,
            "direct_over_residue": d_over_exists,
        }
    finally:
        if own:
            shutil.rmtree(tmp, ignore_errors=True)
        for extra in extra_scratches:
            shutil.rmtree(extra, ignore_errors=True)


def run_negative_alias(root: Path | None = None) -> dict[str, Any]:
    own = root is None
    tmp = Path(root) if root else Path(tempfile.mkdtemp(prefix="tst0202-neg-"))
    extra_scratches: list[str] = []
    try:
        over = build_over_budget_junction(tmp / "over")
        extra_scratches.append(over["direct_scratch"])
        budget = over["budget"]
        # Production first: must refuse and leave zero bytes. Residue is
        # recorded on the exception *before* the defect writer runs.
        prod = _try_write(aw.write_artifact, over["alias_path"], PAYLOAD, budget)
        prod_residue_before_defect = Path(over["resolved_path"]).is_file()
        defect = _try_write(
            aw.write_measuring_alias, over["alias_path"], PAYLOAD, budget
        )
        indep = independent_resolve(over["alias_path"])
        bash = bash_resolve(over["alias_path"])
        writer_len = int(prod["measured_length"])
        indep_len = len(indep)
        bash_len = len(bash)
        lengths_agree = (
            writer_len == indep_len == bash_len == over["resolved_length"]
        )
        alias_admits = (
            defect["raised"] is False
            and defect["wrote"] is True
            and Path(over["resolved_path"]).is_file()
            and defect["measured_length"] == over["alias_length"]
            and defect["measured_length"] <= budget
            and over["resolved_length"] > budget
        )
        production_refused = (
            prod["raised"] is True
            and prod["error_name"] == "PathBudgetExceeded"
            and int(prod.get("residue_bytes") or 0) == 0
            and prod_residue_before_defect is False
        )
        return {
            "pass": bool(
                alias_admits
                and production_refused
                and lengths_agree
                and indep == over["resolved_path"]
                and bash == over["resolved_path"]
            ),
            "alias_admits_over_limit_write": alias_admits,
            "production_refused": production_refused,
            "lengths_agree": lengths_agree,
            "writer_measured_length": writer_len,
            "independent_readlink_f": indep,
            "independent_length": indep_len,
            "bash_resolved": bash,
            "bash_length": bash_len,
            "over": over,
            "production": prod,
            "defect": defect,
        }
    finally:
        if own:
            shutil.rmtree(tmp, ignore_errors=True)
        for extra in extra_scratches:
            shutil.rmtree(extra, ignore_errors=True)
