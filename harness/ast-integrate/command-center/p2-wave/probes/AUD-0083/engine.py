#!/usr/bin/env python3
"""AUD-0083 script-interpreter engine.

Probe 1: shebang + extension classification, plus the explicit interpreter at
each hook / plugin / CI call site.

Probe 2: what Windows PowerShell 7 would actually launch for a *bare*
invocation. Windows does not read shebang lines. A resolver that reports
SUCCESS for a bare `.sh` path is reading the shebang (or inventing bash from
the extension), not the OS.
"""
from __future__ import annotations

import json
import os
import shlex
import stat
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REPO = REPO

SCRIPT_EXTS = {".sh", ".ps1", ".py", ".mjs"}
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tox",
    ".eggs",
}
WINDOWS_PATHEXT = {
    ".com",
    ".exe",
    ".bat",
    ".cmd",
    ".vbs",
    ".vbe",
    ".js",
    ".jse",
    ".wsf",
    ".wsh",
    ".msc",
}
POWERSHELL_NATIVE_EXT = {".ps1", ".psm1", ".psd1"}
INTERPRETER_NAMES = {
    "bash",
    "sh",
    "dash",
    "zsh",
    "ksh",
    "fish",
    "python",
    "python3",
    "python3.11",
    "python3.12",
    "python3.13",
    "py",
    "node",
    "nodejs",
    "deno",
    "bun",
    "pwsh",
    "powershell",
    "powershell.exe",
    "pwsh.exe",
    "cmd",
    "cmd.exe",
    "ruby",
    "perl",
    "lua",
    "php",
    "dotnet",
    "wsl",
    "wsl.exe",
}
COMMAND_KEYS = {
    "command",
    "cmd",
    "script",
    "run",
    "entry",
    "entrypoint",
    "exec",
    "executable",
    "shell_command",
}
INTERPRETER_KEYS = {"interpreter", "shell", "runtime", "program"}


def posix_rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO).as_posix()
    except ValueError:
        return resolved.as_posix()


def iter_files() -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def read_shebang(path: Path) -> str | None:
    try:
        with path.open("rb") as fh:
            head = fh.read(256)
    except OSError:
        return None
    if not head.startswith(b"#!"):
        return None
    line = head.split(b"\n", 1)[0]
    return line.decode("utf-8", errors="replace").rstrip("\r")


def shebang_interpreter(shebang: str | None) -> str | None:
    if not shebang or not shebang.startswith("#!"):
        return None
    body = shebang[2:].strip()
    if not body:
        return None
    try:
        parts = shlex.split(body, posix=True)
    except ValueError:
        parts = body.split()
    if not parts:
        return None
    if Path(parts[0]).name == "env" and len(parts) >= 2:
        idx = 1
        while idx < len(parts) and parts[idx].startswith("-"):
            idx += 1
        if idx < len(parts):
            return Path(parts[idx]).name
    return Path(parts[0]).name


def looks_like_script_ref(value: str) -> bool:
    token = value.strip().strip("\"'")
    if not token or "\n" in token:
        return False
    first = token.split()[0]
    lowered = first.lower()
    return lowered.endswith((".sh", ".ps1", ".py", ".mjs", ".bash"))


def windows_pwsh7_bare(path: Path | str, *, shebang: str | None = None) -> dict[str, Any]:
    """Bare invocation on Windows pwsh7. The shebang argument is ignored on purpose."""
    del shebang
    ext = Path(str(path)).suffix.lower()
    if ext in POWERSHELL_NATIVE_EXT:
        return {
            "outcome": "SUCCESS",
            "executor": "pwsh",
            "reads_shebang": False,
            "reason": "PowerShell-native script extension; pwsh invokes itself",
        }
    if ext in WINDOWS_PATHEXT:
        return {
            "outcome": "SUCCESS",
            "executor": "CreateProcess/PATHEXT",
            "reads_shebang": False,
            "reason": f"{ext} is in default PATHEXT",
        }
    if ext in {".sh", ".bash", ".zsh", ".ksh", ".csh"}:
        return {
            "outcome": "FAILURE",
            "executor": None,
            "reads_shebang": False,
            "reason": (
                "Windows pwsh7 / CreateProcess does not read shebang; "
                f"{ext} is not PATHEXT and is not PowerShell-native"
            ),
        }
    if ext in {".py", ".mjs", ".pyw"}:
        return {
            "outcome": "FAILURE",
            "executor": None,
            "reads_shebang": False,
            "reason": (
                f"{ext} is not default PATHEXT; a per-machine file association "
                "is not implied by a shebang"
            ),
        }
    return {
        "outcome": "FAILURE",
        "executor": None,
        "reads_shebang": False,
        "reason": f"extension {ext or '<none>'} has no default Windows launcher",
    }


