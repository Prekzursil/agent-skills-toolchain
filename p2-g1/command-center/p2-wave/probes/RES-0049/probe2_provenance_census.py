#!/usr/bin/env python3
"""RES-0049 independent re-derivation: provenance-generator census recount.
Two mechanics (JSON walk + raw regex) over the AUD-0041 census; NC = injected
attest-build-provenance step must fire the census detector."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0049"
GEN = re.compile(r"attest-build-provenance|slsa-github-generator|in-toto|cosign\s+attest", re.I)

def census_hits(node, out):
    if isinstance(node, dict):
        blob = json.dumps(node)[:400]
        if GEN.search(blob):
            out.append(node)
        for v in node.values():
            census_hits(v, out)
    elif isinstance(node, list):
        for v in node:
            census_hits(v, out)
    return out

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    census = L.REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    raw = census.read_text(encoding="utf-8", errors="ignore")
    cdata = json.loads(raw)
    hits = census_hits(cdata, [])
    hits = [h for h in hits if GEN.search(json.dumps(h)[:400])]
    c.append(("JSON walk: zero build-provenance generators across the inventory",
              not hits, f"hits={len(hits)}"))
    m = GEN.findall(raw)
    only_test = ("test_manifest_provenance" in raw) and not m
    c.append(("raw regex: no generator invocation anywhere; the only 'provenance' string is a unit test",
              only_test, f"regex_hits={len(m)} test_present={'test_manifest_provenance' in raw}"))
    live_dir = L.REPO / ".github" / "workflows"
    live_hits = []
    live_files = sorted(live_dir.glob("*.yml")) if live_dir.is_dir() else []
    for f in live_files:
        if GEN.search(f.read_text(encoding="utf-8", errors="ignore")):
            live_hits.append(f.name)
    c.append(("live-tree re-census on THIS worktree: zero provenance generators",
              not live_hits, f"files={[f.name for f in live_files]} hits={live_hits}"))
    cc = doc.get("ci_census") or {}
    c.append(("artifact census agrees: attestation_generator_hits empty",
              (cc.get("attestation_generator_hits") or []) == [],
              f"hits={cc.get('attestation_generator_hits')}"))

    def mutate(d):
        d.setdefault("workflows", []).append(
            {"file": "injected.yml", "steps": [{"uses": "actions/attest-build-provenance@v1"}]})
        return d

    mp = L.mutation_copy(cdata, mutate, suffix=".mutant.json")
    try:
        mdoc = json.loads(mp.read_text(encoding="utf-8"))
        fired = bool(census_hits(mdoc, []))
        c.append(("NC: injected attest-build-provenance step fires the census detector", fired,
                  f"mutant hits={len(census_hits(mdoc, []))}"))
    finally:
        mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
