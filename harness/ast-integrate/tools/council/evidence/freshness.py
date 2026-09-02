"""Per-class evidence freshness windows and transport-layer revalidation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FRESH = "FRESH"
STALE = "STALE"
FIRED = "FIRED"
SILENT = "SILENT"
REVALIDATED = "REVALIDATED"

WINDOWS = {
    "live-url": 3600.0,
    "measurement": 3600.0,
    "executable-proof": 86400.0,
    "documentation": 7 * 86400.0,
    "peer-reviewed": 40 * 86400.0,
    "archive": 365 * 86400.0,
    "anecdote": 1800.0,
}


def window_for(evidence_class: str) -> float:
    return float(WINDOWS.get(str(evidence_class), 3600.0))


def is_stale(anchor: dict[str, Any], now: float) -> bool:
    age = float(now) - float(anchor.get("as_of_unix") or 0)
    return age > window_for(anchor.get("evidence_class") or "")


def age_of(anchor: dict[str, Any], now: float) -> float:
    """Seconds between the anchor's ``as_of_unix`` stamp and ``now``."""
    return float(now) - float(anchor.get("as_of_unix") or 0)


# Age bins (seconds) for the histogram: upper bounds, ascending; the last bin is open.
AGE_BIN_EDGES: tuple[tuple[str, float], ...] = (
    ("<=1h", 3600.0),
    ("<=1d", 86400.0),
    ("<=7d", 7 * 86400.0),
    ("<=30d", 30 * 86400.0),
    ("<=365d", 365 * 86400.0),
)
AGE_BIN_OPEN = ">365d"


def age_bin(age_s: float) -> str:
    for label, upper in AGE_BIN_EDGES:
        if age_s <= upper:
            return label
    return AGE_BIN_OPEN


def age_histogram(anchors: list[dict[str, Any]], now: float) -> dict[str, Any]:
    """Age of every anchor at ``now`` against its class window.

    Returns the stale/fresh id lists and counts, ``n_anchors``, ``age_bins`` (anchor
    count per age bin, every bin present), ``by_class`` (per evidence class: ``n``,
    ``n_stale``, ``n_fresh``, ``window_s``, ``ages_s``, ``stale_ids``) and ``ages``
    (per anchor: class, age, window, stale verdict) so a reader can recompute every
    verdict from the record.
    """
    stale_ids = [a["anchor_id"] for a in anchors if is_stale(a, now)]
    fresh_ids = [a["anchor_id"] for a in anchors if not is_stale(a, now)]
    bins: dict[str, int] = {label: 0 for label, _ in AGE_BIN_EDGES}
    bins[AGE_BIN_OPEN] = 0
    by_class: dict[str, dict[str, Any]] = {}
    ages: list[dict[str, Any]] = []
    for a in anchors:
        cls = str(a.get("evidence_class") or "")
        age_s = age_of(a, now)
        stale = is_stale(a, now)
        bins[age_bin(age_s)] += 1
        row = by_class.setdefault(
            cls,
            {
                "n": 0,
                "n_stale": 0,
                "n_fresh": 0,
                "window_s": window_for(cls),
                "ages_s": [],
                "stale_ids": [],
            },
        )
        row["n"] += 1
        row["n_stale" if stale else "n_fresh"] += 1
        row["ages_s"].append(age_s)
        if stale:
            row["stale_ids"].append(a["anchor_id"])
        ages.append(
            {
                "anchor_id": a.get("anchor_id"),
                "evidence_class": cls,
                "age_s": age_s,
                "window_s": window_for(cls),
                "stale": stale,
            }
        )
    return {
        "stale_ids": stale_ids,
        "fresh_ids": fresh_ids,
        "n_stale": len(stale_ids),
        "n_fresh": len(fresh_ids),
        "n_anchors": len(anchors),
        "decision_at": float(now),
        "age_bins": bins,
        "by_class": by_class,
        "ages": ages,
    }


def load_recorded_council(path: str | Path, sources_root: str | Path | None = None) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    root = Path(sources_root) if sources_root else Path(path).parent / "sources"
    for a in doc.get("anchors") or []:
        uri = a.get("source_uri")
        src = root / uri if uri else None
        if src is not None and src.is_file():
            raw = src.read_bytes()
            a["content_sha256"] = hashlib.sha256(raw).hexdigest()
            a["source_path"] = str(src)
        if "as_of" not in a and "as_of_unix" in a:
            a["as_of"] = a["as_of_unix"]
    return doc