def windows_explicit(interpreter: str, script: Path | str) -> dict[str, Any]:
    name = Path(interpreter.strip().split()[0]).name.lower()
    if name in INTERPRETER_NAMES:
        return {
            "outcome": "SUCCESS",
            "executor": name,
            "reads_shebang": False,
            "reason": f"explicit interpreter {name} launches {Path(str(script)).as_posix()}",
        }
    return {
        "outcome": "FAILURE",
        "executor": None,
        "reads_shebang": False,
        "reason": f"unrecognised explicit interpreter {interpreter!r}",
    }


def shebang_reading_mutant_bare(path: Path) -> dict[str, Any]:
    sb = read_shebang(path)
    if sb:
        return {
            "outcome": "SUCCESS",
            "executor": shebang_interpreter(sb),
            "reads_shebang": True,
            "reason": "mutant trusted the shebang on a bare Windows invocation",
        }
    return windows_pwsh7_bare(path)


def extension_implies_bash_mutant_bare(path: Path) -> dict[str, Any]:
    if Path(path).suffix.lower() in {".sh", ".bash"}:
        return {
            "outcome": "SUCCESS",
            "executor": "bash",
            "reads_shebang": False,
            "reason": "mutant treated .sh as implying bash on Windows",
        }
    return windows_pwsh7_bare(path)


def classify_script(path: Path) -> dict[str, Any]:
    st = path.stat()
    shebang = read_shebang(path)
    header = b""
    try:
        with path.open("rb") as fh:
            header = fh.read(4)
    except OSError:
        pass
    kind = "script"
    if header.startswith(b"\x7fELF") or header.startswith(b"MZ"):
        kind = "native-binary"
    ext = path.suffix.lower()
    return {
        "path": posix_rel(path),
        "extension": ext or "",
        "shebang": shebang,
        "shebang_interpreter": shebang_interpreter(shebang),
        "posix_exec_bit": bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)),
        "kind": kind,
        "windows_pwsh7_bare": windows_pwsh7_bare(path, shebang=shebang),
        "windows_explicit_bash": windows_explicit("bash", path),
    }


def is_call_site_file(rel: Path) -> bool:
    parts = rel.parts
    name = rel.name.lower()
    if name == "plugin.json":
        return True
    if "hooks" in parts and rel.suffix.lower() == ".json":
        return True
    if name == "manifest.json":
        return True
    if ".github" in parts and rel.suffix.lower() in {".yml", ".yaml"}:
        return True
    return False


def _first_token(value: str) -> str:
    try:
        parts = shlex.split(value, posix=True)
    except ValueError:
        parts = value.split()
    return parts[0] if parts else ""


