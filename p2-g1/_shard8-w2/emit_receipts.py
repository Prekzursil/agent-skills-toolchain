#!/usr/bin/env python3
"""Shard8-w2: emit BLOCKED receipts for the two unclosed units; verify the ten kept closures."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha_norm(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def blocked_receipt(uid, out_rel):
    out = REPO / out_rel
    p2 = REPO / ("command-center/p2-wave/probes/%s/probe2_livecheck.py" % uid)
    return {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": "FAILED:%s artifact delivered and live-verified (probes exit 0, manifest sha matches); SUCCESS withheld: no independent reviewer closure exists - builders must not self-certify" % uid,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#%s completion_sentinel" % uid,
        "min_bytes_threshold": 2048,
        "produced_by": {"vendor": "anthropic", "model": "opus-5-5",
                        "role": "builder-shard8-w2-resume", "execution_substrate": "local-serialized"},
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": ("artifact at output_path exists, parses, is not self-blocked; probe1 "
                       "(artifact consistency) and probe2 (live re-derivation) exit 0; "
                       "UNIT-ARTIFACT-MANIFEST.json row sha256 matches live bytes (CRLF-normalized). "
                       "Only the independent reviewer may flip state to SUCCESS."),
            "blocked_on": "independent reviewer closure not yet issued",
        },
        "reviewer": {"reviewer_id": "none-yet (builder must not self-certify)",
                     "verdict": "NOT-REVIEWED", "independent": False, "fresh_context": True,
                     "notes": "builder-emitted BLOCKED receipt per receipt_core; the state flip is reviewer-only"},
        "artifacts": [{"path": out_rel, "bytes": out.stat().st_size,
                       "sha256": sha_norm(out), "exists": True, "role": "primary"}],
        "evidence": [{"claim": "live probes re-verified the artifact on 2026-10-25",
                      "verdict": "CONFIRMED", "confidence": "high",
                      "anchor": "command-center/p2-wave/probes/" + uid,
                      "probes": [{"role": "source", "method": "command",
                                  "command": "python3 -B " + p2.relative_to(REPO).as_posix(),
                                  "exit_code": 0, "raw_output": "probe2_livecheck.raw.json",
                                  "fingerprint": sha_norm(p2)}]}],
        "timestamps": {"written_at": NOW},
        "downstream_consumers": [],
        "residual_unknowns": [],
    }

def main():
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    lookup = {u["id"]: u for u in cat["work_units"]}
    for uid in ("CNF-0077", "CNF-0089"):
        out_rel = lookup[uid]["output_path"]
        path = REPO / "command-center/receipts" / (uid + ".json")
        path.write_bytes(json.dumps(blocked_receipt(uid, out_rel), indent=2).encode() + b"\n")
        print(uid, "BLOCKED receipt written")
    kept = []
    for uid in ["CNF-0129","CNF-0142","CNF-0147","CNF-0149","CNF-0152","CNF-0153",
                "CNF-0158","CNF-0163","CNF-0166","CNF-0167"]:
        r = json.loads((REPO / "command-center/receipts" / (uid + ".json")).read_text(encoding="utf-8"))
        rv = r.get("reviewer") or {}
        ok = r.get("state") == "SUCCESS" and rv.get("verdict") == "PASS" and rv.get("independent") is True
        kept.append([uid, r.get("state"), rv.get("verdict"), rv.get("independent"), "KEPT" if ok else "PROBLEM"])
    print(json.dumps(kept))
    return 0

if __name__ == "__main__":
    sys.exit(main())
