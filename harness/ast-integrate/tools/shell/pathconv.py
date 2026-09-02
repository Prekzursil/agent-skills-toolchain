"""Argument-scoped MSYS/Git-Bash path conversion (IMP-0466).

Production path is MSYS2_ARG_CONV_EXCL around revision-shaped and device
arguments. Never MSYS_NO_PATHCONV globally. The conversion model is the
evidence surface on a Linux worktree that does not host Git Bash.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS_PATH = REPO / "command-center/p2-wave/probes/IMP-0466/fixtures/corpus.json"

FAILURE_GLOBAL_SUPPRESSION = "global-MSYS_NO_PATHCONV"
FAILURE_SILENT_NOOP_CLONE = "silent-noop-clone"
FAILURE_REDIRECT_TRUNCATION = "redirect-truncation"

_MSYS_ROOT = "C:\\msys64"


def _load_corpus() -> list[dict[str, Any]]:
    doc = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return list(doc.get("arguments") or [])


CORPUS = _load_corpus()


def posix_to_win(arg: str) -> str:
    """MSYS-on conversion of one argv token."""
    if arg == "/dev/null":
        return "NUL"
    if arg.startswith("/dev/"):
        return "NUL"
    if len(arg) >= 3 and arg[0] == "/" and arg[1].isalpha() and arg[2] == "/":
        drive = arg[1].upper()
        rest = arg[3:].replace("/", "\\")
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"
    if arg.startswith("/") and not arg.startswith("//"):
        return _MSYS_ROOT + arg.replace("/", "\\")
    return arg


def _shape_of(arg: str) -> str:
    for row in CORPUS:
        if row.get("arg") == arg:
            return str(row.get("shape") or "")
    if arg.startswith("/refs/") or ":" in arg and not arg.startswith("/"):
        return "revision"
    if arg.startswith("/dev/"):
        return "device"
    return "posix-path"


def _excl_prefixes(mode: str) -> tuple[str, ...]:
    if mode == "scoped":
        return ("/refs", "/dev/", "origin/", "HEAD")
    return ()


def convert_arg(arg: str, mode: str) -> str:
    """mode: scoped | global | none (conversion-on)."""
    if mode == "global":
        return arg
    if mode == "scoped":
        for pfx in _excl_prefixes(mode):
            if arg.startswith(pfx):
                return arg
        if _shape_of(arg) in {"revision", "device"}:
            return arg
        return posix_to_win(arg)
    return posix_to_win(arg)


def prepare_subprocess_env(mode: str, base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    env.pop("MSYS_NO_PATHCONV", None)
    env.pop("MSYS2_ARG_CONV_EXCL", None)
    if mode == "global":
        env["MSYS_NO_PATHCONV"] = "1"
        return env
    if mode == "scoped":
        env["MSYS2_ARG_CONV_EXCL"] = "/refs;/dev/;origin/"
        return env
    return env


def _sandbox() -> Path:
    root = Path(tempfile.gettempdir()) / "imp0466-pathconv"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _intended_win_path(posix: str) -> Path:
    win = posix_to_win(posix)
    # Map C:\Users\probe\... onto a sandbox so Linux G-1 never writes C:\.
    rel = win.replace(":", "").replace("\\", "/").lstrip("/")
    return _sandbox() / "intended" / rel


def _unconverted_posix_path(posix: str) -> Path:
    rel = posix.lstrip("/")
    return _sandbox() / "unconverted" / rel


def _write_clone_marker(dest: Path, marker: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / ".imp0466-clone").write_text(marker, encoding="utf-8")


def _redirect(posix: str, mode: str, body: str) -> dict[str, Any]:
    intended = _intended_win_path(posix)
    other = _unconverted_posix_path(posix)
    intended.parent.mkdir(parents=True, exist_ok=True)
    other.parent.mkdir(parents=True, exist_ok=True)
    if intended.is_file():
        intended.write_text("", encoding="utf-8")
    converted = convert_arg(posix, mode) != posix
    if converted:
        intended.write_text(body, encoding="utf-8")
        content = intended.read_text(encoding="utf-8")
        return {
            "ok": content == body,
            "content": content,
            "truncated": False,
            "converted": True,
        }
    other.write_text(body, encoding="utf-8")
    live = intended.read_text(encoding="utf-8") if intended.is_file() else ""
    return {
        "ok": False,
        "content": live,
        "truncated": live == "",
        "converted": False,
    }


def _run_mode(mode: str) -> dict[str, Any]:
    env = prepare_subprocess_env(mode)
    rev = "/refs/heads/main"
    device = "/dev/null"
    posix = "/c/Users/probe/repo"
    redir = "/c/Users/probe/out.txt"
    rev_obs = convert_arg(rev, mode)
    dev_obs = convert_arg(device, mode)
    posix_obs = convert_arg(posix, mode)
    marker = "IMP-0466-CLONE"
    intended = _intended_win_path(posix)
    if intended.exists():
        for child in intended.rglob("*"):
            if child.is_file():
                child.unlink()
    clone_happened = False
    if posix_obs != posix:
        _write_clone_marker(intended, marker)
        clone_happened = True
    redir_row = _redirect(redir, mode, "probe-body\n")
    return {
        "mode": mode,
        "env_clone": {k: env[k] for k in env if k.startswith("MSYS")},
        "global_suppression": "MSYS_NO_PATHCONV" in env,
        "revision_original": rev,
        "revision_observed": rev_obs,
        "revision_unconverted": rev_obs == rev,
        "revision_corrupted": rev_obs != rev,
        "device_original": device,
        "device_observed": dev_obs,
        "device_unconverted": dev_obs == device,
        "device_corrupted": dev_obs != device,
        "posix_original": posix,
        "posix_observed": posix_obs,
        "posix_converted": posix_obs != posix,
        "clone_marker": marker,
        "clone_happened": clone_happened,
        "clone_intended_exists": (intended / ".imp0466-clone").is_file(),
        "silent_noop": (not clone_happened) and posix_obs == posix,
        "redirect_ok": redir_row["ok"],
        "redirect_content": redir_row["content"],
        "redirect_truncated": redir_row["truncated"],
    }


def both_directions_report() -> dict[str, Any]:
    scoped = _run_mode("scoped")
    none = _run_mode("none")
    same = (
        "MSYS_NO_PATHCONV" not in scoped["env_clone"]
        and "MSYS2_ARG_CONV_EXCL" in scoped["env_clone"]
    )
    ok = (
        same
        and scoped["revision_unconverted"]
        and scoped["device_unconverted"]
        and scoped["posix_converted"]
        and scoped["clone_intended_exists"]
        and none["revision_corrupted"]
        and none["device_corrupted"]
        and none["posix_converted"]
    )
    return {
        "pass": ok,
        "same_configuration": same,
        "scoped": scoped,
        "conversion_on": none,
    }


def global_suppression_discrimination_report() -> dict[str, Any]:
    scoped = _run_mode("scoped")
    glob = _run_mode("global")
    disc = (
        scoped["posix_converted"]
        and scoped["clone_happened"]
        and scoped["redirect_ok"]
        and (not glob["posix_converted"])
        and glob["silent_noop"]
        and (not glob["clone_intended_exists"])
        and glob["redirect_truncated"]
        and glob["redirect_content"] == ""
        and glob["global_suppression"]
        and (not scoped["global_suppression"])
    )
    rev_both = scoped["revision_unconverted"] and glob["revision_unconverted"]
    return {
        "pass": disc and rev_both,
        "discriminates": disc,
        "revision_survives_both": rev_both,
        "note": "global MSYS_NO_PATHCONV is a fixture, not the production path",
        "scoped": scoped,
        "global": glob,
    }


def per_argument_shape_matrix(mode: str) -> list[dict[str, Any]]:
    rows = []
    for item in CORPUS:
        arg = str(item["arg"])
        observed = convert_arg(arg, mode)
        rows.append(
            {
                "id": item["id"],
                "arg": arg,
                "shape": item["shape"],
                "mode": mode,
                "observed": observed,
                "converted": observed != arg,
                "msys_would_convert": bool(item.get("msys_would_convert")),
            }
        )
    return rows


def contract_holds() -> dict[str, Any]:
    both = both_directions_report()
    disc = global_suppression_discrimination_report()
    return {
        "pass": bool(both["pass"] and disc["pass"]),
        "both_directions": both["pass"],
        "global_discrimination": disc["pass"],
    }
