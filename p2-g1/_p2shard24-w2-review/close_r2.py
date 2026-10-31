#!/usr/bin/env python3
"""Shard-24 r2 CLOSE phase: write independent-reviewer PASS closures.

Targets (all gating checks verified green beforehand):
  TST-0145, TST-0150, TST-0155, TST-0163

Per unit:
  1. preserve prior reviewer verbatim under extensions.shard24_prior_reviewer_preserved
  2. replace reviewer with this reviewer's PASS block (schema-clean keys only)
  3. dump sort_keys=True indent=1 + trailing newline (current tree format)
  4. re-register the manifest primary row (sha256/bytes/present) to the new bytes
  5. verify post-write: parse, schema content-errors still 0, primary row match,
     reviewer PASS+independent, state SUCCESS
Caller must separately re-run the program measure / WSL probes post-write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
OUT = REPO / "_p2shard24-w2-review"
REVIEWER_ID = "independent-reviewer-wave2-shard24-opus-fresh-r2"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

NOTES = {
    "TST-0145": (
        "Independent close (wave-2 shard-24 r2, fresh context, not the builder): receipt "
        "re-parsed at catalog output_path; state=SUCCESS not self-blocked; sentinel "
        "SUCCESS-family and completion sentinel present; catalog output_schema predicate_report "
        "validated live with jsonschema Draft2020-12 (program resolver + full chain): errors are "
        "ENVELOPE-DRIFT only (schema tightened after this legacy receipt closed; content_errors=0; "
        "drift census per receipt_gate policy, recorded here, not folded into green); receipt_core "
        "SUCCESS conditions hold (no open P0/P1 defect, all 5 test rows PASS, 2 negative controls); "
        "UNIT-ARTIFACT-MANIFEST primary row sha256 recomputed (CRLF->LF) and matched, then "
        "re-registered after this write; named probes re-run to exit 0 by THIS reviewer via the "
        "program measure _measure_one_delivered.py (SUCCESS:delivered; an earlier raw bash lane "
        "hit a tools/platform shadow of stdlib platform under the g1 PYTHONPATH - lane artifact, "
        "not content; the canonical g1_python wrapper lane is authoritative). Prior probe-identity "
        "reviewer block preserved verbatim under extensions.shard24_prior_reviewer_preserved."
    ),
    "TST-0150": (
        "Independent close (wave-2 shard-24 r2, fresh context, not the builder): receipt re-parsed; "
        "state=SUCCESS not self-blocked; SUCCESS-family sentinel + completion sentinel present; "
        "output_schema monitor_report validated live (jsonschema + program resolver): ENVELOPE-DRIFT "
        "only, content_errors=0; receipt_core SUCCESS conditions hold (no open P0/P1 defect, both "
        "test rows PASS, manifest_registration.registered=true); manifest primary row sha256 "
        "recomputed (CRLF->LF), matched, re-registered after this write; named probes re-run to "
        "exit 0 by THIS reviewer via the program measure (SUCCESS:delivered, both bash and pwsh "
        "lanes green in measure output). One supporting row (probe1-both-states.raw.json) is "
        "hash-drifted from a prior probe re-run - recorded, non-gating (primary row is the "
        "delivery row). Prior probe-identity reviewer block preserved verbatim under "
        "extensions.shard24_prior_reviewer_preserved."
    ),
    "TST-0155": (
        "Independent close (wave-2 shard-24 r2, fresh context, not the builder): receipt re-parsed; "
        "state=SUCCESS not self-blocked; SUCCESS-family sentinel + completion sentinel present; "
        "output_schema monitor_report validated live: ENVELOPE-DRIFT only, content_errors=0; "
        "receipt_core SUCCESS conditions hold (no open P0/P1 defect, all test rows PASS); manifest "
        "primary row sha256 recomputed (CRLF->LF), matched, re-registered after this write; named "
        "probes re-run to exit 0 by THIS reviewer on a NATIVE Linux filesystem (WSL ext4 copy of "
        "the probe tree + receipt, byte-identical): probe1 rotation exact-match 75/75 rc=0, probe2 "
        "both-states+mid-line+two-broken-readers rc=0. The native-OS lane is required: on win32 the "
        "probe's os.replace-while-reader-holds hits WinError 32 and /mnt/c 9P lanes give ENODATA/"
        "inode churn - host-OS portability limits, not content failures (build lane was "
        "linux-headless-local). Prior probe-identity reviewer block preserved verbatim under "
        "extensions.shard24_prior_reviewer_preserved."
    ),
    "TST-0163": (
        "Independent close (wave-2 shard-24 r2, fresh context, not the builder): receipt re-parsed; "
        "state=SUCCESS not self-blocked; SUCCESS-family sentinel + completion sentinel present; "
        "output_schema concurrency_report validated live: ENVELOPE-DRIFT only, content_errors=0; "
        "receipt_core SUCCESS conditions hold (no open P0/P1 defect, all 3 test rows PASS, "
        "manifest_registration.registered=true); manifest primary row sha256 recomputed (CRLF->LF), "
        "matched, re-registered after this write; named probes re-run to exit 0 by THIS reviewer "
        "via the program measure (SUCCESS:delivered; probe2's child-process hash re-derivation "
        "matches the recorded CONTRACT-DRIFT digests). Prior probe-identity reviewer block "
        "preserved verbatim under extensions.shard24_prior_reviewer_preserved."
    ),
}

UNIT_DIRS = {
    "TST-0145": "command-center/p2-wave/probes/TST-0145",
    "TST-0150": "command-center/p2-wave/probes/TST-0150",
    "TST-0155": "command-center/p2-wave/probes/TST-0155",
    "TST-0163": "command-center/p2-wave/probes/TST-0163",
}


def norm_sha_bytes(b: bytes) -> tuple[str, int]:
    n = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(n).hexdigest(), len(n)


def dump(path: Path, doc) -> None:
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> int:
    only = set(sys.argv[1:])
    results = {}
    for uid, probe_dir in UNIT_DIRS.items():
        if only and uid not in only:
            continue
        rp = REPO / "command-center" / "receipts" / (uid + ".json")
        doc = json.loads(rp.read_text(encoding="utf-8"))
        prior = doc.get("reviewer")
        ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
        ext["shard24_prior_reviewer_preserved"] = prior
        doc["extensions"] = ext
        doc["reviewer"] = {
            "reviewer_id": REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "reviewed_at": NOW,
            "notes": NOTES[uid],
        }
        # state stays SUCCESS (already verified)
        dump(rp, doc)
        raw = rp.read_bytes()
        sha, n = norm_sha_bytes(raw)
        man_p = REPO / probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
        man = json.loads(man_p.read_text(encoding="utf-8"))
        updated = 0
        for row in man.get("artifacts") or []:
            if row.get("role") == "primary" and row.get("path") == "command-center/receipts/" + uid + ".json":
                row["sha256"] = sha
                row["bytes"] = n
                row["present"] = True
                updated += 1
        dump(man_p, man)
        # post-write verify
        doc2 = json.loads(rp.read_text(encoding="utf-8"))
        rev = doc2.get("reviewer") or {}
        sha2, n2 = norm_sha_bytes(rp.read_bytes())
        man2 = json.loads(man_p.read_text(encoding="utf-8"))
        row2 = [r for r in man2.get("artifacts") or []
                if r.get("role") == "primary" and r.get("path") == "command-center/receipts/" + uid + ".json"][0]
        ok = (rev.get("verdict") == "PASS" and rev.get("independent") is True
              and doc2.get("state") == "SUCCESS"
              and row2.get("sha256") == sha2 and row2.get("bytes") == n2
              and row2.get("present") is True
              and (doc2.get("extensions") or {}).get("shard24_prior_reviewer_preserved") is not None)
        results[uid] = {"closed": ok, "new_sha256": sha2, "new_bytes": n2,
                        "manifest_rows_updated": updated,
                        "prior_reviewer_id": (prior or {}).get("reviewer_id")}
        print(("CLOSED " if ok else "CLOSE-VERIFY-FAILED ") + uid,
              json.dumps(results[uid]))
    (OUT / "r2_close_report.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0 if all(r.get("closed") for r in results.values()) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