def classify_command_value(value: Any, parent: dict[str, Any] | None) -> dict[str, Any] | None:
    parent = parent or {}
    sibling: str | None = None
    for key in INTERPRETER_KEYS:
        raw = parent.get(key)
        if isinstance(raw, str) and raw.strip():
            sibling = raw.strip()
            break

    if isinstance(value, list) and value:
        tokens = [str(v) for v in value if v is not None]
        if not tokens:
            return None
        first = Path(tokens[0]).name.lower()
        script_token = next(
            (t for t in tokens if looks_like_script_ref(t) or Path(t).suffix.lower() in SCRIPT_EXTS),
            tokens[-1],
        )
        if first in INTERPRETER_NAMES:
            return {
                "form": "argv",
                "argv": tokens,
                "script": script_token,
                "explicit_interpreter": first,
                "bare": False,
            }
        if looks_like_script_ref(tokens[0]) or Path(tokens[0]).suffix.lower() in SCRIPT_EXTS:
            return {
                "form": "argv",
                "argv": tokens,
                "script": tokens[0],
                "explicit_interpreter": sibling,
                "bare": sibling is None,
            }
        return None

    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    first = Path(_first_token(text)).name.lower()
    script = text
    try:
        toks = shlex.split(text, posix=True)
    except ValueError:
        toks = text.split()
    for tok in toks:
        if looks_like_script_ref(tok) or Path(tok).suffix.lower() in SCRIPT_EXTS:
            script = tok
            break
    script_is_script = looks_like_script_ref(script) or Path(script).suffix.lower() in SCRIPT_EXTS
    if first in INTERPRETER_NAMES:
        if not script_is_script:
            return None
        return {
            "form": "string",
            "raw": text,
            "script": script,
            "explicit_interpreter": first,
            "bare": False,
        }
    if not script_is_script:
        return None
    return {
        "form": "string",
        "raw": text,
        "script": script,
        "explicit_interpreter": sibling,
        "bare": sibling is None,
    }


def walk_json(node: Any, parent: dict[str, Any] | None, pointer: str) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        for key, child in node.items():
            child_ptr = f"{pointer}/{key}"
            if key in COMMAND_KEYS:
                classified = classify_command_value(child, node)
                if classified:
                    script = str(classified.get("script") or "")
                    if looks_like_script_ref(script) or Path(script).suffix.lower() in SCRIPT_EXTS:
                        yield {"pointer": child_ptr, "key": key, **classified}
            yield from walk_json(child, node, child_ptr)
    elif isinstance(node, list):
        for i, child in enumerate(node):
            yield from walk_json(child, parent, f"{pointer}/{i}")


def _site_row(
    rel: Path, hit: dict[str, Any], *, source: str
) -> dict[str, Any]:
    script = str(hit.get("script") or "")
    bare = bool(hit.get("bare"))
    explicit = hit.get("explicit_interpreter")
    win = (
        windows_pwsh7_bare(script)
        if bare
        else windows_explicit(str(explicit or "unknown"), script)
    )
    return {
        "file": rel.as_posix(),
        "pointer": hit.get("pointer"),
        "key": hit.get("key"),
        "form": hit.get("form"),
        "script": script,
        "explicit_interpreter": explicit,
        "bare": bare,
        "windows_pwsh7": win,
        "hazard": bare and win.get("outcome") == "FAILURE",
        "source": source,
    }


def scan_yaml_ci_sites() -> list[dict[str, Any]]:
    """Single-line GitHub Actions `run:` / `shell:` command sites.

    Multiline `|` / `>` blocks are counted as skipped, not classified: a
    folded block is not a single argv the Windows resolver can name.
    """
    sites: list[dict[str, Any]] = []
    for path in iter_files():
        try:
            rel = path.relative_to(REPO)
        except ValueError:
            continue
        if ".github" not in rel.parts:
            continue
        if path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            i += 1
            if not stripped.startswith("run:"):
                continue
            value = stripped[4:].strip()
            if value in {"|", ">", "|-", ">-", "|+", ">+"}:
                continue
            classified = classify_command_value(value, None)
            if not classified:
                continue
            script = str(classified.get("script") or "")
            if not (
                looks_like_script_ref(script)
                or Path(script).suffix.lower() in SCRIPT_EXTS
            ):
                continue
            sites.append(
                _site_row(
                    rel,
                    {
                        **classified,
                        "pointer": f":{i}",
                        "key": "run",
                    },
                    source="github-workflow-run",
                )
            )
    return sites


def scan_call_sites() -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    for path in iter_files():
        try:
            rel = path.relative_to(REPO)
        except ValueError:
            continue
        if not is_call_site_file(rel):
            continue
        if path.suffix.lower() != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        for hit in walk_json(data, None, ""):
            script = str(hit.get("script") or "")
            if not (
                looks_like_script_ref(script)
                or Path(script).suffix.lower() in SCRIPT_EXTS
            ):
                continue
            sites.append(_site_row(rel, hit, source="json-manifest"))
    sites.extend(scan_yaml_ci_sites())
    sites.sort(key=lambda r: (r["file"], r["pointer"] or ""))
    return sites


