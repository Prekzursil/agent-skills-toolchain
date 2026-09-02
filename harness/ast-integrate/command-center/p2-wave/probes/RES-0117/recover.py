"""Archive recovery table: snapshot-versus-claim dates and unrecoverable count.

A Wayback snapshot dated AFTER the claim date is not evidence of what was read.
A snapshot dated before the claim is a historical record, not a contemporaneous
read-proof. Same-calendar-day is the only contemporaneous class.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "corpus.json"
ART = REPO / "command-center/research/RES-0117.json"
CAPTURE = REPO / "command-center/p2-wave/probes/RES-0027/snapshots/CAPTURE.json"
SENTINEL = (
    "SUCCESS:RES-0117 in the receipt AND a recovery table with "
    "snapshot-versus-claim date comparison and a count of unrecoverable links"
)
UNIT = "RES-0117"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

AFTER = "SNAPSHOT-AFTER-CLAIM"
BEFORE = "SNAPSHOT-BEFORE-CLAIM"
SAME = "SNAPSHOT-SAME-DAY"
NONE = "NO-SNAPSHOT"


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    p = path or CORPUS
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("links"), list):
        raise SystemExit("FAILED:RES-0117 corpus missing links")
    return doc


def parse_claim_date(value: str) -> date:
    text = str(value or "").strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    return datetime.strptime(text[:10], "%Y-%m-%d").date()


def parse_cdx_timestamp(ts: str) -> date:
    raw = str(ts or "").strip()
    if len(raw) < 8 or not raw[:8].isdigit():
        raise ValueError(f"bad CDX timestamp {ts!r}")
    return datetime.strptime(raw[:8], "%Y%m%d").date()


def date_relation(snapshot: date, claim: date) -> str:
    if snapshot > claim:
        return AFTER
    if snapshot == claim:
        return SAME
    return BEFORE


def historical_usable(relation: str) -> bool:
    return relation in {BEFORE, SAME}


def contemporaneous(relation: str) -> bool:
    return relation == SAME


def after_claim_mismatch(relation: str) -> bool:
    """Catalog evidence rule: post-claim snapshot proves nothing about what was read."""
    return relation == AFTER


def wayback_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{original}"


def cdx_rows(link: dict[str, Any]) -> list[list[str]]:
    rows = link.get("cdx") or []
    if not isinstance(rows, list):
        return []
    out: list[list[str]] = []
    for row in rows:
        if isinstance(row, list) and len(row) >= 3 and str(row[0]).isdigit():
            out.append([str(x) for x in row])
    return out


def pick_closest_on_or_before(rows: list[list[str]], claim: date) -> list[str] | None:
    best: list[str] | None = None
    best_date: date | None = None
    for row in rows:
        snap = parse_cdx_timestamp(row[0])
        if snap <= claim and (best_date is None or snap > best_date):
            best = row
            best_date = snap
    return best


def pick_closest_any(rows: list[list[str]], claim: date) -> list[str] | None:
    if not rows:
        return None
    return min(rows, key=lambda r: abs((parse_cdx_timestamp(r[0]) - claim).days))


def live_resolves(link: dict[str, Any]) -> bool:
    live = link.get("live") or {}
    if not isinstance(live, dict):
        return False
    if live.get("ok") is True and live.get("http_status") == 200:
        return True
    status = live.get("http_status")
    return isinstance(status, int) and 200 <= status < 400


def recovery_row(link: dict[str, Any]) -> dict[str, Any]:
    claim = parse_claim_date(str(link.get("claim_date") or ""))
    rows = cdx_rows(link)
    on_or_before = pick_closest_on_or_before(rows, claim)
    closest = pick_closest_any(rows, claim)
    chosen = on_or_before or closest
    if chosen is None:
        relation = NONE
        snap_date = None
        archive_url = None
        snap_status = None
        snap_digest = None
        snap_ts = None
        original = None
    else:
        snap_ts = chosen[0]
        original = chosen[1]
        snap_status = chosen[2]
        snap_digest = chosen[3] if len(chosen) > 3 else None
        snap_date = parse_cdx_timestamp(snap_ts)
        relation = date_relation(snap_date, claim)
        archive_url = wayback_url(snap_ts, original)

    live_ok = live_resolves(link)
    unrecoverable = (not live_ok) and relation == NONE
    final = str((link.get("live") or {}).get("final_url") or "")
    moved = live_ok and final not in ("", str(link.get("url") or ""))
    if unrecoverable:
        recovery_class = "UNRECOVERABLE"
    elif live_ok and moved:
        recovery_class = "RECOVERED-LIVE-REDIRECT"
    elif live_ok:
        recovery_class = "LIVE"
    else:
        recovery_class = "RECOVERED-ARCHIVE-ONLY"

    return {
        "id": link.get("id"),
        "url": link.get("url"),
        "cited_by": list(link.get("cited_by") or []),
        "claim_date": claim.isoformat(),
        "claim_date_source": link.get("claim_date_source"),
        "planted_control": bool(link.get("planted_control")),
        "live_ok": live_ok,
        "live_http_status": (link.get("live") or {}).get("http_status"),
        "live_final_url": (link.get("live") or {}).get("final_url"),
        "live_error": (link.get("live") or {}).get("error"),
        "live_fetched_at": (link.get("live") or {}).get("fetched_at"),
        "cdx_row_count": len(rows),
        "snapshot_timestamp": snap_ts,
        "snapshot_date": snap_date.isoformat() if snap_date else None,
        "snapshot_original": original,
        "snapshot_statuscode": snap_status,
        "snapshot_digest": snap_digest,
        "snapshot_archive_url": archive_url,
        "snapshot_on_or_before_claim": on_or_before[0] if on_or_before else None,
        "snapshot_vs_claim": relation,
        "days_snapshot_minus_claim": (
            (snap_date - claim).days if snap_date is not None else None
        ),
        "after_claim_mismatch": after_claim_mismatch(relation),
        "historical_record_usable": historical_usable(relation),
        "contemporaneous_read_proof": contemporaneous(relation),
        "recovery_class": recovery_class,
        "unrecoverable": unrecoverable,
        "conclusion_currently_resting": link.get("conclusion_currently_resting"),
        "recovered_artifact_changes_conclusion": False,
        "strongest_caveat": caveat_for(relation, recovery_class, live_ok),
    }


def caveat_for(relation: str, recovery_class: str, live_ok: bool) -> str:
    if relation == NONE and not live_ok:
        return (
            "No Wayback CDX row and live fetch did not resolve. "
            "Counted as unrecoverable; no archival substitute exists."
        )
    if relation == AFTER:
        return (
            "Closest snapshot is AFTER the claim date. Per 05-ECO section 6 / "
            "this unit's evidence_requirement, it proves nothing about what was read."
        )
    if relation == BEFORE:
        return (
            "Closest snapshot is BEFORE the claim date. It is a historical record, "
            "not a contemporaneous proof of the bytes read when the claim was made."
        )
    if relation == SAME:
        return "Snapshot calendar date matches the claim date."
    if live_ok:
        return (
            "Live fetch followed a host change. Content still exists at the final URL; "
            "the original cited host is no longer the canonical location."
        )
    return "dated comparison recorded"


def hub_capture_errors() -> list[str]:
    if not CAPTURE.is_file():
        return ["RES-0027 CAPTURE.json missing"]
    cap = json.loads(CAPTURE.read_text(encoding="utf-8"))
    errs: list[str] = []
    dns = (cap.get("dns") or {}).get("hub.continue.dev") or {}
    if dns.get("ok") is not False:
        errs.append("CAPTURE dns.hub.continue.dev.ok is not false")
    failed = cap.get("failed_fetches") or []
    if not any(
        isinstance(x, dict) and "hub.continue.dev" in str(x.get("permalink") or "")
        for x in failed
    ):
        errs.append("CAPTURE failed_fetches missing hub.continue.dev")
    return errs


def build_recovery_table(corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = corpus if corpus is not None else load_corpus()
    return [recovery_row(link) for link in doc["links"] if isinstance(link, dict)]


def unrecoverable_rows(table: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in table if r.get("unrecoverable") is True]


def live_control_ok(corpus: dict[str, Any] | None = None) -> bool:
    doc = corpus if corpus is not None else load_corpus()
    live = (doc.get("live_control") or {}).get("live") or {}
    return live.get("ok") is True and live.get("http_status") == 200


def after_claim_synthetic_rejected() -> bool:
    """Probe-2 control: a snapshot dated after the claim must not settle the read."""
    rel = date_relation(date(2026, 8, 20), date(2026, 8, 6))
    return (
        after_claim_mismatch(rel)
        and not contemporaneous(rel)
        and not historical_usable(rel)
    )


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    p = path or ART
    if not p.is_file() or p.stat().st_size <= 0:
        raise SystemExit("FAILED:RES-0117 artifact missing")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:RES-0117 artifact not an object")
    return doc


def artifact_errors(doc: dict[str, Any], table: list[dict[str, Any]]) -> list[str]:
    errs: list[str] = []
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        errs.append("catalog-sentinel-absent")
    if "SUCCESS:RES-0117" not in blob:
        errs.append("short-sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        errs.append(f"self-declared:{st}")
    if str(doc.get("unit_id") or "") != UNIT:
        errs.append("unit_id")
    art_table = doc.get("recovery_table")
    if not isinstance(art_table, list) or len(art_table) != len(table):
        errs.append(f"recovery_table-len {type(art_table).__name__}")
        return errs
    by_id = {r.get("id"): r for r in table}
    for row in art_table:
        if not isinstance(row, dict):
            errs.append("row-not-object")
            continue
        rid = row.get("id")
        exp = by_id.get(rid)
        if not exp:
            errs.append(f"unknown-row:{rid}")
            continue
        for key in (
            "claim_date",
            "snapshot_date",
            "snapshot_vs_claim",
            "after_claim_mismatch",
            "unrecoverable",
            "recovery_class",
            "days_snapshot_minus_claim",
        ):
            if row.get(key) != exp.get(key):
                errs.append(
                    f"{rid}:{key} artifact={row.get(key)!r} recomputed={exp.get(key)!r}"
                )
    counted = doc.get("unrecoverable_link_count")
    live_count = len(unrecoverable_rows(table))
    if counted != live_count:
        errs.append(
            f"unrecoverable_link_count artifact={counted} recomputed={live_count}"
        )
    if live_count < 1:
        errs.append("unrecoverable-count-zero-control-missing")
    planted = [r for r in table if r.get("planted_control") and r.get("unrecoverable")]
    if not planted:
        errs.append("planted-unrecoverable-control-missing")
    if doc.get("recovered_artifact_changes_any_conclusion") is True:
        errs.append("overclaim-conclusion-changed")
    return errs
