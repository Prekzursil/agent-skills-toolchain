#!/usr/bin/env python3
"""Census emit scripts + leftover target fields for envelope-rest IDs."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}


def ids() -> list[str]:
    out = []
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        p = SHARDS / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid:
                out.append(uid)
    return out


def main() -> int:
    prefixes = Counter()
    emit_names = Counter()
    has_targets = Counter()
    has_completion = Counter()
    schema_like = 0
    n = 0
    samples_no_targets = []
    for uid in ids():
        n += 1
        prefixes[uid.split("-")[0]] += 1
        probe = WAVE / "probes" / uid
        emits = []
        if probe.is_dir():
            for p in sorted(probe.glob("*.py")):
                if p.name.startswith(("emit", "write_receipts", "build")):
                    emits.append(p.name)
        emit_names[tuple(emits) or ("<none>",)] += 1
        u = BY_ID.get(uid) or {}
        rel = str(u.get("output_path") or "").replace("\\", "/")
        path = REPO / rel
        if path.is_file():
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                doc = None
            if isinstance(doc, dict):
                if "$schema" in doc or "$id" in doc:
                    schema_like += 1
                t = doc.get("targets")
                has_targets[type(t).__name__ if t is not None else "missing"] += 1
                has_completion["completion_sentinel" in doc] += 1
                if not t:
                    samples_no_targets.append(
                        {
                            "id": uid,
                            "keys": sorted(doc.keys())[:18],
                            "state": doc.get("state"),
                            "sentinel_head": str(doc.get("sentinel") or "")[:60],
                            "emits": emits,
                        }
                    )
    payload = {
        "n": n,
        "prefixes": dict(prefixes),
        "emit_names": {str(k): v for k, v in emit_names.most_common()},
        "has_targets": dict(has_targets),
        "has_completion": {str(k): v for k, v in has_completion.items()},
        "schema_like": schema_like,
        "samples_no_targets": samples_no_targets[:12],
    }
    dest = SHARDS / "_envelope_census2.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("n", "prefixes", "has_targets", "schema_like")}, indent=2))
    print("emit_names", json.dumps(payload["emit_names"], indent=2)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
