#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0317.json from live persist/scan/retention runs."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.council.artifacts.retention import (  # noqa: E402
    PersistenceRefused,
    RetentionPolicy,
    apply_retention,
    persist_transcript,
)
import corpus as C  # noqa: E402
import gitleaks_style as G  # noqa: E402

OUT = "command-center/receipts/IMP-0317.json"
MODULE = "tools/council/artifacts/retention.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0317/probe1_planted_zero_survivors.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0317/probe2_negative_control.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_measure() -> dict:
    out: dict = {}
    with tempfile.TemporaryDirectory(prefix="imp0317-emit-") as td:
        root = Path(td)
        clean = root / "clean" / "transcript.json"
        dirty = root / "dirty" / "transcript.json"
        meta = persist_transcript(
            C.transcript(),
            clean,
            RetentionPolicy(redact=True, refuse_if_survivors=True),
        )
        clean_surv = C.survivor_kinds(clean.read_bytes())
        clean_gl = G.scan_dir(clean.parent)
        persist_transcript(
            C.transcript(),
            dirty,
            RetentionPolicy(
                redact=False,
                refuse_if_survivors=False,
                allow_unredacted_for_test=True,
            ),
        )
        dirty_surv = C.survivor_kinds(dirty.read_bytes())
        dirty_gl = G.scan_dir(dirty.parent)
        dirty_rules = sorted({h["rule_id"] for h in dirty_gl})
        refused = False
        try:
            persist_transcript(
                C.transcript(),
                root / "refused.json",
                RetentionPolicy(redact=False, allow_unredacted_for_test=False),
            )
        except PersistenceRefused:
            refused = True
        now = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
        store = root / "retain"
        store.mkdir()
        ttl = RetentionPolicy(redact=True, retention_seconds=60)
        persist_transcript(
            {"schema": "council-transcript/v1", "turns": [{"text": "no secrets"}]},
            store / "expired.json",
            ttl,
            now=now - timedelta(seconds=120),
        )
        persist_transcript(
            {"schema": "council-transcript/v1", "turns": [{"text": "no secrets"}]},
            store / "fresh.json",
            ttl,
            now=now,
        )
        ret = apply_retention(store, ttl, now=now)
        out = {
            "clean_bytes": meta["bytes"],
            "clean_sha256": meta["sha256"],
            "clean_survivors": clean_surv,
            "clean_survivor_count": len(clean_surv),
            "clean_gitleaks_hits": len(clean_gl),
            "dirty_survivors": dirty_surv,
            "dirty_survivor_count": len(dirty_surv),
            "dirty_gitleaks_hits": len(dirty_gl),
            "dirty_gitleaks_rules": dirty_rules,
            "production_unredacted_refused": refused,
            "retention_expired_deleted": not (store / "expired.json").exists(),
            "retention_fresh_kept": (store / "fresh.json").exists(),
            "retention_deleted_count": len(ret["deleted"]),
            "redaction_applied_on_shipped_path": meta["redaction_applied"] is True,
        }
    return out


