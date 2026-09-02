"""Pinned gitleaks runner. Drops Secret/Match fields before anything is stored."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from helpers import (
    HERE,
    REPO,
    classify,
    fingerprint,
    git_coverage,
    is_self_artifact,
    relpath,
    scope_for,
    strip_secret_fields,
    variable_name_at,
)

GITLEAKS_VERSION = "8.21.2"
GITLEAKS_SHA256 = "5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba"
GITLEAKS_URL = (
    "https://github.com/gitleaks/gitleaks/releases/download/"
    f"v{GITLEAKS_VERSION}/gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
)
BIN = HERE / ".bin" / "gitleaks"
CONFIG = HERE / "gitleaks.toml"


def gitleaks_bin() -> Path:
    if not BIN.is_file():
        raise RuntimeError("gitleaks-binary-missing")
    return BIN


def gitleaks_version() -> str:
    p = subprocess.run(
        [str(gitleaks_bin()), "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (p.stdout or p.stderr or "").strip().splitlines()[0] if (p.stdout or p.stderr) else "unknown"


def run_gitleaks(source: Path) -> list[dict]:
    source = source.resolve()
    with tempfile.TemporaryDirectory(prefix="aud77-gl-") as tmp:
        report = Path(tmp) / "gitleaks.json"
        cmd = [
            str(gitleaks_bin()),
            "detect",
            "--no-git",
            "--source",
            str(source),
            "--redact",
            "--no-banner",
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--exit-code",
            "0",
        ]
        if source == REPO.resolve() and CONFIG.is_file():
            cmd.extend(["--config", str(CONFIG)])
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(source))
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"gitleaks-rc:{proc.returncode}")
        if not report.is_file() or report.stat().st_size == 0:
            raw_hits: list[dict] = []
        else:
            loaded = json.loads(report.read_text(encoding="utf-8") or "[]")
            raw_hits = loaded if isinstance(loaded, list) else []
        findings: list[dict] = []
        for hit in raw_hits:
            safe = strip_secret_fields(hit)
            file_raw = str(safe.get("File") or "")
            if not file_raw:
                continue
            path = Path(file_raw)
            if not path.is_absolute():
                path = source / path
            rel = relpath(path)
            if is_self_artifact(rel):
                continue
            line = int(safe.get("StartLine") or 1)
            rule_id = str(safe.get("RuleID") or "gitleaks-unknown")
            var = variable_name_at(path, line) if path.is_file() else ""
            findings.append(
                {
                    "path": rel,
                    "line": line,
                    "rule_id": rule_id,
                    "detector": "gitleaks",
                    "variable_name": var,
                    "scope": scope_for(rel, var),
                    "classification": classify(rel, var),
                    "fingerprint": fingerprint(rel, line, rule_id, "gitleaks"),
                    "entropy_reported": safe.get("Entropy"),
                    "end_line": int(safe.get("EndLine") or line),
                    "tags": list(safe.get("Tags") or []),
                    "description": str(safe.get("Description") or "")[:120],
                }
            )
        findings.sort(key=lambda r: r["fingerprint"])
        return findings


def scan_repo() -> dict:
    hits = run_gitleaks(REPO)
    cov = git_coverage()
    return {
        "tool": "gitleaks",
        "version": gitleaks_version(),
        "pinned_version": GITLEAKS_VERSION,
        "mode": "--no-git working-tree",
        "history": cov,
        "hit_count": len(hits),
        "findings": hits,
        "fingerprints": [h["fingerprint"] for h in hits],
        "rule_counts": _counts(hits),
        "hit_count": len(hits),
        "pinned_version": GITLEAKS_VERSION,
        "rule_counts": _counts(hits),
    }


def _counts(hits: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for h in hits:
        k = h["rule_id"]
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))

scan_repo = scan_repo
