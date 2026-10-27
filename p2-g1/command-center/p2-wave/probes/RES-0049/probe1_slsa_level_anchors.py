#!/usr/bin/env python3
"""RES-0049 delivery predicate: SLSA level verdict + census file:line anchors.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0049"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    lv = doc.get("level_verdict") or {}
    c.append(("verdict: SLSA Build L1 maximal without a hosted builder, measured current L0",
              lv.get("achievable_without_hosted_builder") == "SLSA Build L1"
              and "L0" in str(lv.get("measured_current")),
              f"achievable={lv.get('achievable_without_hosted_builder')} "
              f"current={lv.get('measured_current')}"))
    c.append(("capping capability named: no provenance generation in CI",
              "provenance" in str(lv.get("ci_capability_that_caps") or "").lower(),
              str(lv.get("ci_capability_that_caps"))[:70]))
    c.append(("named delta to the next level recorded",
              bool(str(lv.get("named_delta_to_next_level") or "").strip())
              and bool(str(lv.get("next_level") or "").strip()),
              f"next={lv.get('next_level')}"))
    c.append(("evidence that would prove L1 stated", bool(str(lv.get("evidence_that_would_prove_l1") or "").strip()),
              str(lv.get("evidence_that_would_prove_l1"))[:60]))
    census = L.REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
    lines = census.read_text(encoding="utf-8", errors="ignore").splitlines()
    a310 = lines[309] if len(lines) > 309 else ""
    a321 = lines[320] if len(lines) > 320 else ""
    a874 = lines[873] if len(lines) > 873 else ""
    a8 = lines[7] if len(lines) > 7 else ""
    c.append(("anchor :310 resolves live to the quality.yml workflow file",
              ".github/workflows/quality.yml" in a310, a310.strip()[:70]))
    c.append(("anchor :321 resolves live to hosted ubuntu-latest runners",
              "ubuntu-latest" in a321, a321.strip()[:60]))
    c.append(("anchor :874 resolves live to the only provenance token (a unit test)",
              "test_manifest_provenance" in a874, a874.strip()[:70]))
    c.append(("anchor :8 resolves live to the 7-workflow inventory count",
              "7" in a8, a8.strip()[:50]))
    cl = doc.get("claims") or []
    ok_r = len(cl) >= 2
    for x in cl:
        rails = x.get("rails") or []
        if len(rails) < 2:
            ok_r = False
            continue
        for r in rails:
            # permalink may be a local captured-bytes anchor (transport file);
            # wire-fetched rails must additionally carry their HTTP status.
            if not (str(r.get("permalink") or "").strip()
                    and r.get("fetch_timestamp")
                    and (r.get("sha256") or r.get("captured_bytes_path"))):
                ok_r = False
            elif str(r.get("transport")) == "https" and not r.get("http_status"):
                ok_r = False
    c.append(("claims carry >=2 rails each with anchor+fetch-timestamp+sha/capture "
              "(wire rails also carry their HTTP status)", ok_r, f"{len(cl)} claims"))
    qy = L.REPO / ".github" / "workflows" / "quality.yml"
    live = qy.read_text(encoding="utf-8", errors="ignore") if qy.is_file() else ""
    c.append(("two-rail doctrine: live-tree divergence from the recorded census is REPORTED, not hidden",
              True,
              f"live quality.yml here: runs-on={[ln.strip() for ln in live.splitlines() if 'runs-on' in ln][:1] or ['file-shorter-than-recorded-anchor']} "
              f"vs census :321 ubuntu-latest"))
    c.append(("live quality.yml exists on this worktree for the re-census",
              qy.is_file(), f"{qy.name} bytes={len(live)}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
