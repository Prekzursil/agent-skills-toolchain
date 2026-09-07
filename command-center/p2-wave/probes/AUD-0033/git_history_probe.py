#!/usr/bin/env python3
"""AUD-0033 Probe 2: git log --all on MISSING identities to separate NEVER-EXISTED vs DELETED."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent
PLANTED = "command-center/does-not-exist-AUD0033-typo.json"
MAX_MISSING = 40


def git_log_path(path: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", "log", "--all", "--pretty=format:%H", "-n", "1", "--", path],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "").strip()
        return r.returncode, out
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def prefer_missing(path: str) -> int:
    """Lower sort key = search earlier. Prefer planted + repo-shaped paths."""
    if path == PLANTED:
        return 0
    if path.startswith(("-", "...", "../", "./..")):
        return 50
    if "\\" in path or path.startswith("C:"):
        return 30
    if path.startswith(("command-center/", "tools/", "docs/", "scripts/", ".agents/")):
        return 1
    if path.startswith("./") or path.startswith("."):
        return 10
    return 5


def main() -> int:
    p1 = json.loads((OUT_DIR / "probe1-results.json").read_text(encoding="utf-8"))
    identities = p1.get("identities") or {}
    missing = [k for k, v in identities.items() if v == "MISSING"]
    ordered = sorted(missing, key=prefer_missing)
    searched = ordered[:MAX_MISSING]
    leftover = max(0, len(missing) - len(searched))

    classes = {"NEVER-EXISTED": 0, "DELETED": 0, "ERROR": 0}
    details = []
    for path in searched:
        rc, commit = git_log_path(path)
        if commit:
            klass = "DELETED"
        elif rc in (0, 128):
            # empty history: never existed (rc=128 often means bad pathspec outside tree)
            klass = "NEVER-EXISTED"
        else:
            klass = "ERROR"
        classes[klass] = classes.get(klass, 0) + 1
        details.append({"path": path, "class": klass, "commit": commit or "-", "git_exit": rc})

    planted = next((d for d in details if d["path"] == PLANTED), None)
    planted_ok = bool(planted and planted["class"] == "NEVER-EXISTED")

    result = {
        "unit": "AUD-0033",
        "stage": "linux-local-remeasure",
        "repo": str(REPO),
        "git_worktree": (REPO / ".git").exists() or (REPO / ".git").is_file(),
        "missing_total": len(missing),
        "searched": len(searched),
        "leftover_uncapped": leftover,
        "class_counts": classes,
        "planted_typo": PLANTED,
        "planted_class": planted["class"] if planted else None,
        "planted_ok": planted_ok,
        "details": details,
        "ok": planted_ok,
    }
    (OUT_DIR / "probe2-history-results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "AUD-0033 NAMED PROBE 2: git log --all per MISSING identity",
        f"unit=AUD-0033",
        f"stage=linux-local-remeasure",
        f"repo={REPO}",
        f"git_worktree={result['git_worktree']}",
        f"batch_git_scope=all-max-{MAX_MISSING}",
    ]
    for d in details:
        lines.append(
            f"PATH {d['path']} class={d['class']} commit={d['commit']} git_exit={d['git_exit']}"
        )
    lines.extend(
        [
            f"missing_total={len(missing)}",
            f"searched={len(searched)}",
            f"leftover_uncapped={leftover}",
            f"class_counts={json.dumps(classes)}",
            f"planted_typo={PLANTED}",
            f"planted_class={result['planted_class']}",
            f"planted_ok={planted_ok}",
            f"history_all_searched_in_budget={leftover == 0}",
            "SUCCESS:AUD-0033-probe2" if result["ok"] else "FAILED:AUD-0033-probe2",
        ]
    )
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe2-git-history.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
