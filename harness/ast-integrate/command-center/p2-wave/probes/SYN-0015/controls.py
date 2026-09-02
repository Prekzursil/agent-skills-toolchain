"""Fixture controls required by SYN-0015 tests_required."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import scanner as S

HERE = Path(__file__).resolve().parent
KNOWN = HERE / "fixtures" / "known-present"
QUOTED = HERE / "fixtures" / "quoted-mention"
SCOPED = HERE / "fixtures" / "already-scoped"


def _plant_hits(overclaims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits = []
    for row in overclaims:
        sent = str(row.get("sentence") or "")
        q = str(row.get("quantifier") or "").lower()
        if q == "no unit" or "no unit" in sent.lower():
            hits.append(row)
    return hits


def known_present() -> dict[str, Any]:
    scan = S.scan_dir(KNOWN, strip_mentions=True)
    hits = _plant_hits(scan["overclaims"])
    rewrite_ok = False
    measured_ok = False
    if hits:
        row = hits[0]
        rw = str(row.get("corrected_sentence") or "")
        mp = row.get("measured_population") or {}
        rewrite_ok = "12" in rw and "103" in rw and len(rw) >= 12
        measured_ok = mp.get("measured_n") == 12 and mp.get("population_n") == 103
        work_ok = row.get("underlying_work_verdict") == "CONFIRMED"
    else:
        work_ok = False
    ok = len(hits) >= 1 and rewrite_ok and measured_ok and work_ok
    return {
        "ok": ok,
        "overclaim_count": len(scan["overclaims"]),
        "plant_hits": len(hits),
        "rewrite_ok": rewrite_ok,
        "measured_ok": measured_ok,
        "work_confirmed": work_ok,
        "rows": scan["overclaims"],
        "path": scan["path"],
    }


def quoted_mention() -> dict[str, Any]:
    masked = S.scan_dir(QUOTED, strip_mentions=True)
    unmasked = S.scan_dir(QUOTED, strip_mentions=False)
    masked_plants = _plant_hits(masked["overclaims"])
    unmasked_plants = _plant_hits(unmasked["overclaims"])
    ok = len(masked_plants) == 0 and len(unmasked_plants) >= 1
    return {
        "ok": ok,
        "masked_flags": len(masked["overclaims"]),
        "masked_plant_hits": len(masked_plants),
        "unmasked_plant_hits": len(unmasked_plants),
        "mention_mask_is_load_bearing": len(unmasked_plants) >= 1
        and len(masked_plants) == 0,
        "path": masked["path"],
    }


def already_scoped() -> dict[str, Any]:
    scan = S.scan_dir(SCOPED, strip_mentions=True)
    kinds = [f.get("kind") for f in scan["findings"]]
    ok = len(scan["overclaims"]) == 0 and "confirmed-scoped" in kinds
    return {
        "ok": ok,
        "overclaim_count": len(scan["overclaims"]),
        "kinds": kinds,
        "path": scan["path"],
    }


def all_controls() -> dict[str, Any]:
    kp = known_present()
    qm = quoted_mention()
    sc = already_scoped()
    ok = bool(kp["ok"] and qm["ok"] and sc["ok"])
    return {"ok": ok, "known_present": kp, "quoted_mention": qm, "already_scoped": sc}


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report.* once receipt_core additionalProperties is on."""
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and str(rep.get("kind") or "") == "overclaim-scan":
        return rep
    return doc


def flagged_sentences(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = domain(doc).get("flagged_sentences")
    if isinstance(rows, list) and rows:
        return [r for r in rows if isinstance(r, dict)]
    rows = doc.get("flagged_sentences")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def artifact_honesty(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    if str(doc.get("unit_id")) != "SYN-0015":
        return False, "unit_id"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    payload = domain(doc)
    live = payload.get("live_corpus")
    if not isinstance(live, dict):
        return False, "live_corpus-missing"
    try:
        n_files = int(live["files_scanned"])
    except (KeyError, TypeError, ValueError):
        return False, "files_scanned-missing"
    try:
        absent = int(live["absent_outputs"])
    except (KeyError, TypeError, ValueError):
        absent = -1
    if absent < 0:
        return False, "absent_outputs-missing"
    verdict = str(payload.get("verdict") or doc.get("verdict") or "")
    live_verdict = str(payload.get("live_verdict") or doc.get("live_verdict") or "")
    if n_files == 0:
        if verdict == "CONFIRMED":
            return False, "CONFIRMED-on-empty-live-corpus"
        if live_verdict == "CONFIRMED":
            return False, "live_verdict-CONFIRMED-on-empty"
        if str(live.get("verdict")) == "CONFIRMED":
            return False, "live_corpus.verdict-CONFIRMED-on-empty"
    if absent > 0 and verdict == "CONFIRMED":
        return False, "CONFIRMED-while-syntheses-absent"
    if absent > 0 and live_verdict == "CONFIRMED":
        return False, "live_verdict-CONFIRMED-while-syntheses-absent"
    flagged = flagged_sentences(doc)
    if not flagged:
        return False, "flagged_sentences-empty"
    for i, row in enumerate(flagged):
        if not isinstance(row, dict):
            return False, f"flagged[{i}]-not-object"
        rw = str(row.get("corrected_sentence") or "").strip()
        if len(rw) < 12:
            return False, f"flagged[{i}]-rewrite-missing"
        if str(row.get("underlying_work_verdict")) != "CONFIRMED":
            return False, f"flagged[{i}]-work-not-CONFIRMED"
        mp = row.get("measured_population")
        if not isinstance(mp, dict):
            return False, f"flagged[{i}]-measured-missing"
        if "measured_n" not in mp or "population_n" not in mp:
            return False, f"flagged[{i}]-denominator-missing"
        anchor = row.get("receipt_anchor")
        if not isinstance(anchor, dict) or not str(anchor.get("path") or ""):
            return False, f"flagged[{i}]-anchor-missing"
        if str(row.get("classification")) != "overclaim":
            return False, f"flagged[{i}]-not-overclaim"
        if not str(row.get("quantifier") or ""):
            return False, f"flagged[{i}]-quantifier-missing"
        if not str(row.get("asserted_population") or ""):
            return False, f"flagged[{i}]-asserted-missing"
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        counts = doc.get("counts") if isinstance(doc.get("counts"), dict) else None
    if not isinstance(counts, dict):
        return False, "counts-missing"
    try:
        quoted_flags = int(counts["quoted_mention_flags"])
        scoped_flags = int(counts["already_scoped_flags"])
    except (KeyError, TypeError, ValueError):
        return False, "negative-control-counts-missing"
    if quoted_flags != 0:
        return False, "quoted-mention-leaked-into-counts"
    if scoped_flags != 0:
        return False, "already-scoped-leaked-into-counts"
    if int(counts.get("flagged_with_rewrite") or 0) != len(flagged):
        return False, "rewrite-count-drift"
    return True, f"flagged={len(flagged)} live_files={n_files}"
