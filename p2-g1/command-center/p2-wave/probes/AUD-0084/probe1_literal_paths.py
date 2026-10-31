#!/usr/bin/env python3
"""AUD-0084 probe 1 (source, static-analysis): literal-string scan for drive
letters, /home/, /Users/ and hard separators inside path contexts."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "probe1_literal_paths_out.json"

BS = chr(92)
DRIVE = re.compile("[A-Za-z]:[" + re.escape(BS) + "/]")
HOME = re.compile("/home/|/Users/|/root/")
SEP = re.compile("[" + chr(39) + chr(34) + "][A-Za-z0-9_.-]+" + re.escape(BS) + "+" + "[A-Za-z0-9_.-]+" + re.escape(BS) + "+")

SCOPES = ["platform", "tools", "scripts", "hooks", "ci", "council", "plugin",
          "workflow_foundry", "marketplace", "lib", "release"]
EXTS = {".py", ".ps1", ".sh", ".cmd", ".bat", ".js", ".ts"}
SKIP = {"node_modules", ".git", "__pycache__", "fixtures"}
MAX_FILES = 6000


def main() -> int:
    per_file: dict = {}
    files_scanned = 0
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        n = 0
        for dirpath, dirnames, filenames in base.walk():
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            for fn in filenames:
                if Path(fn).suffix not in EXTS:
                    continue
                n += 1
                if n > MAX_FILES:
                    break
                p = Path(dirpath) / fn
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                hits = []
                for pat, kind in ((DRIVE, "drive-letter"), (HOME, "home-dir"), (SEP, "hard-separator")):
                    for m in pat.finditer(text):
                        line = text.count(chr(10), 0, m.start()) + 1
                        hits.append({"kind": kind, "line": line,
                                     "snippet": m.group(0)[:60]})
                if hits:
                    rel = p.resolve().relative_to(REPO).as_posix()
                    per_file[rel] = hits[:20]
                files_scanned += 1
    total = sum(len(v) for v in per_file.values())
    by_kind = {}
    for v in per_file.values():
        for h in v:
            by_kind[h["kind"]] = by_kind.get(h["kind"], 0) + 1

    # fixture control (rough): detector must find a planted drive-letter literal
    fixture = HERE / "fixture_paths.py"
    fixture.write_text(
        "# fixture" + chr(10)
        + 'OPEN_LIT = open("' + "C:" + BS + "temp" + BS + "x.txt" + '")' + chr(10)
        + 'RX = re.compile("a' + BS + BS + 'd+")' + chr(10)
        + 'DOC = ' + chr(39) * 3 + "docstring mentions C:" + BS + "temp" + chr(39) * 3 + chr(10),
        encoding="utf-8")
    ftext = fixture.read_text(encoding="utf-8")
    f_drive = len(DRIVE.findall(ftext))
    control = {"fixture_drive_hits": f_drive, "fixture_found": f_drive >= 1}

    result = {
        "probe": "probe1-literal-paths",
        "files_scanned": files_scanned,
        "files_with_hits": len(per_file),
        "total_hits": total,
        "by_kind": by_kind,
        "top_files": sorted(per_file.items(), key=lambda kv: -len(kv[1]))[:25],
        "fixture_control": control,
        "pass": bool(control["fixture_found"]),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("files=%d with_hits=%d total=%d by_kind=%s" % (files_scanned, len(per_file), total, by_kind))
    print("SUCCESS:AUD-0084-probe1 literal path census" if result["pass"]
          else "FAILED:AUD-0084-probe1 fixture control")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
