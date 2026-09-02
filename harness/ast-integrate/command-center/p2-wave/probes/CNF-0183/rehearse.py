"""Third-party replication rehearsal: completeness first, then isolated run."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import isolate as ISO  # noqa: E402
from package import normalize_stdout, sha256_hex  # noqa: E402

ACCESS = (
    "isolated temp copy of the package only; repo prefix forbidden via "
    "sitecustomize; no receipts, no catalog, no prior conversation"
)

REQUIRED_PKG_KEYS = (
    "id",
    "claim",
    "pins",
    "inputs",
    "command",
    "expected",
    "normalizers",
    "pass_criterion",
)


def load_pkg(pkg_dir: Path) -> dict | None:
    meta = pkg_dir / "package.json"
    if not meta.is_file():
        return None
    try:
        doc = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def missing_elements(pkg_dir: Path) -> list[str]:
    meta = pkg_dir / "package.json"
    if not meta.is_file():
        return ["package.json"]
    try:
        pkg = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["package.json:unparseable"]
    if not isinstance(pkg, dict):
        return ["package.json:not-object"]
    missing: list[str] = []
    for k in REQUIRED_PKG_KEYS:
        val = pkg.get(k)
        if val in (None, "", [], {}):
            missing.append(k)
    for rel in pkg.get("inputs") or []:
        if not isinstance(rel, str) or not (pkg_dir / rel).is_file():
            missing.append(str(rel))
    expected = pkg.get("expected") if isinstance(pkg.get("expected"), dict) else {}
    if "exit_code" not in expected:
        missing.append("expected.exit_code")
    if "stdout_sha256" not in expected:
        missing.append("expected.stdout_sha256")
    cmd = pkg.get("command")
    if isinstance(cmd, list) and len(cmd) >= 2:
        script = cmd[-1]
        if isinstance(script, str) and not script.startswith("-"):
            if not (pkg_dir / script).is_file():
                missing.append(script)
    return missing


def _run_claim(pkg_dir: Path, repo: Path, isolate: bool) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if isolate:
        isolate_dir = pkg_dir / "._isolate"
        ISO.write_sitecustomize(isolate_dir)
        env = ISO.isolation_env(repo, isolate_dir)
    p = subprocess.run(
        [sys.executable, "-B", "run.py"],
        cwd=str(pkg_dir),
        env=env,
        capture_output=True,
        timeout=30,
    )
    stdout = p.stdout or b""
    norm = normalize_stdout(stdout)
    return {
        "exit_code": p.returncode,
        "stdout_sha256": sha256_hex(norm),
        "stderr_tail": (p.stderr or b"")[-400:].decode("utf-8", "replace"),
    }


def rehearse(
    pkg_dir: Path,
    repo: Path,
    *,
    isolate: bool = True,
    skip_completeness: bool = False,
) -> dict:
    """Copy package to a temp dir, then completeness-check, then maybe run.

    skip_completeness is the naive classifier path: any run mismatch becomes
    CLAIM-REFUTED, including missing inputs. That path exists only to prove
    the split is load-bearing.
    """
    tmp = ISO.outside_repo_tmpdir(repo)
    try:
        dest = tmp / "pkg"
        shutil.copytree(
            pkg_dir,
            dest,
            ignore=shutil.ignore_patterns("._isolate", "__pycache__", "*.pyc"),
        )
        pkg = load_pkg(dest)
        pid = (pkg or {}).get("id") or pkg_dir.name
        missing = [] if skip_completeness else missing_elements(dest)
        if missing:
            named = missing[0]
            return {
                "package_id": pid,
                "access": ACCESS,
                "outcome": (
                    f"package structurally incomplete; first missing element "
                    f"named: {named}; claim was not executed"
                ),
                "verdict": "PACKAGE-INCOMPLETE",
                "missing_element": named,
                "missing_all": missing,
                "counter_evidence": None,
                "ran": False,
            }
        run = _run_claim(dest, repo, isolate=isolate)
        expected = (pkg or {}).get("expected") or {}
        want_code = expected.get("exit_code")
        want_sha = expected.get("stdout_sha256")
        got_code = run["exit_code"]
        got_sha = run["stdout_sha256"]
        if got_code == want_code and got_sha == want_sha:
            return {
                "package_id": pid,
                "access": ACCESS,
                "outcome": (
                    f"isolated run exit={got_code} stdout_sha256={got_sha} "
                    f"matched expected"
                ),
                "verdict": "REPRODUCED",
                "missing_element": None,
                "counter_evidence": None,
                "ran": True,
                "observed_exit_code": got_code,
                "observed_stdout_sha256": got_sha,
            }
        counter = (
            f"expected exit={want_code} stdout_sha256={want_sha}; "
            f"observed exit={got_code} stdout_sha256={got_sha}"
        )
        return {
            "package_id": pid,
            "access": ACCESS,
            "outcome": "package complete; observed output diverged from claim",
            "verdict": "CLAIM-REFUTED",
            "missing_element": None,
            "counter_evidence": counter,
            "ran": True,
            "observed_exit_code": got_code,
            "observed_stdout_sha256": got_sha,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def naive_run_only(pkg_dir: Path, repo: Path) -> dict:
    """Wrong classifier: skip completeness, treat any mismatch as CLAIM-REFUTED."""
    rec = rehearse(pkg_dir, repo, isolate=True, skip_completeness=True)
    if rec["verdict"] == "REPRODUCED":
        return rec
    rec = dict(rec)
    rec["verdict"] = "CLAIM-REFUTED"
    rec["counter_evidence"] = rec.get("counter_evidence") or rec.get("outcome")
    rec["missing_element"] = None
    rec["classifier"] = "naive-any-failure-is-refute"
    return rec


def battery(repo: Path) -> dict:
    """Live isolation + three rehearsals + naive incomplete classifier."""
    import package as PKG

    iso = ISO.both_states(repo)
    tmp = ISO.outside_repo_tmpdir(repo)
    try:
        tdir = tmp / "true"
        idir = tmp / "inc"
        fdir = tmp / "false"
        pkg_true = PKG.materialize(tdir, "true")
        pkg_inc = PKG.materialize(idir, "incomplete")
        pkg_false = PKG.materialize(fdir, "false")
        r_true = rehearse(tdir, repo)
        r_inc = rehearse(idir, repo)
        r_false = rehearse(fdir, repo)
        r_naive = naive_run_only(idir, repo)
        split = {
            "incomplete_not_recorded_as_refute": r_inc["verdict"]
            == "PACKAGE-INCOMPLETE",
            "refute_not_recorded_as_incomplete": r_false["verdict"]
            == "CLAIM-REFUTED",
            "naive_classifier_conflates_incomplete_to_refute": r_naive["verdict"]
            == "CLAIM-REFUTED",
            "complete_true_is_reproduced": r_true["verdict"] == "REPRODUCED",
        }
        split["pass"] = all(split.values())
        return {
            "isolation": iso,
            "packages": [pkg_true, pkg_inc, pkg_false],
            "true": r_true,
            "incomplete": r_inc,
            "false": r_false,
            "naive_incomplete": r_naive,
            "verdict_split": split,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
