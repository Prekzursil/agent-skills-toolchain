#!/usr/bin/env python3
"""Regenerate tools/agent-sessions/manifest-summary.json from the live vault.

The summary is the repo-side drift baseline: it pins the manifest's sha256,
size, entry count and per-store counts/bytes/aliases WITHOUT committing the
bulk manifest.jsonl (owner rule: content lives in the vault, not in git).

Usage:
    python tools/agent-sessions/regen_summary.py [--vault D:/agent-sessions-vault]

Run after any sync, then commit the updated summary on the sessions/vault-sync
branch. Stdlib only (Python >= 3.7).
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VAULT = "D:/agent-sessions-vault"


def summarize(vault):
    mp = os.path.join(vault, "manifest.jsonl")
    h = hashlib.sha256()
    n = 0
    with open(mp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    man_sha, man_bytes = h.hexdigest(), os.path.getsize(mp)

    stores = {}
    with open(mp, encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            s = stores.setdefault(
                o["store"],
                {
                    "files": 0,
                    "bytes": 0,
                    "aliases": 0,
                    "ok": 0,
                    "missing": 0,
                    "unreadable": 0,
                },
            )
            status = o.get("status")
            if status == "ok":
                s["ok"] += 1
                s["bytes"] += o.get("size") or 0
                if o.get("alias_of"):
                    s["aliases"] += 1
            elif status == "missing":
                s["missing"] += 1
            else:
                s["unreadable"] += 1
            s["files"] += 1
            n += 1

    tot = {"files": 0, "bytes": 0, "aliases": 0, "ok": 0, "missing": 0, "unreadable": 0}
    for s in stores.values():
        for k in tot:
            tot[k] += s[k]

    return {
        "_comment": (
            "Drift baseline for the repo: compare manifest_sha256 against "
            "the live D:/agent-sessions-vault/manifest.jsonl sha256; "
            "regenerate via tools/agent-sessions/regen_summary.py. Bulk "
            "manifest.jsonl itself stays OUT of git (owner rule)."
        ),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "engine_version_written_by": "regen_summary.py",
        "vault": vault,
        "manifest_sha256": man_sha,
        "manifest_bytes": man_bytes,
        "manifest_entries": n,
        "stores": stores,
        "totals": tot,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--out", default=os.path.join(HERE, "manifest-summary.json"))
    a = ap.parse_args()
    if not os.path.isfile(os.path.join(a.vault, "manifest.jsonl")):
        sys.stderr.write("no manifest.jsonl under %s\n" % a.vault)
        return 2
    out = summarize(a.vault)
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, a.out)
    print(
        "entries=%d stores=%d sha256=%s -> %s"
        % (out["manifest_entries"], len(out["stores"]), out["manifest_sha256"], a.out)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
