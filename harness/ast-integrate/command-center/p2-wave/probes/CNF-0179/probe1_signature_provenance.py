#!/usr/bin/env python3
"""Named probe 1: independent OpenSSL signature + provenance both-states.

Mechanically: openssl dgst -verify on the artifact and the in-toto statement,
plus sha256sum/hashlib agreement. Probe 2 reads tar members vs SBOM — a
different field.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from bundle import publish  # noqa: E402
from tools import agree_sha256, openssl_version, sha256sum_version  # noqa: E402
from verify_chain import both_states_signature, provenance_subject_matches, verify_provenance_signature  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0179.json"
FIX = HERE / "fixtures" / "published"


def require_artifact() -> dict:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0179-probe1 receipt missing")
        raise SystemExit(1)
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0179":
        print("FAILED:CNF-0179-probe1 unit_id", doc.get("unit_id"))
        raise SystemExit(1)
    if "SUCCESS:CNF-0179" not in text:
        print("FAILED:CNF-0179-probe1 sentinel absent")
        raise SystemExit(1)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0179-probe1 self-declared {st}")
        raise SystemExit(1)
    return doc


def check_dir(label: str, dest: Path) -> dict:
    artifact = dest / "cnf-0179-published.tar.gz"
    sig = dest / "cnf-0179-published.tar.gz.sig"
    pub = dest / "pubkey.pem"
    prov = dest / "provenance.intoto.json"
    prov_sig = dest / "provenance.intoto.json.sig"
    for p in (artifact, sig, pub, prov, prov_sig):
        if not p.is_file():
            print(f"FAILED:CNF-0179-probe1 {label} missing {p.name}")
            raise SystemExit(1)
    with tempfile.TemporaryDirectory(prefix="cnf0179-p1-mut-") as tmp:
        mutant = Path(tmp) / "mutated.tar.gz"
        states = both_states_signature(pub, artifact, sig, mutant)
    if not states["pass"]:
        print(f"FAILED:CNF-0179-probe1 {label} both-states {json.dumps(states)}")
        raise SystemExit(1)
    prov_ok, prov_text = verify_provenance_signature(pub, prov, prov_sig)
    if not prov_ok:
        print(f"FAILED:CNF-0179-probe1 {label} provenance sig {prov_text}")
        raise SystemExit(1)
    statement = json.loads(prov.read_text(encoding="utf-8"))
    art_sha = agree_sha256(artifact)
    sub_ok, sub_why = provenance_subject_matches(
        statement, art_sha, "cnf-0179-published.tar.gz"
    )
    if not sub_ok:
        print(f"FAILED:CNF-0179-probe1 {label} subject {sub_why}")
        raise SystemExit(1)
    return {
        "label": label,
        "both_states": states,
        "provenance_sig_ok": True,
        "subject_ok": True,
        "artifact_sha256": art_sha,
    }


def main() -> int:
    require_artifact()
    if not (FIX / "cnf-0179-published.tar.gz").is_file():
        print("FAILED:CNF-0179-probe1 published fixture missing")
        return 1
    live = check_dir("fixtures", FIX)
    with tempfile.TemporaryDirectory(prefix="cnf0179-p1-rebuild-") as tmp:
        rebuilt = publish(Path(tmp) / "published")
        indep = check_dir("rebuild", Path(tmp) / "published")
    ov = openssl_version()
    sv = sha256sum_version()
    out = {
        "probe": "probe1-signature-provenance",
        "unit_id": "CNF-0179",
        "openssl_version": ov,
        "sha256sum_version": sv,
        "fixture": live,
        "independent_rebuild": {
            "pubkey_sha256": rebuilt["pubkey_sha256"],
            "artifact_sha256": indep["artifact_sha256"],
            "both_states_pass": indep["both_states"]["pass"],
        },
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0179-probe1 openssl signature both-states and provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
