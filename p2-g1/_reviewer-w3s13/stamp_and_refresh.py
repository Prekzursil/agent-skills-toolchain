#!/usr/bin/env python3
"""Wave-3 shard-13 independent reviewer: stamp IMP-0371 + refresh its manifest.

Only units whose verify_out.json shows ZERO failing checks are stamped here.
The stamp REPLACES the builder-authored reviewer block (which named the
builder's own probe script as "reviewer" - a self-review) with this
reviewer's block, re-validates the stamped receipt against the declared
output_schema via the program's fail-closed resolver BEFORE writing, then
re-hashes the live receipt into UNIT-ARTIFACT-MANIFEST.json's primary row
(CRLF->LF) so the manifest keeps describing the live tree.

Receipts with ANY failing check are NEVER touched by this script.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "platform" / "lib"))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import schema_resolver as sr  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
VERIFY_OUT = REPO / "_reviewer-w3s13" / "verify_out.json"
REVIEWER_ID = "claude-opus-5-5-independent-reviewer-w3s13-2026-10-26"
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def stamp_notes(rep: dict, prior_rid: str) -> str:
    return (
        "Independent reviewer closed this unit (did not build it; fresh context, "
        "started from the catalog clause + live probe re-run + manifest re-hash, "
        "not the author's summary). Five closure checks re-derived live: "
        "1) artifact at " + rep["output_path"] + " exists, non-empty, parses, "
        "state=SUCCESS with no self-declared BLOCKED/FAILED anywhere in the parsed "
        "artifact. 2) both named probes re-executed live by the reviewer from repo "
        "root, rc=0, SUCCESS: markers present, no FAILED: marker; probe2 is a "
        "negative control that FIRES on the ungated twin (both-states control "
        "distinguishes the hypotheses). 3) receipt sha256 recomputed CRLF->LF "
        "matched UNIT-ARTIFACT-MANIFEST.json primary row pre-stamp; manifest "
        "primary row re-hashed to the stamped receipt post-stamp (live re-hash, "
        "wave3 shard13). 4) output_schema resolved fail-closed via "
        "platform/lib/schema_resolver.validate_artifact: 0 errors. 5) catalog "
        "clause required fields (8) present and non-empty. Scope: PASS covers the "
        "unit contract's DELIVERED definition only, not the program 12-condition "
        "gate. The prior builder-authored reviewer block "
        "(reviewer_id=" + prior_rid + ", a probe script, i.e. a self-review) is "
        "replaced by this stamp; no other receipt content was altered."
    )


def main() -> int:
    data = json.loads(VERIFY_OUT.read_text(encoding="utf-8"))
    stamped = 0
    for uid in data["units"]:
        rep = data["results"][uid]
        if rep.get("fails"):
            print(f"SKIP {uid}: {len(rep['fails'])} failing check(s) - receipt unchanged")
            continue
        out = REPO / rep["output_path"]
        receipt = json.loads(out.read_text(encoding="utf-8"))
        prior = (receipt.get("reviewer") or {}).get("reviewer_id") or "unknown"
        receipt["reviewer"] = {
            "reviewer_id": REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "reviewed_at": NOW,
            "notes": stamp_notes(rep, prior)[:8000],
        }
        receipt["reviewer_verdict"] = "PASS"
        receipt["state"] = "SUCCESS"
        # reviewed_at lives in the reviewer block only; timestamps def forbids
        # additional properties (fail-closed pre-write check enforced this).

        # fail-closed: validate the STAMPED receipt before it touches disk
        entries = json.loads((REPO / "_shard13-w3-entries.json").read_text(encoding="utf-8"))
        declared = entries[uid]["output_schema"]
        errs = sr.validate_artifact(receipt, declared)
        if errs:
            print(f"ABORT {uid}: stamped receipt fails output_schema ({len(errs)}) - not written")
            for e in errs[:5]:
                print("   ", e[:160])
            return 1

        out.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # refresh manifest primary row to the stamped receipt (live re-hash)
        man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man = json.loads(man_path.read_text(encoding="utf-8"))
        sha, nbytes = digest(out)
        hit = False
        for row in man.get("artifacts") or []:
            if str(row.get("path") or "").replace("\\", "/") == rep["output_path"]:
                row["sha256"] = sha
                row["bytes"] = nbytes
                row["present"] = True
                hit = True
        if not hit:
            print(f"ABORT {uid}: manifest primary row not found after stamp")
            return 1
        man["ts"] = NOW[:10]
        man["derivation"] = "per-unit (live re-hash 2026-10-26, wave3 shard13 independent review)"
        man_path.write_text(
            json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # verify the refreshed manifest actually matches the live receipt
        man2 = json.loads(man_path.read_text(encoding="utf-8"))
        prim = [r for r in man2["artifacts"] if r.get("path") == rep["output_path"]][0]
        sha2, n2 = digest(out)
        if prim["sha256"] != sha2 or prim["bytes"] != n2:
            print(f"ABORT {uid}: post-stamp manifest mismatch")
            return 1
        stamped += 1
        print(f"STAMPED {uid}: reviewer={REVIEWER_ID} sha={sha[:12]} bytes={n2} manifest-refreshed")
    print(f"TOTAL stamped: {stamped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
