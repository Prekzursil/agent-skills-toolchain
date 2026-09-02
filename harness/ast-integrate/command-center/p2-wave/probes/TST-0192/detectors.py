"""LF versus CRLF detectors: real bash -n vs Git-Bash igncr analogue.

Signal (a) is a CR byte count (git cat-file -p when the blob exists, otherwise
worktree bytes — never git archive). Signal (b) is real-bash `bash -n` exit
status. Git Bash is modeled as CR-stripped `bash -n` because GNU bash on Linux
has no `igncr` option; MSYS Git Bash enables it by default.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EMITTTED = HERE / "emitted"
GITATTRIBUTES = REPO / ".gitattributes"
REGRESSION_SEED = "windows-shell.md:3 (agent-written CRLF breaks real bash)"

LF_BODY = (
    "#!/usr/bin/env bash\n"
    "if true; then\n"
    "  echo lf-ok\n"
    "fi\n"
)
# `then\\r` is not the then keyword; GNU bash -n rejects it. Git Bash igncr
# (and the strip-CR analogue) accepts the same bytes.
CRLF_BODY = LF_BODY.replace("\n", "\r\n")
BROKEN_BODY = "#!/usr/bin/env bash\nif true; then\n  echo missing-fi\n"


def cr_count(raw: bytes) -> int:
    return raw.count(b"\r")


def real_bash_argv() -> list[str]:
    """Interpreter that will actually run the scripts on this substrate.

    Catalog names `wsl bash -n`. On native Linux that is `/bin/bash` (or
    `bash` on PATH). `wsl` is used only when present.
    """
    wsl = shutil.which("wsl")
    if wsl:
        return [wsl, "bash"]
    bash = shutil.which("bash") or "/bin/bash"
    return [bash]


def interpreters() -> dict[str, Any]:
    argv = real_bash_argv()
    wsl = shutil.which("wsl")
    return {
        "real_bash": argv,
        "git_bash_analogue": "strip-CR then the same bash -n (MSYS igncr model)",
        "wsl_present": bool(wsl),
        "wsl_path": wsl,
        "substrate": "wsl-bash" if wsl else "native-linux-bash",
        "forbidden_detector": "git-bash-as-sole-syntax-check",
        "git_archive_forbidden": True,
    }


def _write_temp(data: bytes, suffix: str = ".sh") -> Path:
    fd, name = tempfile.mkstemp(prefix="tst0192-", suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return Path(name)


def bash_n(path: Path, *, strip_cr: bool = False) -> dict[str, Any]:
    argv = real_bash_argv()
    target = path
    tmp: Path | None = None
    raw = path.read_bytes()
    if strip_cr:
        tmp = _write_temp(raw.replace(b"\r\n", b"\n").replace(b"\r", b""))
        target = tmp
    try:
        p = subprocess.run(
            [*argv, "-n", str(target)],
            capture_output=True,
            timeout=30,
        )
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        return {
            "argv": argv + ["-n", str(target)],
            "strip_cr": strip_cr,
            "exit": int(p.returncode),
            "stderr_tail": err[-400:],
            "cr_in_input": cr_count(raw),
        }
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def real_bash_n(path: Path) -> dict[str, Any]:
    return bash_n(path, strip_cr=False)


def git_bash_n(path: Path) -> dict[str, Any]:
    """Git-Bash analogue: ignore CR, then syntax-check."""
    return bash_n(path, strip_cr=True)


def git_cat_file_bytes(rel: str) -> dict[str, Any]:
    """CRLF count over the committed blob. Never git archive."""
    rel = rel.replace("\\", "/")
    try:
        p = subprocess.run(
            ["git", "cat-file", "-p", f"HEAD:{rel}"],
            cwd=str(REPO),
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "path": rel,
            "ok": False,
            "source": "git-cat-file-unavailable",
            "reason": f"{type(exc).__name__}:{exc}",
            "cr_count": None,
            "bytes": None,
        }
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", errors="replace").strip()[:240]
        return {
            "path": rel,
            "ok": False,
            "source": "git-cat-file-miss",
            "reason": err or f"exit {p.returncode}",
            "cr_count": None,
            "bytes": None,
        }
    blob = p.stdout or b""
    return {
        "path": rel,
        "ok": True,
        "source": "git cat-file -p HEAD:<path>",
        "cr_count": cr_count(blob),
        "bytes": len(blob),
        "used_git_archive": False,
    }


def worktree_cr(path: Path, rel: str) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": rel,
        "ok": True,
        "source": "worktree-bytes",
        "cr_count": cr_count(raw),
        "bytes": len(raw),
        "used_git_archive": False,
    }


def blob_or_worktree_cr(path: Path, rel: str) -> dict[str, Any]:
    blob = git_cat_file_bytes(rel)
    wt = worktree_cr(path, rel)
    return {
        "path": rel,
        "blob": blob,
        "worktree": wt,
        "cr_count_live": blob["cr_count"] if blob.get("ok") else wt["cr_count"],
        "live_source": blob["source"] if blob.get("ok") else wt["source"],
        "used_git_archive": False,
    }


def parse_sh_eol_lf(text: str) -> dict[str, Any]:
    """True when a gitattributes rule pins *.sh to LF."""
    hits: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        pattern, attrs = parts[0], [a.lower() for a in parts[1:]]
        if pattern in {"*.sh", "*.SH"} or pattern.endswith(".sh"):
            joined = " ".join(attrs)
            if "eol=lf" in joined:
                hits.append(raw_line.strip())
    return {
        "has_sh_eol_lf": bool(hits),
        "matching_lines": hits,
        "rule": hits[0] if hits else "",
    }


def gitattributes_status(path: Path | None = None) -> dict[str, Any]:
    path = path or GITATTRIBUTES
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "has_sh_eol_lf": False,
            "rule": "",
            "bytes": 0,
        }
    text = path.read_text(encoding="utf-8")
    parsed = parse_sh_eol_lf(text)
    return {
        "path": rel,
        "present": True,
        "has_sh_eol_lf": parsed["has_sh_eol_lf"],
        "rule": parsed["rule"] or "*.sh text eol=lf",
        "matching_lines": parsed["matching_lines"],
        "bytes": path.stat().st_size,
    }


def both_states() -> dict[str, Any]:
    lf = _write_temp(LF_BODY.encode("ascii"))
    crlf = _write_temp(CRLF_BODY.encode("ascii"))
    broken = _write_temp(BROKEN_BODY.encode("ascii"))
    try:
        lf_real = real_bash_n(lf)
        lf_git = git_bash_n(lf)
        crlf_real = real_bash_n(crlf)
        crlf_git = git_bash_n(crlf)
        broken_real = real_bash_n(broken)
        broken_git = git_bash_n(broken)
    finally:
        for p in (lf, crlf, broken):
            p.unlink(missing_ok=True)

    crlf_real_fails = crlf_real["exit"] != 0
    crlf_git_passes = crlf_git["exit"] == 0
    lf_real_passes = lf_real["exit"] == 0
    lf_git_passes = lf_git["exit"] == 0
    broken_both_fail = broken_real["exit"] != 0 and broken_git["exit"] != 0
    detectors_differ = crlf_real_fails and crlf_git_passes
    return {
        "regression_seed": REGRESSION_SEED,
        "lf_real": lf_real,
        "lf_git": lf_git,
        "crlf_real": crlf_real,
        "crlf_git": crlf_git,
        "broken_real": broken_real,
        "broken_git": broken_git,
        "crlf_real_bash_fails": crlf_real_fails,
        "crlf_git_bash_passes": crlf_git_passes,
        "lf_real_bash_passes": lf_real_passes,
        "lf_git_bash_passes": lf_git_passes,
        "broken_syntax_fails_both": broken_both_fail,
        "detectors_differ": detectors_differ,
        "git_bash_not_vacuous": broken_both_fail,
    }


def inventory_sh() -> list[Path]:
    """This unit owns generated scripts under probes/TST-0192/emitted/ only."""
    EMITTTED.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in EMITTTED.glob("*.sh") if p.is_file())


def receipt_shell_fields(doc: dict[str, Any]) -> dict[str, Any]:
    """Probe-facing fields may live at top-level (legacy) or under report/extensions."""
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    kind = doc.get("report_kind") or report.get("kind")
    ga = doc.get("gitattributes") if isinstance(doc.get("gitattributes"), dict) else None
    if not ga:
        ga = ext.get("gitattributes") if isinstance(ext.get("gitattributes"), dict) else {}
    scripts = doc.get("emitted_scripts")
    if not isinstance(scripts, list):
        scripts = ext.get("emitted_scripts") if isinstance(ext.get("emitted_scripts"), list) else []
    both = doc.get("both_states") if isinstance(doc.get("both_states"), dict) else None
    if not both:
        both = ext.get("both_states") if isinstance(ext.get("both_states"), dict) else {}
    return {
        "kind": kind,
        "gitattributes": ga,
        "emitted_scripts": scripts,
        "both_states": both,
    }


# Import aliases for probe/gate modules (same objects, stable names).
blob_or_worktree_cr = blob_or_worktree_cr
gitattributes_status = gitattributes_status
inventory_sh = inventory_sh
parse_sh_eol_lf = parse_sh_eol_lf
real_bash_n = real_bash_n
