"""CI formatter/linter/scanner pin inventory from AUD-0041 YAML extract."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CI_INV = REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"

PIP_EQ = re.compile(
    r"\b(ruff|basedpyright|semgrep|bandit|mypy|black|isort)==([0-9][0-9A-Za-z._-]*)",
    re.I,
)
OPENGREP_URL = re.compile(r"opengrep/releases/download/v([0-9][0-9.]*)/", re.I)
GITLEAKS_URL = re.compile(r"gitleaks/releases/download/v([0-9][0-9.]*)/", re.I)
GITLEAKS_VASSIGN = re.compile(r"\bV=([0-9][0-9.]*)\b.*\bgitleaks\b", re.I | re.S)
GITLEAKS_ENV = re.compile(r"\$\{?GITLEAKS_VERSION\}?")
OSV_ACTION = re.compile(
    r"uses:google/osv-scanner-action/[^\s@]*@([0-9a-f]{8,})", re.I
)
GITLEAKS_ACTION = re.compile(r"uses:gitleaks/gitleaks-action@([0-9a-f]{8,})", re.I)
RUFF_WORD = re.compile(r"\bruff\b", re.I)
OPENGREP_WORD = re.compile(r"\bopengrep\b", re.I)
GITLEAKS_WORD = re.compile(r"\bgitleaks\b", re.I)
OSV_WORD = re.compile(r"\bosv-scanner\b", re.I)


def _ambient(cmd: str) -> dict:
    path = shutil.which(cmd)
    if not path:
        return {"present": False, "which": None, "version": None}
    try:
        proc = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=15
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        ver = text[0] if text else ""
    except (OSError, subprocess.TimeoutExpired):
        ver = ""
    return {"present": True, "which": path, "version": ver or None}


def _walk_steps(doc: dict):
    for wf in doc.get("workflows") or []:
        file = str(wf.get("file") or "")
        for job in wf.get("jobs") or []:
            job_name = str(job.get("name") or job.get("job_id") or "")
            for step in job.get("steps") or []:
                yield {
                    "file": file,
                    "job": job_name,
                    "step": str(step.get("name") or ""),
                    "command": str(step.get("command") or ""),
                }


def collect() -> dict:
    if not CI_INV.is_file():
        raise FileNotFoundError(CI_INV)
    doc = json.loads(CI_INV.read_text(encoding="utf-8"))
    usages: list[dict] = []
    for step in _walk_steps(doc):
        cmd = step["command"]
        loc = {
            "workflow": step["file"],
            "job": step["job"],
            "step": step["step"],
        }
        for m in PIP_EQ.finditer(cmd):
            tool = m.group(1).lower()
            usages.append(
                {
                    **loc,
                    "tool": tool,
                    "kind": "formatter-linter" if tool == "ruff" else "typechecker",
                    "pin": m.group(2),
                    "pin_kind": "pip-exact",
                    "citation": m.group(0),
                }
            )
        og = OPENGREP_URL.search(cmd)
        if og:
            usages.append(
                {
                    **loc,
                    "tool": "opengrep",
                    "kind": "scanner",
                    "pin": og.group(1),
                    "pin_kind": "release-url",
                    "citation": og.group(0),
                }
            )
        elif OPENGREP_WORD.search(cmd) and not cmd.strip().lower().startswith("uses:"):
            usages.append(
                {
                    **loc,
                    "tool": "opengrep",
                    "kind": "scanner",
                    "pin": None,
                    "pin_kind": "unpinned",
                    "citation": "opengrep mentioned without a release URL version",
                }
            )
        gl_v = GITLEAKS_VASSIGN.search(cmd)
        gl_url = GITLEAKS_URL.search(cmd)
        if gl_v:
            usages.append(
                {
                    **loc,
                    "tool": "gitleaks",
                    "kind": "scanner",
                    "pin": gl_v.group(1),
                    "pin_kind": "literal-version-var",
                    "citation": f"V={gl_v.group(1)}",
                }
            )
        elif gl_url:
            usages.append(
                {
                    **loc,
                    "tool": "gitleaks",
                    "kind": "scanner",
                    "pin": gl_url.group(1),
                    "pin_kind": "release-url",
                    "citation": gl_url.group(0),
                }
            )
        elif GITLEAKS_ENV.search(cmd) and GITLEAKS_WORD.search(cmd):
            usages.append(
                {
                    **loc,
                    "tool": "gitleaks",
                    "kind": "scanner",
                    "pin": None,
                    "pin_kind": "unresolved-env",
                    "citation": "${GITLEAKS_VERSION} (value not in extracted inventory)",
                }
            )
        ga = GITLEAKS_ACTION.search(cmd)
        if ga:
            usages.append(
                {
                    **loc,
                    "tool": "gitleaks",
                    "kind": "scanner",
                    "pin": None,
                    "pin_kind": "action-sha-only",
                    "citation": (
                        f"gitleaks-action@{ga.group(1)[:12]} "
                        "(action SHA, not binary version)"
                    ),
                }
            )
        oa = OSV_ACTION.search(cmd)
        if oa:
            usages.append(
                {
                    **loc,
                    "tool": "osv-scanner",
                    "kind": "scanner",
                    "pin": None,
                    "pin_kind": "action-sha-only",
                    "citation": (
                        f"osv-scanner-action@{oa.group(1)[:12]} "
                        "(action SHA, not scanner version)"
                    ),
                }
            )
        elif OSV_WORD.search(cmd):
            usages.append(
                {
                    **loc,
                    "tool": "osv-scanner",
                    "kind": "scanner",
                    "pin": None,
                    "pin_kind": "unpinned",
                    "citation": "osv-scanner mentioned without version",
                }
            )

    missing = [
        u
        for u in usages
        if not u.get("pin")
        and u.get("pin_kind")
        in {"unpinned", "unresolved-env", "action-sha-only", "unpinned-install"}
    ]
    by_tool: dict[str, dict] = {}
    for u in usages:
        t = u["tool"]
        cur = by_tool.get(t)
        if cur is None or (cur.get("pin") is None and u.get("pin")):
            by_tool[t] = dict(u)

    ambient = {
        "ruff": _ambient("ruff"),
        "basedpyright": _ambient("basedpyright"),
        "gitleaks": _ambient("gitleaks"),
        "opengrep": _ambient("opengrep"),
        "osv-scanner": _ambient("osv-scanner"),
    }
    return {
        "source": CI_INV.relative_to(REPO).as_posix(),
        "note": (
            "`.github/workflows` is absent on this Linux worktree. Pins are "
            "read from AUD-0041's extracted quality.yml inventory, which is "
            "the CI pin record present here."
        ),
        "usages": usages,
        "by_tool": by_tool,
        "missing_pins": missing,
        "ambient": ambient,
    }
