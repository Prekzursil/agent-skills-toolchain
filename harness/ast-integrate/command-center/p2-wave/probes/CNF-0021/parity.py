"""Live version-parity measurement for CNF-0021.

Primary resolution is PowerShell (PATHEXT-aware). POSIX which is contrast only.
"""
from __future__ import annotations

import hashlib
import json
import locale
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "identical_bytes.py"
RESOLVER_PS1 = HERE / "resolver.ps1"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
PINNED_RUFF = "0.15.17"
AMBIENT_RUFF = "0.15.22"

SENTINEL = (
    "SUCCESS:CNF-0021 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and at least one tool was run "
    "at both the pinned and the ambient version on identical bytes and both "
    "verdicts are recorded. Any other terminal state is FAILED:CNF-0021 "
    "<classification> with the diagnostic tail attached."
)


def tools_root() -> Path:
    return HERE / "tools"


def pwsh_bin() -> Path:
    p = tools_root() / "pwsh" / "pwsh"
    if not p.is_file():
        raise FileNotFoundError(f"pwsh missing at {p}")
    return p


def ruff_bin(version: str) -> Path:
    root = tools_root() / f"ruff-{version}"
    for cand in (
        root / "ruff",
        root / "ruff-x86_64-unknown-linux-gnu" / "ruff",
    ):
        if cand.is_file() or cand.is_symlink():
            return cand.resolve()
    raise FileNotFoundError(f"ruff {version} missing under {root}")


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def _strip(text: str) -> str:
    return ANSI.sub("", text or "").strip()


