#!/usr/bin/env python3
"""AUD-0083 named probe 1: census of executable scripts + shebang parse.

Walks the tracked working tree (git ls-files, so vendored/ignored noise such
as node_modules or .venv never inflates the count) and classifies every file
that is either (a) marked executable on disk, (b) carries a shebang line, or
(c) has an extension this repo actually uses for scripts (.sh, .ps1, .py,
.mjs, .js). For each such file this probe records:

  * extension (or "" for extensionless)
  * exec bit (measured via os.access(..., os.X_OK), not assumed from mode bits
    alone -- os.access resolves the real effective permission check)
  * shebang line verbatim, if present, and the interpreter token parsed out of
    it (first whitespace-separated token after `#!`, with a `env NAME` shebang
    resolved to NAME)

HONESTY NOTE: this probe only measures what shebangs SAY. It does not decide
what would actually run them on any platform -- that resolution (including the
Windows-has-no-shebang-support case) is probe 2's job, and deliberately kept
in a separate module so probe 2 cannot silently fall back to re-reading the
shebang line instead of doing real platform resolution (see AUD-0083's
tests_required control).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "probe1-inventory-shebangs.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-inventory-shebangs.raw.txt"

SCRIPT_EXTENSIONS = {".sh", ".ps1", ".py", ".mjs", ".js", ".bash", ".zsh"}
# Extensions that are never scripts even if they happen to carry a shebang-
# shaped first line (binary formats, data files) -- excluded so the census
# does not misclassify e.g. a JSON file that happens to start with "#!".
NEVER_SCRIPT_EXTENSIONS = {
    ".json",
    ".md",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".lock",
    ".txt",
}


def git_ls_files() -> list[str]:
    r = subprocess.run(
        ["git", "ls-files"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git ls-files failed rc={r.returncode}: {r.stderr}")
    return [ln for ln in r.stdout.splitlines() if ln]


def parse_shebang(first_line: str) -> tuple[str, str] | tuple[None, None]:
    """Return (raw_shebang, resolved_interpreter) or (None, None)."""
    if not first_line.startswith("#!"):
        return None, None
    body = first_line[2:].strip()
    if not body:
        return first_line, ""
    tokens = body.split()
    if tokens[0].endswith("/env") or tokens[0] == "env":
        # e.g. "#!/usr/bin/env python3" or "#!/usr/bin/env -S bash"
        rest = tokens[1:]
        rest = [t for t in rest if t != "-S"]
        interp = rest[0] if rest else ""
    else:
        interp = os.path.basename(tokens[0])
    return first_line, interp


def read_first_line_and_exec(rel: str) -> dict | None:
    p = REPO / rel
    if not p.is_file():
        return None
    ext = p.suffix.lower()
    if ext in NEVER_SCRIPT_EXTENSIONS:
        return None
    try:
        is_exec = os.access(p, os.X_OK)
    except OSError:
        is_exec = False
    first_line = ""
    is_binary = False
    try:
        with open(p, "rb") as fh:
            chunk = fh.read(4096)
        if b"\x00" in chunk:
            is_binary = True
        else:
            first_line = chunk.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    except OSError:
        pass
    if is_binary:
        return None
    shebang, interp = parse_shebang(first_line)
    has_shebang = shebang is not None
    is_script_ext = ext in SCRIPT_EXTENSIONS
    if not (is_exec or has_shebang or is_script_ext):
        return None
    return {
        "path": rel,
        "extension": ext or "",
        "exec_bit": bool(is_exec),
        "has_shebang": has_shebang,
        "shebang": shebang or "",
        "shebang_interpreter": interp or "",
        "extensionless": ext == "",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = git_ls_files()
    rows: list[dict] = []
    for rel in files:
        row = read_first_line_and_exec(rel)
        if row is not None:
            rows.append(row)

    by_extension: dict[str, int] = {}
    by_shebang_interpreter: dict[str, int] = {}
    exec_bit_count = 0
    shebang_count = 0
    extensionless_count = 0
    extensionless_with_shebang = 0
    extensionless_no_shebang = 0
    exec_no_shebang_count = 0

    for row in rows:
        ext = row["extension"] or "(none)"
        by_extension[ext] = by_extension.get(ext, 0) + 1
        if row["exec_bit"]:
            exec_bit_count += 1
        if row["has_shebang"]:
            shebang_count += 1
            interp = row["shebang_interpreter"] or "(empty)"
            by_shebang_interpreter[interp] = by_shebang_interpreter.get(interp, 0) + 1
        else:
            if row["exec_bit"]:
                exec_no_shebang_count += 1
        if row["extensionless"]:
            extensionless_count += 1
            if row["has_shebang"]:
                extensionless_with_shebang += 1
            else:
                extensionless_no_shebang += 1

    control_windows_relevant = [
        row
        for row in rows
        if row["extension"] == ".sh" or (row["extensionless"] and row["has_shebang"])
    ]

    census = {
        "ok": True,
        "started_at": started,
        "files_scanned": len(files),
        "script_rows_found": len(rows),
        "exec_bit_count": exec_bit_count,
        "shebang_count": shebang_count,
        "exec_no_shebang_count": exec_no_shebang_count,
        "extensionless_count": extensionless_count,
        "extensionless_with_shebang": extensionless_with_shebang,
        "extensionless_no_shebang": extensionless_no_shebang,
        "by_extension": dict(sorted(by_extension.items(), key=lambda kv: -kv[1])),
        "by_shebang_interpreter": dict(
            sorted(by_shebang_interpreter.items(), key=lambda kv: -kv[1])
        ),
        "windows_no_shebang_support_candidate_count": len(control_windows_relevant),
        "rows": rows,
    }

    OUT_JSON.write_text(json.dumps(census, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0083-probe1",
        f"unit=AUD-0083 probe=1 files_scanned={len(files)} script_rows_found={len(rows)}",
        f"exec_bit_count={exec_bit_count} shebang_count={shebang_count} "
        f"exec_no_shebang_count={exec_no_shebang_count}",
        f"extensionless_count={extensionless_count} "
        f"extensionless_with_shebang={extensionless_with_shebang} "
        f"extensionless_no_shebang={extensionless_no_shebang}",
        f"by_extension={census['by_extension']}",
        f"by_shebang_interpreter={census['by_shebang_interpreter']}",
        f"windows_no_shebang_support_candidate_count={len(control_windows_relevant)}",
        "--- sample rows (first 25 by path) ---",
    ]
    for row in sorted(rows, key=lambda r: r["path"])[:25]:
        lines.append(
            f"{row['path']} ext={row['extension'] or '(none)'} exec={row['exec_bit']} "
            f"shebang={row['shebang'] or '(none)'} interp={row['shebang_interpreter'] or '(none)'}"
        )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
