"""Emit LF-only .sh files and pin *.sh eol=lf in .gitattributes."""
from __future__ import annotations

from pathlib import Path

from detectors import GITATTRIBUTES, HERE, REPO, gitattributes_status, parse_sh_eol_lf

EMITTTED = HERE / "emitted"

SCRIPTS: dict[str, str] = {
    "hello.sh": (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo TST-0192-hello\n"
    ),
    "branch.sh": (
        "#!/usr/bin/env bash\n"
        "if true; then\n"
        "  echo TST-0192-branch\n"
        "fi\n"
    ),
    "argv.sh": (
        "#!/usr/bin/env bash\n"
        "printf '%s\\n' \"${1:-TST-0192-argv}\"\n"
    ),
}

GITATTR_BLOCK = (
    "# TST-0192: generated shell scripts must stay LF on every checkout\n"
    "*.sh text eol=lf\n"
)


def write_lf(path: Path, text: str) -> None:
    if "\r" in text:
        raise ValueError(f"emitter refused CR in {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    raw = path.read_bytes()
    if b"\r" in raw:
        raise ValueError(f"written {path} contains CR")


def ensure_gitattributes() -> dict:
    path = GITATTRIBUTES
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if not parse_sh_eol_lf(text)["has_sh_eol_lf"]:
            addition = GITATTR_BLOCK if text.endswith("\n") else "\n" + GITATTR_BLOCK
            path.write_text(text + addition, encoding="utf-8")
    else:
        write_lf(path, GITATTR_BLOCK)
    st = gitattributes_status(path)
    if not st["has_sh_eol_lf"]:
        raise RuntimeError("failed to pin *.sh eol=lf in .gitattributes")
    return st


def emit() -> dict:
    EMITTTED.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, body in SCRIPTS.items():
        path = EMITTTED / name
        write_lf(path, body)
        rel = path.relative_to(REPO).as_posix()
        raw = path.read_bytes()
        rows.append(
            {
                "path": rel,
                "bytes": len(raw),
                "cr_count": raw.count(b"\r"),
            }
        )
    ga = ensure_gitattributes()
    return {"scripts": rows, "gitattributes": ga}