def scan_scripts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in iter_files():
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        try:
            mode = path.stat().st_mode
        except OSError:
            continue
        extless_exec = (not ext) and bool(
            mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        )
        if ext not in SCRIPT_EXTS and not extless_exec:
            continue
        try:
            rows.append(classify_script(path))
        except OSError:
            continue
    rows.sort(key=lambda r: r["path"])
    return rows


def _pwsh_present() -> bool:
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder:
            continue
        base = Path(folder)
        if (base / "pwsh").exists() or (base / "pwsh.exe").exists():
            return True
    return False


def control_pair() -> dict[str, Any]:
    control_dir = HERE / "fixtures" / "control"
    with_sb = control_dir / "with-shebang.sh"
    no_sb = control_dir / "no-shebang.sh"
    honest_bare = windows_pwsh7_bare(with_sb, shebang=read_shebang(with_sb))
    honest_explicit = windows_explicit("bash", with_sb)
    honest_bare_nosb = windows_pwsh7_bare(no_sb)
    mutant_shebang = shebang_reading_mutant_bare(with_sb)
    mutant_ext = extension_implies_bash_mutant_bare(with_sb)
    control_pass = (
        honest_bare["outcome"] == "FAILURE"
        and honest_explicit["outcome"] == "SUCCESS"
        and honest_bare_nosb["outcome"] == "FAILURE"
    )
    return {
        "with_shebang": posix_rel(with_sb),
        "no_shebang": posix_rel(no_sb),
        "honest_bare_with_shebang": honest_bare,
        "honest_explicit_bash": honest_explicit,
        "honest_bare_no_shebang": honest_bare_nosb,
        "shebang_reading_mutant": mutant_shebang,
        "extension_implies_bash_mutant": mutant_ext,
        "control_pass": control_pass,
        "shebang_mutant_would_pass_both": mutant_shebang["outcome"] == "SUCCESS"
        and honest_explicit["outcome"] == "SUCCESS",
        "extension_mutant_would_pass_both": mutant_ext["outcome"] == "SUCCESS"
        and honest_explicit["outcome"] == "SUCCESS",
        "linux_contrast": {
            "posix_execve_reads_shebang": True,
            "note": (
                "On this Linux worktree, execve would honour #! for a bare "
                "./with-shebang.sh. That SUCCESS is POSIX, not Windows, and is "
                "not the Probe 2 answer."
            ),
        },
        "pwsh_present": _pwsh_present(),
        "git_bash_present": False,
        "shells_tried": ["bash"],
        "shells_absent": ["pwsh7", "git-bash"],
    }


def census() -> dict[str, Any]:
    scripts = scan_scripts()
    sites = scan_call_sites()
    by_ext: dict[str, int] = {}
    shebang_n = 0
    native_n = 0
    for row in scripts:
        key = row["extension"] or "<none>"
        by_ext[key] = by_ext.get(key, 0) + 1
        if row.get("shebang"):
            shebang_n += 1
        if row.get("kind") == "native-binary":
            native_n += 1
    hazards = [s for s in sites if s.get("hazard")]
    return {
        "worktree": str(REPO),
        "platform": os.name,
        "script_count": len(scripts),
        "by_extension": dict(sorted(by_ext.items())),
        "with_shebang": shebang_n,
        "native_binaries": native_n,
        "call_site_count": len(sites),
        "bare_windows_hazard_count": len(hazards),
        "scripts": scripts,
        "call_sites": sites,
        "hazards": hazards,
        "control": control_pair(),
        "skip_dirs": sorted(SKIP_DIRS),
    }


if __name__ == "__main__":
    data = census()
    summary = {k: v for k, v in data.items() if k not in {"scripts", "call_sites", "hazards"}}
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"scripts={data['script_count']} sites={data['call_site_count']} "
        f"hazards={data['bare_windows_hazard_count']} "
        f"control_pass={data['control']['control_pass']}"
    )
