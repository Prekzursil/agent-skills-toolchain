#!/usr/bin/env python3
"""Repair the unterminated string literal in the ARC-0021 probe stubs (line-based)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "command-center" / "p2-wave" / "probes" / "ARC-0021"


def repair(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    i = 0
    fixed = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip("\r\n") == '        "# rule.no-secrets':
            # lines i .. i+3 are: unterminated string, blank, body, closing quote
            body = lines[i + 2].rstrip("\r\n")
            out.append(f'        "# rule.no-secrets\\n\\n{body}\\n"\n')
            i += 4  # skip old B, blank C, body D, quote E
            fixed += 1
            continue
        out.append(line)
        i += 1
    path.write_text("".join(out), encoding="utf-8", newline="")
    print(f"{path.name}: fixed={fixed}")
    return 0 if fixed else 1


if __name__ == "__main__":
    rc = 0
    for name in ("probe1_adopt.py", "probe2_uninstall.py"):
        rc |= repair(BASE / name)
    sys.exit(rc)