def main() -> int:
    m = live_measure()
    if m["clean_survivor_count"] != 0 or m["clean_gitleaks_hits"] != 0:
        print("FAILED:IMP-0317 emit clean persist still has survivors/hits", m)
        return 1
    if m["dirty_survivor_count"] != 4 or set(m["dirty_survivors"]) != set(C.ENCODINGS):
        print("FAILED:IMP-0317 emit dirty persist missed encodings", m)
        return 1
    need = {
        "env-assignment",
        "json-password",
        "camelcase-apikey",
        "base64-assignment",
    }
    if not need.issubset(set(m["dirty_gitleaks_rules"])):
        print("FAILED:IMP-0317 emit gitleaks rules incomplete", m)
        return 1
    if not m["production_unredacted_refused"]:
        print("FAILED:IMP-0317 emit production unredacted persist was allowed")
        return 1
    if not m["retention_expired_deleted"] or not m["retention_fresh_kept"]:
        print("FAILED:IMP-0317 emit retention did not discriminate", m)
        return 1
    if not m["redaction_applied_on_shipped_path"]:
        print("FAILED:IMP-0317 emit redactor not on shipped persist path")
        return 1

    mod_sha, mod_bytes = sha256_file(REPO / MODULE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "IMP-0317",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0317",
        "completion_sentinel": "SUCCESS:IMP-0317",
        "title": "Privacy, retention and persistence policy engine",
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-privacy-module"
        ),
        "spec_anchor": (
            "_USER-PROMPTS.md:11298-11347; _USER-PROMPTS.md:11345 "
            "(credentials or decrypted secrets must not enter an artifact bundle); "
            "11-COUNCIL-SPECIFICATION artifacts/privacy/persistence; "
            "catalog IMP-0317 question_or_target"
        ),
        "min_bytes_threshold": 2048,
        "artifact_paths": [
            OUT,
            MODULE,
            "tools/council/artifacts/__init__.py",
            "command-center/p2-wave/probes/IMP-0317/probe1_planted_zero_survivors.py",
            "command-center/p2-wave/probes/IMP-0317/probe2_negative_control.py",
            "command-center/p2-wave/probes/IMP-0317/gitleaks_style.py",
        ],
        "module": {
            "path": MODULE,
            "sha256": mod_sha,
            "bytes": mod_bytes,
            "hard_rule": (
                "no credential or decrypted secret enters a persisted council artifact"
            ),
            "encodings": list(C.ENCODINGS),
            "persist_refuses_survivors": True,
            "unredacted_requires_explicit_test_flag": True,
        },
        "falsifiable_question": (
            "does a secret pasted into a participant turn reach the persisted "
            "artifact, and does the redactor handle JSON-embedded and camelCase "
            "key forms as well as plain assignments?"
        ),
        "answer": (
            "No: persist_transcript redacts before write and refuses if any of "
            "the four planted encodings survive. Disable the redactor (test flag "
            "only) and the same scanners find all four, so silence on the clean "
            "artifact is not a dead scanner. Declared retention deletes the "
            "expired file and keeps the in-window file."
        ),
        "live": m,
        "evidence": [
            {
                "id": "planted-secret-corpus",
                "claim": (
                    "Planted corpus (env-style, JSON-embedded, camelCase, base64) "
                    "scanned in the persisted artifact after redaction; required "
                    "zero survivors."
                ),
                "verdict": "CONFIRMED",
                "survivors": m["clean_survivor_count"],
                "encodings_checked": list(C.ENCODINGS),
                "survivor_kinds": m["clean_survivors"],
                "redaction_applied": True,
                "shipped_path": "tools.council.artifacts.retention.persist_transcript",
                "anchor": MODULE,
            },
            {
                "id": "independent-gitleaks-style-scan",
                "claim": (
                    "An independent gitleaks-style scanner (command-center/p2-wave/"
                    "probes/IMP-0317/gitleaks_style.py) of the same artifact "
                    "directory reports 0 hits on the redacted persist and fires "
                    "all four rule ids on the unredacted persist."
                ),
                "verdict": "CONFIRMED",
                "clean_hits": m["clean_gitleaks_hits"],
                "dirty_hits": m["dirty_gitleaks_hits"],
                "dirty_rule_ids": m["dirty_gitleaks_rules"],
                "anchor": "command-center/p2-wave/probes/IMP-0317/gitleaks_style.py",
                "mechanically_different_from_redactor": True,
            },
        ],
        "test_ids": [
            "security-planted-secret-corpus-four-encodings",
            "negative-control-disable-redactor",
            "retention-expired-deletes-fresh-kept",
            "production-unredacted-persist-refused",
        ],
        "negative_control_ids": [
            "disable-redactor-all-four-found",
            "gitleaks-fires-on-dirty-silent-on-clean",
            "expired-artifact-deleted",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0317-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": (
                "tests (planted corpus + disabled redactor), not the author summary"
            ),
            "notes": (
                "Probe 2 treats retention.py as a black box: it plants the four "
                "catalog encodings, disables the redactor, and asserts the "
                "scanner is not silently passing. It does not grant the owner half."
            ),
        },
        "owner_signoff": {
            "required": True,
            "block_present": True,
            "reviewer_granted_owner_half": False,
            "hard_rule": (
                "no credential or decrypted secret enters a council artifact"
            ),
            "hard_rule_source": "_USER-PROMPTS.md:11345 / catalog IMP-0317",
            "policy_defaults_disclosed": {
                "retention_seconds": 2592000,
                "persistence": "redacted-only",
                "redact": True,
            },
            "status": "RECORDED",
            "note": (
                "Owner half is this structured block. The reviewer must not and "
                "did not grant it. Fail-closed defaults implement the spec hard "
                "rule; they do not invent an owner-chosen retention window beyond "
                "the disclosed 30-day default."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "A separate human reviewer in a vendor-fresh context was not "
                    "seated on this worktree; G-1 uses the named adversarial probe "
                    "that starts from the tests."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Seat an independent reviewer who did not author retention.py "
                    "and starts from probe1/probe2, not this receipt."
                ),
            },
            {
                "claim": (
                    "Owner may choose a retention window other than the disclosed "
                    "30-day default."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record the owner's retention_seconds in OWNER-DECISIONS.md "
                    "and re-run apply_retention against that value."
                ),
            },
            {
                "claim": (
                    "gitleaks binary (external) was not invoked; the independent "
                    "scan is a stdlib gitleaks-style rule table."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If a gitleaks binary is present, run it on the same dirty and "
                    "clean artifact directories and compare rule hits."
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "planted-zero-survivors", "command": P1},
            {"id": "probe2", "role": "negative-control-and-retention", "command": P2},
        ],
        "timestamps": {"ended_at": now},
        "cloud_ok": False,
        "registered": True,
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "a live credential was scanned (corpus is synthetic only)",
                "external gitleaks binary executed",
            ]
        },
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha, size = sha256_file(dest)
    if size < 2048:
        print(f"FAILED:IMP-0317 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0317")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
