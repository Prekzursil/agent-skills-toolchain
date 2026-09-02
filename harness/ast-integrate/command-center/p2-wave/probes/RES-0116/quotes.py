"""Shared quote / two-rail / discard checks for RES-0116 probes."""
from __future__ import annotations

from captures_index import capture_text, verify_row
from register import DISCARDED_RETRANSLATIONS, SENTINEL

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
MEASURED = "NO-ENGLISH-EQUIVALENT-IN-CORPUS"


def quotes_ok(doc: dict) -> tuple[bool, str]:
    rows = doc.get("register") or []
    if len(rows) < 4:
        return False, "register too small"
    discarded_n = int(doc.get("discarded_as_translations_of_english_sources") or -1)
    if discarded_n != len(DISCARDED_RETRANSLATIONS):
        return False, f"discard count {discarded_n}"
    for row in rows:
        quote = row.get("original_language_quote") or ""
        if len(quote) < 8:
            return False, f"{row.get('id')} missing original quote"
        if int(row.get("discarded_retranslations_count") or -1) != discarded_n:
            return False, f"{row.get('id')} missing discarded-retranslation count"
        rails = row.get("rails") or []
        found = False
        for rail in rails:
            cid = rail.get("id")
            if cid and quote in capture_text(cid):
                found = True
                break
        sec = row.get("secondary_quote") or ""
        sec_cid = row.get("secondary_quote_capture") or ""
        if sec and sec_cid and sec in capture_text(sec_cid):
            found = True
        if not found:
            return False, f"{row.get('id')} quote not in captures"
        if row.get("verdict") == MEASURED and row.get("evidence_grade") != "E3":
            kinds = {r.get("kind") for r in rails}
            if "api" not in kinds or "prose" not in kinds:
                return False, f"{row.get('id')} needs api+prose rails"
            if len(rails) < 2:
                return False, f"{row.get('id')} single rail graded as measured"
            for rail in rails:
                fake = {
                    "id": rail["id"],
                    "sha256": rail.get("sha256"),
                    "byte_length": rail.get("byte_length"),
                }
                ok, why = verify_row(fake)
                if not ok:
                    return False, why
                if rail.get("http_status") != 200:
                    return False, f"{rail.get('id')} http {rail.get('http_status')}"
                if not rail.get("permalink") or not rail.get("fetch_timestamp"):
                    return False, f"{rail.get('id')} missing permalink/timestamp"
    return True, "ok"


def sentinel_ok(doc: dict, text: str) -> tuple[bool, str]:
    if SENTINEL not in text:
        return False, "sentinel-absent"
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return False, f"self-declared {doc.get('state')}"
    return True, "ok"


def discards_not_promoted(doc: dict) -> tuple[bool, str]:
    promoted = " ".join(
        (r.get("mechanism") or "") + (r.get("claim") or "")
        for r in (doc.get("register") or [])
        if r.get("verdict") == MEASURED
    ).lower()
    for needle in ("autogen", "crewai", "langgraph"):
        if needle in promoted:
            return False, f"english-framework {needle} promoted"
    ids = {d["id"] for d in doc.get("discarded_candidates") or []}
    expected = {d["id"] for d in DISCARDED_RETRANSLATIONS}
    if ids != expected:
        return False, f"discard ids {ids}"
    return True, "ok"
