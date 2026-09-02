#!/usr/bin/env python3
"""Runner: commit messages, PR bodies, and prompts travel by FILE, never argv.

Catalog TST-0186: apostrophe-bearing prose must not reach a shell command
line. The production argv is always a flag-plus-path shape:

  git commit -F <path>
  gh pr create --title <safe> --body-file <path>
  codex --ignore-user-config --prompt-file <path>

The prose bytes are written with Path.write_bytes and never interpolated
into a shell string. Consumers in this probe stand in for git/gh/codex so
the live round-trip does not perform a real commit or network call.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONSUMER = HERE / "consumers.py"

# Odd apostrophe count: naive single-quote wrap leaves bash looking for a
# matching quote (catalog both-states control).
CONTROL_PAYLOAD = "don't ship"

# Property corpus: each metacharacter the catalog names, plus a combined row.
PROPERTY_PAYLOADS: dict[str, bytes] = {
    "apostrophe": "don't ship".encode("utf-8"),
    "double-quote": b'he said "no merge"',
    "backtick": b"touch `date`",
    "dollar": b"path=$HOME/secret",
    "newline": b"subject line\n\nsecond paragraph",
    "crlf": b"subject line\r\n\r\nCRLF body",
    "combined": (
        "O'Brien's \"draft\" uses `rm -rf` and $HOME\n"
        "line-two\r\n"
        "end"
    ).encode("utf-8"),
}

KINDS = ("commit_message", "pr_body", "prompt")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_prose(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def argv_for(kind: str, file_path: Path) -> list[str]:
    """Production argv. The file path is the only payload-bearing token, and
    it is an argv element (no shell)."""
    p = str(file_path)
    if kind == "commit_message":
        return ["git", "commit", "-F", p]
    if kind == "pr_body":
        return ["gh", "pr", "create", "--title", "tst0186", "--body-file", p]
    if kind == "prompt":
        return ["codex", "--ignore-user-config", "--prompt-file", p]
    raise ValueError(f"unknown kind {kind}")


def prose_leaked_into_argv(argv: Iterable[str], prose: bytes) -> bool:
    """True if the prose bytes appear in any argv element other than as a
    path we just wrote (paths are ascii temp names without the prose)."""
    try:
        text = prose.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    for elt in argv:
        raw = elt.encode("utf-8", errors="surrogateescape")
        if prose and prose in raw and Path(elt).is_file():
            # Path coincidentally containing bytes is still a leak if the
            # path IS the prose; our writer never uses the prose as a name.
            if Path(elt).read_bytes() == prose:
                continue
        if prose and prose in raw:
            return True
        if text and text in elt and not Path(elt).is_file():
            return True
    return False


def dispatch(kind: str, prose: bytes, workdir: Path) -> dict:
    if kind not in KINDS:
        raise ValueError(kind)
    dest = workdir / f"{kind}.txt"
    write_prose(dest, prose)
    argv = argv_for(kind, dest)
    leaked = prose_leaked_into_argv(argv, prose)
    return {
        "kind": kind,
        "path": str(dest),
        "argv": argv,
        "argv_shell_join_unused": True,
        "prose_sha256": sha256_bytes(prose),
        "file_sha256": sha256_bytes(dest.read_bytes()),
        "leaked_into_argv": leaked,
        "ok": (not leaked) and dest.is_file() and dest.read_bytes() == prose,
    }


def consumer_argv(kind: str, file_path: Path) -> list[str]:
    """Stand-in executable that accepts the same flag shape as production."""
    py = str(CONSUMER)
    if kind == "commit_message":
        return [sys.executable, py, "commit", "-F", str(file_path)]
    if kind == "pr_body":
        return [sys.executable, py, "pr", "--body-file", str(file_path)]
    if kind == "prompt":
        return [sys.executable, py, "prompt", "--prompt-file", str(file_path)]
    raise ValueError(kind)


def run_file_route(kind: str, prose: bytes, workdir: Path) -> dict:
    rec = dispatch(kind, prose, workdir)
    argv = consumer_argv(kind, Path(rec["path"]))
    # argv-array exec: no shell, so quoting never sees the prose.
    proc = subprocess.run(argv, capture_output=True, timeout=20)
    stdout = proc.stdout or b""
    rec.update(
        {
            "consumer_argv": argv,
            "returncode": proc.returncode,
            "stdout_sha256": sha256_bytes(stdout),
            "round_trip": stdout == prose,
            "stderr_head": (proc.stderr or b"")[:400].decode("utf-8", "replace"),
        }
    )
    rec["file_route_holds"] = (
        rec["ok"]
        and rec["returncode"] == 0
        and rec["round_trip"] is True
        and rec["leaked_into_argv"] is False
    )
    return rec


def run_property_matrix(workdir: Path) -> dict:
    rows = {}
    all_ok = True
    for name, prose in PROPERTY_PAYLOADS.items():
        kind_rows = {}
        for kind in KINDS:
            sub = workdir / name / kind
            sub.mkdir(parents=True, exist_ok=True)
            rec = run_file_route(kind, prose, sub)
            kind_rows[kind] = {
                "file_route_holds": rec["file_route_holds"],
                "returncode": rec["returncode"],
                "round_trip": rec["round_trip"],
                "leaked_into_argv": rec["leaked_into_argv"],
                "argv": rec["argv"],
                "prose_sha256": rec["prose_sha256"],
            }
            if not rec["file_route_holds"]:
                all_ok = False
        rows[name] = kind_rows
    return {"rows": rows, "ok": all_ok, "n_payloads": len(PROPERTY_PAYLOADS)}


def second_shell_note() -> dict:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    git_bash = shutil.which("bash")
    return {
        "host_os": os.uname().sysname.lower() if hasattr(os, "uname") else "linux",
        "pwsh_on_path": pwsh,
        "bash_on_path": git_bash,
        "note": (
            "Catalog asks an independent reviewer to re-run on a SECOND Windows "
            "shell (pwsh7 and Git Bash). This worktree is Linux. Git Bash as a "
            "Windows distribution is absent. pwsh is "
            + ("present at " + pwsh if pwsh else "absent")
            + ". The POSIX file-route (argv array, no shell) is shell-agnostic; "
            "the inline single-quote wrap is the bash control. A Windows "
            "re-run remains residual, not a silent pass."
        ),
        "file_route_shell_agnostic": True,
        "windows_second_shell_live": bool(pwsh),
    }


def catalog_inputs() -> dict:
    targets = {
        "_USER-PROMPTS.md": REPO / "_USER-PROMPTS.md",
        "rules/common/windows-shell.md": REPO / "rules" / "common" / "windows-shell.md",
        "rules/common/cross-vendor-dispatch.md": REPO
        / "rules"
        / "common"
        / "cross-vendor-dispatch.md",
        "tools/lib/codex-invocation.mjs": REPO / "tools" / "lib" / "codex-invocation.mjs",
    }
    out = {}
    for rel, path in targets.items():
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        heading10 = False
        if rel.endswith("windows-shell.md") and text:
            for line in text.splitlines():
                if line.strip().startswith("## 10"):
                    heading10 = True
                    break
        out[rel] = {
            "present": path.is_file(),
            "bytes": len(text.encode("utf-8")) if text else 0,
            "heading_10": heading10,
        }
    return out


def fn_anchor(name: str) -> str:
    text = Path(__file__).read_text(encoding="utf-8")
    needle = f"def {name}("
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"command-center/p2-wave/probes/TST-0186/runner.py:{i}"
    return "command-center/p2-wave/probes/TST-0186/runner.py:1"


def measure(workdir: Path) -> dict:
    """Live matrix used by emit and by both named probes."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import inline_control as I  # noqa: E402
    import scan as S  # noqa: E402

    inline_dir = workdir / "inline"
    inline_dir.mkdir(parents=True, exist_ok=True)
    inline = I.run_inline_script(CONTROL_PAYLOAD, inline_dir)
    file_rows = {}
    file_ok = True
    for kind in KINDS:
        sub = workdir / "file" / kind
        sub.mkdir(parents=True, exist_ok=True)
        rec = run_file_route(kind, CONTROL_PAYLOAD.encode("utf-8"), sub)
        file_rows[kind] = rec
        if not rec["file_route_holds"]:
            file_ok = False
    prop = run_property_matrix(workdir / "property")
    scanned = S.run_scan()
    inputs = catalog_inputs()
    second = second_shell_note()
    ok = (
        inline["control_holds"]
        and file_ok
        and prop["ok"]
        and scanned["ok"]
    )
    return {
        "ok": ok,
        "control_payload": CONTROL_PAYLOAD,
        "control_payload_sha256": sha256_bytes(CONTROL_PAYLOAD.encode("utf-8")),
        "inline": inline,
        "file": file_rows,
        "file_route_holds": file_ok,
        "property": prop,
        "scan": scanned,
        "catalog_inputs": inputs,
        "second_shell": second,
        "anchors": {
            "argv_for": fn_anchor("argv_for"),
            "run_file_route": fn_anchor("run_file_route"),
            "dispatch": fn_anchor("dispatch"),
        },
    }


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tst0186-runner-") as tmp:
        prop = run_property_matrix(Path(tmp))
    print(json.dumps({"ok": prop["ok"], "n_payloads": prop["n_payloads"]}, sort_keys=True))
    if not prop["ok"]:
        print("FAILED:TST-0186-runner property matrix")
        return 1
    print("SUCCESS:TST-0186-runner file route property matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