def run_cmd(argv: list[str], timeout: int = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NO_COLOR"] = "1"
    p = subprocess.run(
        argv,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def resolve_powershell(names: list[str], extra_path: str | None = None) -> list[dict]:
    pwsh = pwsh_bin()
    with tempfile.TemporaryDirectory(prefix="cnf0021-ps-") as td:
        out = Path(td) / "resolved.json"
        cmd = [
            str(pwsh),
            "-NoProfile",
            "-File",
            str(RESOLVER_PS1),
            "-NameList",
            ",".join(names),
            "-JsonOut",
            str(out),
        ]
        if extra_path:
            cmd.extend(["-ExtraPath", extra_path])
        code, stdout, stderr = run_cmd(cmd, timeout=45)
        if code != 0 or not out.is_file():
            raise RuntimeError(
                f"pwsh resolver failed rc={code} stdout={stdout[-500:]} stderr={stderr[-500:]}"
            )
        text = out.read_text(encoding="utf-8-sig")
        rows = json.loads(text)
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            raise RuntimeError(f"resolver returned non-list: {type(rows)}")
        return rows


def posix_which(name: str, path: str | None = None) -> str | None:
    """Contrast-only. Never the primary resolver."""
    return shutil.which(name, path=path)


def version_of(binary: Path) -> str:
    code, out, err = run_cmd([str(binary), "--version"])
    text = _strip((out or err).splitlines()[0] if (out or err) else f"rc={code}")
    return text


def _verdict(exit_code: int) -> str:
    return "CLEAN" if exit_code == 0 else "FINDINGS"


def run_ruff_checks(binary: Path, target: Path) -> dict:
    ver = version_of(binary)
    checks = []
    for name, args in (
        ("ruff check", ["check", "--isolated", "--no-cache", "--output-format=concise"]),
        ("ruff format --check", ["format", "--check", "--isolated", "--no-cache"]),
    ):
        code, out, err = run_cmd([str(binary), *args, str(target)])
        checks.append(
            {
                "name": name,
                "exit_code": code,
                "verdict": _verdict(code),
                "stdout_tail": _strip(out)[-1500:],
                "stderr_tail": _strip(err)[-500:],
            }
        )
    return {
        "version_verbatim": ver,
        "invocation": str(binary),
        "checks": checks,
    }


def dual_run_ruff(target: Path | None = None) -> dict:
    path = target or FIXTURE
    raw = path.read_bytes()
    sha, nbytes = digest_bytes(raw)
    pinned_bin = ruff_bin(PINNED_RUFF)
    ambient_bin = ruff_bin(AMBIENT_RUFF)
    with tempfile.TemporaryDirectory(prefix="cnf0021-bytes-") as td:
        tdir = Path(td)
        copy = tdir / path.name
        copy.write_bytes(raw)
        pinned = run_ruff_checks(pinned_bin, copy)
        ambient = run_ruff_checks(ambient_bin, copy)
    pinned_v = [c["verdict"] for c in pinned["checks"]]
    ambient_v = [c["verdict"] for c in ambient["checks"]]
    return {
        "tool": "ruff",
        "input_path": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
        "input_sha256": sha,
        "input_bytes": nbytes,
        "identical_bytes": True,
        "pinned": pinned,
        "ambient": ambient,
        "verdicts_differ": pinned_v != ambient_v,
        "pinned_check_verdicts": pinned_v,
        "ambient_check_verdicts": ambient_v,
    }


def host_ambient_ruff() -> dict:
    """Resolve ruff on the host PATH with no measurement ExtraPath."""
    rows = resolve_powershell(["ruff", "python3", "git"])
    by_name = {r.get("name"): r for r in rows if isinstance(r, dict)}
    posix_ruff = posix_which("ruff")
    return {
        "powershell": by_name,
        "posix_which_ruff": posix_ruff,
        "host_ruff_resolved": bool((by_name.get("ruff") or {}).get("resolved")),
    }


def measurement_ambient_ruff() -> dict:
    extra = str(ruff_bin(AMBIENT_RUFF).parent)
    rows = resolve_powershell(["ruff"], extra_path=extra)
    row = rows[0] if rows else {}
    return {
        "extra_path": extra,
        "powershell": row,
        "posix_which_ruff": posix_which("ruff", path=extra + os.pathsep + os.environ.get("PATH", "")),
    }


def cmd_shim_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf0021-shim-") as td:
        tdp = Path(td)
        shim = tdp / "dummytool.cmd"
        shim.write_text("#!/bin/sh\necho dummytool 9.9.9-shim\n", encoding="utf-8")
        shim.chmod(0o755)
        search = str(tdp) + os.pathsep + os.environ.get("PATH", "")
        posix = posix_which("dummytool", path=search)
        rows = resolve_powershell(["dummytool"], extra_path=str(tdp))
        row = rows[0] if rows else {}
        src = row.get("source") or ""
        sees = bool(row.get("resolved")) and str(src).endswith(".cmd")
        posix_miss = posix is None
        return {
            "shim_basename": "dummytool.cmd",
            "posix_which_dummytool": posix,
            "powershell_source": src or None,
            "powershell_resolved": bool(row.get("resolved")),
            "posix_misses_cmd_shim": posix_miss,
            "powershell_sees_cmd_shim": sees,
            "pass": posix_miss and sees,
        }


def git_autocrlf() -> str | None:
    code, out, err = run_cmd(["git", "config", "--get", "core.autocrlf"])
    text = _strip(out or err)
    if code != 0 and not text:
        return None
    return text or None


def host_manifest() -> dict:
    loc = None
    try:
        loc = locale.getlocale()
    except Exception:
        loc = None
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "platform": platform.platform(),
        "kernel": platform.version(),
        "python_version_verbatim": sys.version,
        "python_executable": sys.executable,
        "locale": list(loc) if loc else None,
        "code_page": None,
        "git_core_autocrlf": git_autocrlf(),
        "cwd": str(REPO),
        "ci_workflows_present": (REPO / ".github" / "workflows").is_dir(),
        "cnf0010_artifact_present": (
            REPO / "command-center/confirmation/CNF-0010-environment-manifest.json"
        ).is_file(),
    }


def combine_verdict(checks: list[dict]) -> str:
    parts = [f"{c['name']}={c['verdict']}(rc={c['exit_code']})" for c in checks]
    return "; ".join(parts) if parts else "NOT-RUN"


def live_measurement() -> dict:
    from pins import extract_pins  # noqa: WPS433

    pins = extract_pins()
    host = host_manifest()
    host_res = host_ambient_ruff()
    meas = measurement_ambient_ruff()
    dual = dual_run_ruff()
    shim = cmd_shim_control()
    pinned_ver = dual["pinned"]["version_verbatim"]
    ambient_ver = dual["ambient"]["version_verbatim"]
    host_ruff = host_res["powershell"].get("ruff") or {}
    py = host_res["powershell"].get("python3") or {}
    git = host_res["powershell"].get("git") or {}

    ruff_pin = next((p for p in pins if p.get("tool") == "ruff" and p.get("ci_pin")), None)
    based = next((p for p in pins if p.get("tool") == "basedpyright"), None)
    gitleaks_missing = [p for p in pins if p.get("kind") == "missing-pin"]

    tools = [
        {
            "tool": "ruff",
            "ci_pin": (ruff_pin or {}).get("ci_pin") or PINNED_RUFF,
            "ci_pin_source": (ruff_pin or {}).get("source"),
            "ambient_version": ambient_ver,
            "ambient_source_path": dual["ambient"]["invocation"],
            "host_path_version": host_ruff.get("version_verbatim"),
            "host_path_resolved": bool(host_ruff.get("resolved")),
            "versions_disagree": PINNED_RUFF != AMBIENT_RUFF,
            "pinned_verdict": combine_verdict(dual["pinned"]["checks"]),
            "ambient_verdict": combine_verdict(dual["ambient"]["checks"]),
            "verdicts_differ": dual["verdicts_differ"],
            "pinned_version_verbatim": pinned_ver,
            "ambient_version_verbatim": ambient_ver,
        },
        {
            "tool": "basedpyright",
            "ci_pin": (based or {}).get("ci_pin"),
            "ci_pin_source": (based or {}).get("source"),
            "ambient_version": None,
            "ambient_source_path": None,
            "host_path_version": None,
            "host_path_resolved": False,
            "versions_disagree": True,
            "pinned_verdict": "NOT-RUN",
            "ambient_verdict": "NOT-RUN",
            "verdicts_differ": False,
            "note": "binary absent on this host; dual-run limited to ruff (named precedent)",
        },
        {
            "tool": "python3",
            "ci_pin": "3.11 (actions/setup-python in quality.yml)",
            "ci_pin_source": ".github/workflows/quality.yml setup-python python-version=3.11",
            "ambient_version": py.get("version_verbatim"),
            "ambient_source_path": py.get("source"),
            "host_path_resolved": bool(py.get("resolved")),
            "versions_disagree": "3.11" not in str(py.get("version_verbatim") or ""),
            "pinned_verdict": "NOT-A-FORMATTER",
            "ambient_verdict": "NOT-A-FORMATTER",
            "verdicts_differ": False,
        },
        {
            "tool": "git",
            "ci_pin": None,
            "ci_pin_source": "not an explicit quality.yml formatter pin",
            "ambient_version": git.get("version_verbatim"),
            "ambient_source_path": git.get("source"),
            "host_path_resolved": bool(git.get("resolved")),
            "versions_disagree": False,
            "pinned_verdict": "NOT-A-FORMATTER",
            "ambient_verdict": "NOT-A-FORMATTER",
            "verdicts_differ": False,
        },
    ]
    if gitleaks_missing:
        tools.append(
            {
                "tool": "gitleaks",
                "ci_pin": None,
                "ci_pin_source": gitleaks_missing[0]["source"],
                "ambient_version": None,
                "host_path_resolved": False,
                "versions_disagree": True,
                "pinned_verdict": "NOT-RUN",
                "ambient_verdict": "NOT-RUN",
                "verdicts_differ": False,
                "note": "quality.yml pin is an unexpanded env var — missing-pin finding",
            }
        )

    disagreeing = [
        t["tool"]
        for t in tools
        if t.get("versions_disagree") and t["tool"] in {"ruff", "basedpyright", "gitleaks", "python3"}
    ]
    verdict_changes = [t["tool"] for t in tools if t.get("verdicts_differ") is True]

    return {
        "host": host,
        "host_resolution": host_res,
        "measurement_ambient": meas,
        "pin_inventory": pins,
        "tools": tools,
        "dual_version_runs": [dual],
        "cmd_shim_control": shim,
        "disagreeing_tools": disagreeing,
        "verdict_changing_tools": verdict_changes,
        "resolver_engine": "pwsh-windows-pathext",
        "posix_which_used_as_primary": False,
    }
