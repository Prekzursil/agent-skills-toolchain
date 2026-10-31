#!/usr/bin/env python3
"""shard11 wave-2 battery: mechanical contract check over all 12 units."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent
IDS = ['IMP-0095', 'IMP-0096', 'IMP-0102', 'IMP-0107', 'IMP-0122', 'IMP-0133',
       'IMP-0138', 'IMP-0146', 'IMP-0151', 'IMP-0153', 'IMP-0160', 'IMP-0161']


def main() -> int:
    ok_all = True
    for uid in IDS:
        rec = REPO / "command-center" / "receipts" / f"{uid}.json"
        raw = rec.read_bytes().replace(b"\r\n", b"\n")
        live_sha = hashlib.sha256(raw).hexdigest()
        pd = REPO / "command-center" / "p2-wave" / "probes" / uid
        files = sorted(os.listdir(pd))
        has_ret = "SUBAGENT-RETURN.json" in files
        has_man = "UNIT-ARTIFACT-MANIFEST.json" in files
        man = (json.loads((pd / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
               if has_man else {})
        rows = [a for a in (man.get("artifacts") or []) if a.get("unit_id") == uid]
        want_rel = "command-center/receipts/" + uid + ".json"
        sha_match = any(
            str(a.get("path", "")).replace("\\", "/") == want_rel
            and a.get("sha256") == live_sha
            and a.get("present") is True
            for a in rows
        )
        ret = (json.loads((pd / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
               if has_ret else {})
        probes = [(p.get("id"), p.get("exit_code")) for p in (ret.get("named_probes") or [])]
        probes_ok = len(probes) == 2 and all(rc == 0 for _, rc in probes)
        doc = json.loads(rec.read_text(encoding="utf-8"))
        state_ok = doc.get("state") == "BLOCKED" and doc.get("status") == "BLOCKED"
        fail_ok = (doc.get("failure") or {}).get("classification") == ["reviewer-absent"]
        sent = ("SUCCESS:" + uid) in rec.read_text(encoding="utf-8")
        prev_closure = bool((doc.get("extensions") or {}).get("prev_closure"))
        green = all([has_ret, has_man, sha_match, probes_ok, state_ok, fail_ok, sent])
        ok_all &= green
        print(f"{uid} probes={probes} sha_match={sha_match} state={doc.get('state')} "
              f"class=reviewer-absent:{fail_ok} prev_closure={prev_closure} "
              f"sentinel={sent} => {'GREEN' if green else 'BROKEN'}")
    print("ALL-GREEN" if ok_all else "SOMETHING-BROKEN")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
