#!/usr/bin/env python3
"""Look inside leftover tgz for missing probe scripts and agentspec.fanin. No full extract."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
PULL = WAVE / "ovh-monitor" / "delivery-pull"
NEED = [
    "command-center/p2-wave/probes/ADV-0013/probe1_old_token_occurrences.py",
    "command-center/p2-wave/probes/ADV-0013/probe2_rename_commit_differential.py",
    "tools/agentspec/agentspec/fanin/__init__.py",
    "tools/agentspec/agentspec/fanin.py",
]
WANT_SUBSTR = ("agentspec/fanin", "probe1_old_token", "ADV-0013/probe")


def main() -> int:
    hits: list[str] = []
    tgzs = sorted(PULL.glob("*/p2-delivery.tgz")) + sorted(PULL.glob("*/p2-leftover-delta.tgz"))
    print(f"tgz={len(tgzs)}", flush=True)
    for tgz in tgzs:
        try:
            with tarfile.open(tgz, "r:gz") as tf:
                names = tf.getnames()
        except Exception as exc:
            print(f"FAIL {tgz.name} {exc}", flush=True)
            continue
        for n in names:
            nn = n.replace("\\", "/")
            if any(s in nn for s in WANT_SUBSTR):
                hits.append(f"{tgz.parent.name}:{nn}")
        for rel in NEED:
            if any(n.replace("\\", "/").endswith(rel) or n.replace("\\", "/") == rel for n in names):
                hits.append(f"NEED {tgz.parent.name}:{rel}")
    out = WAVE / "ovh-monitor" / "g1-tgz-missing.json"
    out.write_text(json.dumps({"hits": hits[:200], "n": len(hits)}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": len(hits), "head": hits[:40]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
