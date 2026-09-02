"""Independent reviewer: run emitted probes from a shell the author did not use."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def reviewer_dash(probe_rels: list[str]) -> dict:
    """Invoke probes from /bin/sh (dash on this box). Author used python3 + bash."""
    sh = "/bin/sh"
    results = []
    silent_pass = False
    for rel in probe_rels:
        path = REPO / rel
        if rel.endswith(".py"):
            cmd = [sh, "-c", 'python3 -B "$1"', "_", str(path)]
        else:
            cmd = [sh, str(path)]
        p = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        if '"status": "PASS"' in text or "status=PASS" in text:
            silent_pass = True
        results.append(
            {
                "probe_path": rel,
                "rc": p.returncode,
                "shell": sh,
                "command": cmd[:3],
                "stdout_tail": text[-800:],
            }
        )
    target = str(Path(sh).resolve()) if Path(sh).exists() else sh
    return {
        "reviewer_id": "BLD-0007-dash-reviewer",
        "independent": True,
        "verdict": "FAIL" if silent_pass else "PASS",
        "scope_not_agreement": True,
        "author_shells": ["python3", "bash"],
        "reviewer_shell": sh,
        "reviewer_shell_target": target,
        "probes_run": results,
        "silent_pass": silent_pass,
        "note": (
            "Ran two emitted probes from POSIX sh (dash on this box). "
            "Author implementation used python3 and bash."
        ),
    }
