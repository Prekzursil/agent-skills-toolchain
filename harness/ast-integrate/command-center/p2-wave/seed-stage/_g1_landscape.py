#!/usr/bin/env python3
"""Cluster the current remaining fails by normalized failure signature.

Usage: python3 _g1_landscape.py [out.json] [min_size]
Reads latest state (g1-local-full.jsonl + g1-fails-rerun.jsonl + repair-claude/*.jsonl
by mtime) and groups every failing unit by a signature derived from its tail:
exception type + message head, or the FAILED:<id>-probeN reason with digits/ids
masked. Prints clusters (largest first) and writes JSON with members + sample tail.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import latest_rows  # noqa: E402  (02.09: Linux-native path fallback)

latest = latest_rows()

EXC_RE = re.compile(r"^\s*([A-Za-z_]+(?:Error|Exception|Exit|Interrupt|Warning))\b:?\s*(.*)$")
PROBE_FAIL_RE = re.compile(r"FAILED:[A-Z]{2,5}-\d{4}(?:-probe\d)?\s+(.*)$")


def norm(s: str) -> str:
    s = re.sub(r"[A-Z]{2,5}-\d{4}", "<ID>", s)
    s = re.sub(r"/home/\S+", "<PATH>", s)
    s = re.sub(r"0x[0-9a-f]+", "<HEX>", s)
    s = re.sub(r"\d+", "<N>", s)
    s = re.sub(r"'[^']*'", "'<S>'", s)
    s = re.sub(r'"[^"]*"', '"<S>"', s)
    return s.strip()[:140]


def signature(rec: dict) -> str:
    tail = str(rec.get("tail") or "")
    line = str(rec.get("line") or "")
    lines = [ln.rstrip() for ln in tail.splitlines() if ln.strip()]
    # Exceptions win (module/attr/import gaps are shared-module clusters).
    for ln in reversed(lines):
        m = EXC_RE.match(ln.strip())
        if m and m.group(1) not in ("SystemExit",):
            return f"EXC {m.group(1)}: {norm(m.group(2))}"
    if "TIMEOUT" in tail or "probe-exit:124" in line:
        return "TIMEOUT"
    for ln in reversed(lines):
        m = PROBE_FAIL_RE.search(ln)
        if m and "FAILED:delivered" not in ln:
            return f"PROBE {norm(m.group(1))}"
    if "FAILED:delivered" in line:
        rest = line.split("FAILED:delivered", 1)[-1].strip().split(" ", 1)
        why = rest[1] if len(rest) > 1 else rest[0]
        if not why.startswith("probe-exit"):
            return f"MEASURE {why}"
        # probe-exit with no FAILED:<id>-probe line -> use the last non-json line
        for ln in reversed(lines[:-1]):
            if not ln.lstrip().startswith(("{", "}", "[", "]", '"', "probe[")):
                return f"LAST {norm(ln)}"
        return "PROBE-EXIT unclassified"
    return f"OTHER {norm(line)}"


groups = defaultdict(list)
for uid, rec in sorted(latest.items()):
    if rec.get("ok"):
        continue
    groups[signature(rec)].append(uid)

min_size = int(sys.argv[2]) if len(sys.argv) > 2 else 1
ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
total = sum(len(v) for v in groups.values())
print(f"fails={total} clusters={len(groups)}")
for sig, ids in ordered:
    if len(ids) < min_size:
        continue
    print(f"{len(ids):4d}  {sig}")
    print("      " + " ".join(ids[:24]) + (" ..." if len(ids) > 24 else ""))
if len(sys.argv) > 1:
    out = {"fails": total, "clusters": [
        {"sig": sig, "n": len(ids), "ids": ids,
         "sample_tail": str(latest[ids[0]].get("tail") or "")[-1200:]}
        for sig, ids in ordered]}
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
