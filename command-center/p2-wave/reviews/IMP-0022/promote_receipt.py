#!/usr/bin/env python3
"""IMP-0022 reviewer promotion: merge the independent reviewer block into the receipt.

Preserves every existing field; replaces only `reviewer` (the implementer's
NOT-REVIEWED self-assessment is retained inside the new block as
prior_implementer_* so no information is lost). Validates the C5 content floor
and falsification-regex expectations from rail_count_gate.py BEFORE writing.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0022.json"

NOTES = (
    "Fresh-context independent review on Windows/NTFS (CPython 3.14.6). "
    "Falsification attempted with discriminating pairs where lower() and "
    "casefold() disagree: 'STRASSE.md' vs 'Straße.md' (control: lower gives "
    "'strasse.md' vs 'straße.md', i.e. lower MISSES) -- implementation "
    "find_casefold_collisions returned collision_group_count=1, key='strasse.md', "
    "paths=['STRASSE.md','Straße.md'], keys of both inputs = 'strasse.md'; "
    "'file-σ.md' vs 'file-ς.md' (sigma vs final sigma; lower MISSES) -- "
    "group_count=1, key='file-σ.md'. NFC applied: NFD 'Café.md' vs NFC "
    "'café.md' -- keys both 'café.md', group formed over NFC-normalised "
    "exacts; 'ẛ.md' vs 'ẛ.md' -- keys both 'ṡ.md' (NFC composed "
    "U+017F+U+0307 to U+1E9B before casefold; a no-NFC key would yield 'ṡ.md' "
    "and differ). NFC-before-casefold ORDER anchored in code at "
    "tools/plugin/casefold_paths.py:88-95 (nfc_path() then .casefold()); on this "
    "build full folding commutes with composition (verified premise), so no "
    "behavioral order claim is made -- the counter-example hunt is in "
    "command-center/p2-wave/reviews/IMP-0022/casefold-nfc-discrimination.raw.txt "
    "(24/24 checks PASS). Negative controls: exact-duplicate dedupe (README.md x2 "
    "=> group of exactly 2), clean set 0 groups. Packer pre-emit refusal re-proven "
    "on NTFS via an index-built colliding git tree (tools/plugin/pack.py:271-275): "
    "PackError named both paths, no zip emitted. Unit probes rerun green here, "
    "including catalog signal (2) on a real case-insensitive filesystem: NTFS "
    "extraction of the planted zip gave archive_entry_count=2, "
    "extracted_file_count=1, shortfall=1 (settles the Linux worker's "
    "missing-CI-FS-substrate block; reviews/IMP-0022/probe2-ci-fs-extract.raw.txt). "
    "pytest 4/5 on NTFS: test_packer_refuses_planted_case_collision is "
    "substrate-blocked (its own comment assumes Linux coexistence; on NTFS the "
    "second write overwrites -- corroborated: case-variant double-write leaves 1 "
    "name), intent independently confirmed by the index-tree check. Residual (LOW, "
    "APFS-only): NFC-composition variants dedupe as exact duplicates rather than "
    "being flagged. Receipt artifact hashes (2026-09-08 Linux pack) drift from the "
    "live worktree (edits by other lanes); this PASS certifies the live worktree "
    "bytes actually executed."
)

MIN_REVIEW_NOTES = 200
_FALSIFICATION = re.compile(
    r"falsif|refut|mutat|counter-?example|tried to break|both[- ]states"
    r"|control|disconfirm|negative case",
    re.I,
)


def main() -> int:
    raw = io.open(RECEIPT, encoding="utf-8").read()
    rec = json.loads(raw)
    prior = rec.get("reviewer") or {}

    # Pre-write validation of everything the C5 gate will check.
    assert len(NOTES) >= MIN_REVIEW_NOTES, len(NOTES)
    assert _FALSIFICATION.search(NOTES), "falsification marker missing"

    new_reviewer = {
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": "claude",
        "reviewer_id": "c5-imp-0022-claude",
        "reviewed_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "notes": NOTES,
        "evidence": [
            "command-center/p2-wave/reviews/IMP-0022/casefold-nfc-discrimination.raw.txt",
            "command-center/p2-wave/reviews/IMP-0022/independent-review.json",
            "command-center/p2-wave/reviews/IMP-0022/probe2-ci-fs-extract.raw.txt",
        ],
        "prior_implementer_verdict": prior.get("verdict"),
        "prior_implementer_notes": prior.get("notes"),
    }
    rec["reviewer"] = new_reviewer

    out = json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    io.open(RECEIPT, "w", encoding="utf-8", newline="\n").write(out)

    # Post-write verification: round-trip + gate conditions.
    back = json.loads(io.open(RECEIPT, encoding="utf-8").read())
    rv = back["reviewer"]
    assert rv["verdict"].upper() == "PASS" and rv["independent"] is True
    assert len(rv["notes"]) >= MIN_REVIEW_NOTES and _FALSIFICATION.search(rv["notes"])
    assert back.get("state") == rec.get("state"), "state must be untouched"
    assert back.get("unit_id") == "IMP-0022"
    print(
        f"SUCCESS:promote-receipt IMP-0022 reviewer=PASS notes_chars={len(rv['notes'])} "
        f"reviewed_at={rv['reviewed_at']} state_preserved={back.get('state')!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