class FileTransport:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.ledger: list[dict[str, Any]] = []

    def read(self, uri: str) -> bytes:
        data = (self.root / uri).read_bytes()
        self.ledger.append(
            {
                "layer": "transport",
                "uri": uri,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        return data


class MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._claimed = False

    def put(self, uri: str, data: bytes) -> None:
        self._store[uri] = data

    def get(self, uri: str) -> bytes:
        self._claimed = True
        return self._store[uri]

    def report(self) -> dict[str, Any]:
        return {"revalidated": True, "layer": "cache", "claimed": self._claimed}


def transport_check(
    transport: FileTransport, uri: str, cache_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    fired = not any(e.get("uri") == uri for e in transport.ledger)
    status = FIRED if fired else SILENT
    return {
        "fired": fired,
        "status": status,
        "cache_report_ignored": True,
        "cache_report": cache_report,
    }


def revalidate_anchor(
    anchor: dict[str, Any],
    now: float,
    *,
    transport: FileTransport,
    reader: MemoryCache | None = None,
) -> dict[str, Any]:
    uri = str(anchor.get("source_uri") or "")
    prior = anchor.get("content_sha256")
    if reader is not None:
        _ = reader.get(uri)
        check = transport_check(transport, uri, cache_report=reader.report())
        return {
            "ok": False,
            "admitted": False,
            "transport_check": FIRED,
            "cache_claimed_revalidation": True,
            "cache_report_ignored": True,
            "content_changed": False,
            "anchor": dict(anchor),
        }
    data = transport.read(uri)
    sha = hashlib.sha256(data).hexdigest()
    restamped = dict(anchor)
    restamped["as_of_unix"] = float(now)
    restamped["content_sha256"] = sha
    restamped["freshness"] = REVALIDATED
    return {
        "ok": True,
        "admitted": True,
        "transport_check": SILENT,
        "cache_claimed_revalidation": False,
        "cache_report_ignored": True,
        "content_changed": sha != prior,
        "anchor": restamped,
    }


def admit_for_binding(
    anchor: dict[str, Any], now: float, revalidation: dict[str, Any] | None = None
) -> dict[str, Any]:
    if revalidation and revalidation.get("ok"):
        return {
            "admitted": True,
            "freshness": REVALIDATED,
            "anchor_id": anchor.get("anchor_id"),
        }
    if is_stale(anchor, now):
        return {"admitted": False, "freshness": STALE, "anchor_id": anchor.get("anchor_id")}
    return {"admitted": True, "freshness": FRESH, "anchor_id": anchor.get("anchor_id")}


def bind_on_fresh_anchors(
    anchors: list[dict[str, Any]],
    now: float,
    *,
    require_all_fresh: bool = False,
    revalidations: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    revalidations = revalidations or {}
    stale_excluded = []
    admitted = []
    for a in anchors:
        rid = a.get("anchor_id")
        rev = revalidations.get(rid)
        if rev and rev.get("ok"):
            admitted.append(rid)
            continue
        if is_stale(a, now):
            stale_excluded.append(rid)
        else:
            admitted.append(rid)
    binding = True
    if require_all_fresh and stale_excluded:
        binding = False
    if stale_excluded and require_all_fresh:
        binding = False
    if not require_all_fresh and stale_excluded and not revalidations:
        binding = False
    if revalidations and all(v.get("ok") for v in revalidations.values()) and not [
        a for a in anchors if is_stale(a, now) and a.get("anchor_id") not in revalidations
    ]:
        binding = True
    if binding:
        refuse_reason = None
    elif stale_excluded:
        refuse_reason = (
            f"{len(stale_excluded)} stale anchor(s) unrevalidated at decision time: "
            + ",".join(str(x) for x in stale_excluded)
        )
    else:
        refuse_reason = "no admitted anchors"
    return {
        "binding": binding,
        "stale_excluded": stale_excluded,
        "admitted": admitted,
        "supporting_anchor_ids": list(admitted),
        "refuse_reason": refuse_reason,
        "n_revalidated": sum(1 for v in revalidations.values() if v.get("ok")),
    }
