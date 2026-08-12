"""Phase 14: verify the artifact manifest ON DISK.

Two independent signals per path:
  (a) os.stat size + sha256 of the working-tree bytes as they sit on disk
  (b) sha256 of the SAME bytes with CRLF normalized to LF (the git-blob form)
Reporting both defeats the CRLF trap: a mismatch in (a) that vanishes in (b) is a
line-ending artifact, not a content drift.

Detector control: we deliberately probe a KNOWN-ABSENT path and a KNOWN-PRESENT path
and assert the detector distinguishes them, before trusting any "present" verdict.
"""
import hashlib
import json
import os
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
CC = os.path.join(REPO, "command-center")
MANIFEST = os.path.join(CC, "ARTIFACT-MANIFEST.json")


def sha_pair(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    lf = raw.replace(b"\r\n", b"\n")
    return (
        len(raw),
        hashlib.sha256(raw).hexdigest(),
        len(lf),
        hashlib.sha256(lf).hexdigest(),
    )


def main():
    out = {"probe": "manifest-verify-on-disk", "detector_control": {}, "entries": []}

    # ---- DETECTOR CONTROL (rule 3b: prove it fires on known-broken) ----
    known_present = MANIFEST
    known_absent = os.path.join(CC, "THIS-FILE-DOES-NOT-EXIST-p14-control.json")
    out["detector_control"] = {
        "known_present_path": known_present,
        "known_present_detected": os.path.isfile(known_present),
        "known_absent_path": known_absent,
        "known_absent_detected": os.path.isfile(known_absent),
    }
    ctl = out["detector_control"]
    if not (ctl["known_present_detected"] and not ctl["known_absent_detected"]):
        out["detector_control"]["verdict"] = "DETECTOR BROKEN - refusing to report"
        print(json.dumps(out, indent=2))
        return 2
    out["detector_control"]["verdict"] = "OK: distinguishes present from absent"

    man = json.load(open(MANIFEST, encoding="utf-8"))
    out["manifest_self_claims"] = {
        "expected": man.get("expected"),
        "present": man.get("present"),
        "verified_on_disk": man.get("verified_on_disk"),
        "contract": man.get("contract"),
        "derivation": man.get("derivation"),
        "n_entries_actually_listed": len(man.get("artifacts", [])),
    }

    n_missing = 0
    n_raw_match = 0
    n_lf_match = 0
    n_no_match = 0
    for a in man.get("artifacts", []):
        rel = a["path"]
        p = os.path.join(REPO, rel)
        e = {
            "path": rel,
            "manifest_bytes": a.get("bytes"),
            "manifest_sha256": a.get("sha256"),
            "manifest_present_claim": a.get("present"),
        }
        if not os.path.isfile(p):
            e["on_disk"] = "ABSENT"
            e["verdict"] = "MISSING"
            n_missing += 1
            out["entries"].append(e)
            continue
        raw_n, raw_h, lf_n, lf_h = sha_pair(p)
        e["on_disk"] = "PRESENT"
        e["disk_bytes_raw"] = raw_n
        e["disk_bytes_lf"] = lf_n
        e["disk_sha256_raw"] = raw_h
        e["disk_sha256_lf"] = lf_h
        if a.get("sha256") == "(self)":
            e["verdict"] = "SELF (manifest cannot hash itself)"
        elif a.get("sha256") == raw_h:
            e["verdict"] = "MATCH (working-tree bytes)"
            n_raw_match += 1
        elif a.get("sha256") == lf_h:
            e["verdict"] = "MATCH (LF-normalized bytes) - manifest hashed the LF form"
            n_lf_match += 1
        else:
            e["verdict"] = "SHA MISMATCH - content drifted since the manifest was written"
            e["byte_delta_vs_manifest_raw"] = raw_n - (a.get("bytes") or 0)
            e["byte_delta_vs_manifest_lf"] = lf_n - (a.get("bytes") or 0)
            n_no_match += 1
        out["entries"].append(e)

    out["totals"] = {
        "listed": len(man.get("artifacts", [])),
        "missing_on_disk": n_missing,
        "sha_match_raw": n_raw_match,
        "sha_match_lf": n_lf_match,
        "sha_mismatch": n_no_match,
        "self": sum(1 for e in out["entries"] if e["verdict"].startswith("SELF")),
    }

    # ---- COVERAGE: how much of the produced corpus is registered? ----
    produced = []
    for root, dirs, files in os.walk(CC):
        dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, REPO).replace("\\", "/")
            if f.startswith("_") or f.endswith(".pyc"):
                continue
            produced.append(rel)
    registered = {a["path"] for a in man.get("artifacts", [])}
    out["coverage"] = {
        "command_center_deliverable_files_on_disk": len(produced),
        "registered_in_manifest": len(registered),
        "on_disk_but_UNREGISTERED": sorted(set(produced) - registered),
    }
    out["coverage"]["n_unregistered"] = len(out["coverage"]["on_disk_but_UNREGISTERED"])

    print(json.dumps(out, indent=2))
    with open(os.path.join(CC, "P14-MANIFEST-VERIFY.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
