#!/usr/bin/env python3
"""RES-0044 independent re-derivation: live credential scan, both states.
Recreated 2026-10-25 (wave-2 shard 17). The scanner re-runs over the artifact
bytes; the recorded bypass mutants (B1 nested JWT, B2 bearer header line,
B3 access_token key) must each fire it on a temp copy."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0044"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    hits = L.scan_credentials(text)
    c.append(("live scan: delivered artifact carries zero credential-shaped values",
              not hits, f"hits={hits}"))
    cs = doc.get("credential_scan") or {}
    c.append(("recorded scan verdict is CREDENTIAL-FREE",
              cs.get("result") == "CREDENTIAL-FREE" and cs.get("hit_count") is not None and int(cs["hit_count"]) == 0,
              f"recorded hit_count={cs.get('hit_count')}"))
    prog = doc.get("this_program") or {}
    imp = str(prog.get("imp0048_hits") or "")
    c.append(("no remote-url server recorded on the program's MCP surface",
              "http" not in imp.lower(), f"imp0048_hits={prog.get('imp0048_hits')}"))

    def m1(d):  # B1 nested JWT
        d["_planted_control"] = ("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
                                 "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
                                 "c2FtcGxlX3NpZ25hdHVyZV9ub3RfYV9yZWFsX3Rva2Vu")
        return d

    def m2(d):  # B2 bearer header inside a transcript field
        d["notes"] = str(d.get("notes") or "") + " Authorization: Bearer Ya29.fakebearercontexttoken"
        return d

    def m3(d):  # B3 access_token key with a 40-hex secret
        d["transcript_example"] = {"access_token": "a" * 40}
        return d

    for name, mut in (("B1 nested-JWT", m1), ("B2 bearer-header", m2), ("B3 access_token-key", m3)):
        mp = L.mutation_copy(doc, mut)
        try:
            fired = bool(L.scan_credentials(mp.read_text(encoding="utf-8")))
            c.append((f"NC bypass mutant ({name}) fires the scanner", fired, f"fired={fired}"))
        finally:
            mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
