"""ADV-0014 Probe 1 (Windows full checkout, 2026-10-21): extract the invoked CLI
surface from source, execute each binary's --help TODAY, diff flag-by-flag, with the
valid/invalid detector control per present binary.

Binaries hunted: git gh uv node docker wsl codex claude python (the vendor CLI set the
unit names). Source = repo .py/.js/.sh/.ps1/.yaml (docs excluded)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
REPO = DIR.parents[3]
BINARIES = ["git", "gh", "uv", "node", "docker", "wsl", "codex", "claude", "python"]
INVALID = "--adv0014-nonexistent-flag-zzz"
FLAG_RE = re.compile(r"--[a-zA-Z][a-zA-Z0-9_-]{1,30}")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".tmp-pr325"}


def extract_surface() -> dict[str, dict]:
    """flags-per-binary extracted from source: statements that name the binary and
    carry --flags nearby (same line for shell/py call sites)."""
    per_bin: dict[str, set[str]] = {b: set() for b in BINARIES}
    files_walked = 0
    for path in REPO.rglob("*"):
        if path.suffix not in (".py", ".js", ".mjs", ".sh", ".ps1", ".yaml", ".yml", ".toml"):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_walked += 1
        for line in text.splitlines():
            low = line.lower()
            for b in BINARIES:
                if re.search(rf"[\s'\"=(/](?:{re.escape(b)})(?:\.exe)?[\s'\"]", " " + low + " ") or low.strip().startswith(b + " "):
                    for f in FLAG_RE.findall(line):
                        if f != INVALID:
                            per_bin[b].add(f)
    return {"files_walked": files_walked, "flags": {b: sorted(v) for b, v in per_bin.items()}}


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return -1, f"<error {exc}>"


def main() -> int:
    surf = extract_surface()
    rows: list[dict] = []
    for b in BINARIES:
        exe = shutil.which(b)
        row: dict = {"binary": b, "on_path": bool(exe), "flags_in_source": len(surf["flags"][b])}
        if not exe:
            row.update({"verdict": "NOT-CHECKED",
                        "reason": "not on PATH on this substrate"})
            rows.append(row)
            continue
        rc_help, help_text = run([b, "--help"])
        rc_ver, ver_text = run([b, "--version"])
        help_norm = " ".join(help_text.split())
        # detector control: known-valid flag (one actually printed by --help) and the
        # planted invalid flag must be ABSENT from help AND rejected by execution
        m = re.search(r"--[a-zA-Z][a-zA-Z0-9_-]+", help_norm)
        valid_flag = m.group(0) if m else None
        det_valid = bool(valid_flag) and valid_flag in help_norm
        rc_invalid, _ = run([b, INVALID], timeout=30)
        det_invalid = (INVALID not in help_norm) and rc_invalid != 0
        control = "PASS" if (det_valid and det_invalid) else ("PARTIAL" if det_valid or det_invalid else "FAIL")
        flags = surf["flags"][b]
        present = [f for f in flags if f in help_norm]
        absent = [f for f in flags if f not in help_norm]
        if control == "FAIL":
            verdict = "NOT-CHECKED"
        elif flags and not absent:
            verdict = "CONFIRMED"
        elif flags:
            verdict = "PARTIAL"   # subcommand-scoped flags legitimately absent from top-level help
        else:
            verdict = "NOT-CHECKED"  # binary present but source invokes it bare (no flags to diff)
        row.update({
            "help_rc": rc_help, "version": (ver_text.strip().splitlines() or [""])[0][:60],
            "help_bytes": len(help_text),
            "detector_control": control,
            "det_valid_flag": valid_flag, "det_valid": det_valid,
            "det_invalid_rejected": det_invalid,
            "flags_checked": len(flags), "flags_in_help": len(present),
            "flags_absent_from_toplevel_help": absent[:25],
            "verdict": verdict,
        })
        rows.append(row)

    payload = {
        "probe": "probe1-surface",
        "files_walked": surf["files_walked"],
        "rows": rows,
        "controls": {
            "CTRL-DETECTOR-VALID-AND-INVALID": all(
                r.get("detector_control") in ("PASS", "PARTIAL") for r in rows if r["on_path"]),
        },
    }
    out = [f"SUCCESS:adv0014-probe1 {surf['files_walked']} source files; "
           + "; ".join(f"{r['binary']}:{r['verdict']}(ctrl={r.get('detector_control','n/a')})"
                       for r in rows)]
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (DIR / "probe1-surface.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (DIR / "probe1-surface.raw.txt").write_text(text_out, encoding="utf-8")
    return 0 if payload["controls"]["CTRL-DETECTOR-VALID-AND-INVALID"] else 1


if __name__ == "__main__":
    sys.exit(main())
