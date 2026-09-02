"""Run gitleaks, trufflehog, and the GitHub-docs local engine. Counts only."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from binaries import GITLEAKS_VER, TRUFFLEHOG_VER, gitleaks_bin, trufflehog_bin
from github_patterns import scan_tree as github_scan

HERE = Path(__file__).resolve().parent


def _rel_from_abs(path_s: str, root: Path) -> str | None:
    try:
        p = Path(path_s)
        if p.is_absolute():
            return p.resolve().relative_to(root.resolve()).as_posix()
        return Path(path_s).as_posix()
    except Exception:
        name = Path(path_s).name
        for cand in root.rglob(name):
            return cand.relative_to(root).as_posix()
        return None


def run_gitleaks(root: Path) -> list[dict]:
    exe = gitleaks_bin()
    root = Path(root)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        report = Path(fh.name)
    cmd = [
        str(exe),
        "detect",
        "--source",
        str(root),
        "--no-git",
        "--redact=100",
        "--report-format",
        "json",
        "--report-path",
        str(report),
        "--exit-code",
        "0",
        "--no-banner",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    raw = report.read_text(encoding="utf-8") if report.is_file() else "[]"
    report.unlink(missing_ok=True)
    try:
        data = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        data = []
    if not isinstance(data, list):
        data = []
    hits: list[dict] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        f = item.get("File") or item.get("file") or item.get("Path") or ""
        rel = _rel_from_abs(str(f), root)
        if not rel or rel in seen:
            continue
        seen.add(rel)
        rule = item.get("RuleID") or item.get("RuleId") or item.get("Description") or "gitleaks"
        hits.append({"relpath": rel, "rule_id": str(rule), "scanner": "gitleaks"})
    # Keep stdout/err out of callers; surface rc only if both empty and failed hard
    if proc.returncode not in (0, 1) and not hits and "unknown flag" in (proc.stderr or ""):
        raise RuntimeError(f"gitleaks failed: {(proc.stderr or proc.stdout)[-500:]}")
    return hits


def run_trufflehog(root: Path) -> list[dict]:
    exe = trufflehog_bin()
    root = Path(root)
    cmd = [
        str(exe),
        "filesystem",
        str(root),
        "--json",
        "--no-verification",
        "--no-update",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    hits: list[dict] = []
    seen: set[str] = set()
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        sm = obj.get("SourceMetadata") or obj.get("source_metadata") or {}
        data = sm.get("Data") or sm.get("data") or {}
        fs = data.get("Filesystem") or data.get("filesystem") or {}
        f = fs.get("file") or fs.get("File") or obj.get("file") or ""
        rel = _rel_from_abs(str(f), root) if f else None
        if not rel or rel in seen:
            continue
        seen.add(rel)
        det = obj.get("DetectorName") or obj.get("detectorName") or "trufflehog"
        hits.append({"relpath": rel, "rule_id": str(det), "scanner": "trufflehog"})
    if proc.returncode not in (0, 183) and not hits:
        # 183 is sometimes used for findings; still parse stdout
        err = (proc.stderr or "")[-400:]
        if "unknown" in err.lower() or "parse error" in err.lower():
            raise RuntimeError(f"trufflehog failed rc={proc.returncode}: {err}")
    return hits


def run_github_local(root: Path) -> list[dict]:
    return github_scan(Path(root))


def hit_relpaths(hits: list[dict]) -> set[str]:
    return {h["relpath"] for h in hits if h.get("relpath")}


def scanner_versions() -> dict:
    return {
        "gitleaks": GITLEAKS_VER,
        "trufflehog": TRUFFLEHOG_VER,
        "github_docs_local": "prefix-regex-from-fetched-github-docs",
        "github_hosted_secret_scanning_invoked": False,
    }
