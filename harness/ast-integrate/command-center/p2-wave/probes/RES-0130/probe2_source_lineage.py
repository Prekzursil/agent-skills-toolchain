#!/usr/bin/env python3
"""Named probe 2: independent source-lineage rehash + needle audit.

Does not call harness.install. Settles load-bearing claims by re-hashing
frozen upstream bytes and requiring cited resolver functions / error strings
to be present in those bytes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/marketplace-ecosystem/RES-0130-lockfile-resolution-under-revocation.json"
SRC = HERE / "snapshots" / "SOURCES.json"
UNIT = "RES-0130"

NEEDLES = (
    ("ssri-index.js", "function checkData"),
    ("ssri-index.js", "Integrity checksum failed when using"),
    ("ssri-index.js", "EINTEGRITY"),
    ("cargo-download.rs", "fn finish_download"),
    ("cargo-download.rs", "failed to verify the checksum"),
    ("cargo-yank.md", "does not delete any data"),
    ("cargo-yank.md", "Existing lock"),
    ("cargo-resolver.html", "already exist in the"),
    ("poetry-executor.py", "def _validate_archive_hash"),
    ("poetry-executor.py", "not found in"),
    ("poetry-executor.py", "known hashes (was:"),
    ("poetry-executor.py", "is yanked."),
    ("pnpm-pr-11968.diff", "ERR_PNPM_TARBALL_INTEGRITY"),
    ("pnpm-pr-11968.diff", "Got unexpected checksum"),
    ("pnpm-pr-11968.diff", "TarballIntegrityError"),
    ("pnpm-install.html", "pnpm i --offline"),
    ("nix-fetchers.cc", "NAR hash mismatch in input"),
    ("nix-fetchers.cc", "getNarHash"),
    ("nix-flake-format.html", "narHash"),
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    if not SRC.is_file() or not ART.is_file():
        print("FAILED:RES-0130-probe2 missing sources or artifact")
        return 1
    index = json.loads(SRC.read_text(encoding="utf-8"))
    art_text = ART.read_text(encoding="utf-8")
    doc = json.loads(art_text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:RES-0130-probe2 unit_id")
        return 1
    if "SUCCESS:RES-0130" not in art_text:
        print("FAILED:RES-0130-probe2 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0130-probe2 self-declared", doc.get("state"))
        return 1

    by_file = {}
    for row in index.get("sources") or []:
        if not row.get("ok"):
            print("FAILED:RES-0130-probe2 source not ok", row.get("file"))
            return 1
        rel = row["path"]
        path = REPO / rel
        raw = path.read_bytes()
        live = hashlib.sha256(raw).hexdigest()
        if live != row.get("sha256"):
            print("FAILED:RES-0130-probe2 snapshot-sha-drift", row["file"], live, row.get("sha256"))
            return 1
        by_file[row["file"]] = {"row": row, "text": raw.decode("utf-8", errors="replace")}

    missing_needles = []
    for fname, needle in NEEDLES:
        blob = by_file.get(fname, {}).get("text") or ""
        if needle not in blob:
            missing_needles.append(f"{fname}:{needle}")
    if missing_needles:
        print("FAILED:RES-0130-probe2 needles-absent", missing_needles)
        return 1

    claims = doc.get("claims") or []
    if len(claims) < 5:
        print("FAILED:RES-0130-probe2 too-few-claims", len(claims))
        return 1
    sha_ok = 0
    for claim in claims:
        lin = claim.get("source_lineage") or {}
        if not isinstance(lin, dict):
            print("FAILED:RES-0130-probe2 lineage-missing", claim.get("claim_id"))
            return 1
        sha = lin.get("sha256")
        if sha not in {r["row"]["sha256"] for r in by_file.values()}:
            print("FAILED:RES-0130-probe2 lineage-sha-not-in-snapshots", claim.get("claim_id"))
            return 1
        band = str(claim.get("confidence_band") or "")
        if band not in {
            "almost-certain",
            "likely",
            "roughly-even",
            "unlikely",
            "remote",
        }:
            print("FAILED:RES-0130-probe2 band", claim.get("claim_id"), band)
            return 1
        if not claim.get("independent_verification_path"):
            print("FAILED:RES-0130-probe2 verification-path-missing", claim.get("claim_id"))
            return 1
        sha_ok += 1

    # Overclaim control: reconstructed 404 codes must be labeled reconstructed,
    # not presented as copied from arborist source.
    recon = doc.get("reconstructed_missing_artifact_strings") or {}
    if recon.get("copied_from_resolver_source") is not False:
        print("FAILED:RES-0130-probe2 reconstructed-strings-overclaimed")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-source-lineage",
        "unit_id": UNIT,
        "snapshots_rehashed": len(by_file),
        "needles_confirmed": len(NEEDLES),
        "claims_lineage_ok": sha_ok,
        "independence_class": "sha256-rehash-of-frozen-upstream-bytes-plus-substring-needles",
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"rehashed={len(by_file)} needles={len(NEEDLES)} claims={sha_ok}")
    print("SUCCESS:RES-0130-probe2 source lineage and resolver needles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
