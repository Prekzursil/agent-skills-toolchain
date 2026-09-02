#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-15.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
FAIL_RE = re.compile(
    r"""fail\(\s*f?['\"]([^'\"]+)['\"]|print\(\s*f?['\"]FAILED:[^'\"]+['\"]|raise AssertionError\(\s*['\"]([^'\"]+)"""
)
CALL_RE = re.compile(r"\b(fail|assert_|check)\([^)]{0,180}\)")


def main() -> None:
    rows = []
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        probes = []
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            calls = CALL_RE.findall(text)
            fails = []
            for ln in text.splitlines():
                s = ln.strip()
                if "fail(" in s or "FAILED:" in s or "AssertionError" in s or s.startswith("assert "):
                    fails.append(s[:220])
            probes.append(
                {
                    "name": p.name,
                    "lines": text.count("\n") + 1,
                    "fails": fails[:30],
                    "has_jsonschema": "jsonschema" in text,
                    "has_emit_cmp": "raw_output" in text or "named_probe" in text,
                }
            )
        rows.append(
            {
                "id": uid,
                "emit": (pdir / "emit_artifact.py").is_file() or (pdir / "emit.py").is_file(),
                "write": (pdir / "write_receipts.py").is_file(),
                "probes": probes,
            }
        )
    dest = HERE / "_shard15_failspec.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("wrote", dest, "n", len(rows))
    for r in rows:
        nfail = sum(len(p["fails"]) for p in r["probes"])
        print(r["id"], "emit", r["emit"], "write", r["write"], "nfail", nfail, "nprobe", len(r["probes"]))


if __name__ == "__main__":
    main()
