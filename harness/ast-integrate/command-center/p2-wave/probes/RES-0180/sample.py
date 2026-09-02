#!/usr/bin/env python3
"""Live 20-source watchlist sample: two real fetches, no local-body mutation."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree as ET

from watchlist import classify, decide_wake, fingerprint, localname, sha256_bytes

UA = "RES-0180-watchlist/1.0 (research; standing-recheck; +https://pypi.org)"
CTX = ssl.create_default_context()

CANDIDATES: list[dict[str, str]] = [
    {"id": "html-example-com", "url": "https://example.com/"},
    {"id": "html-example-org", "url": "https://example.org/"},
    {"id": "html-python-org", "url": "https://www.python.org/"},
    {"id": "html-pep-8", "url": "https://peps.python.org/pep-0008/"},
    {"id": "html-docs-hashlib", "url": "https://docs.python.org/3/library/hashlib.html"},
    {"id": "plain-rfc7232", "url": "https://www.rfc-editor.org/rfc/rfc7232.txt"},
    {"id": "rel-pip-atom", "url": "https://github.com/pypa/pip/releases.atom"},
    {"id": "rel-cpython-atom", "url": "https://github.com/python/cpython/releases.atom"},
    {"id": "rel-numpy-atom", "url": "https://github.com/numpy/numpy/releases.atom"},
    {"id": "rel-requests-atom", "url": "https://github.com/psf/requests/releases.atom"},
    {"id": "vcs-pip-commits", "url": "https://github.com/pypa/pip/commits/main.atom"},
    {"id": "feed-pypi-updates", "url": "https://pypi.org/rss/updates.xml"},
    {"id": "reg-pypi-pip", "url": "https://pypi.org/pypi/pip/json"},
    {"id": "reg-pypi-requests", "url": "https://pypi.org/pypi/requests/json"},
    {"id": "reg-pypi-packaging", "url": "https://pypi.org/pypi/packaging/json"},
    {"id": "reg-pypi-setuptools", "url": "https://pypi.org/pypi/setuptools/json"},
    {"id": "reg-pypi-wheel", "url": "https://pypi.org/pypi/wheel/json"},
    {"id": "reg-npm-lodash", "url": "https://registry.npmjs.org/lodash/latest"},
    {"id": "reg-crates-serde", "url": "https://crates.io/api/v1/crates/serde"},
    {"id": "plain-pip-readme-pin", "url": "https://raw.githubusercontent.com/pypa/pip/24.2/README.rst"},
    {"id": "html-iana-tz", "url": "https://www.iana.org/time-zones"},
    {"id": "html-pypi-simple-pip", "url": "https://pypi.org/simple/pip/"},
    {"id": "html-pep-508", "url": "https://peps.python.org/pep-0508/"},
    {"id": "rel-setuptools-atom", "url": "https://github.com/pypa/setuptools/releases.atom"},
]

WAYBACK_HTML = [
    "https://example.com/",
    "https://www.python.org/",
    "https://peps.python.org/pep-0008/",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime | None = None) -> str:
    t = ts or utcnow()
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(text: str) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def week_native_events(source_class: str, raw: bytes, now: datetime) -> dict[str, Any]:
    cutoff = now - timedelta(days=7)
    hits: list[str] = []
    if source_class in {"feed", "release", "vcs"}:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            root = None
        if root is not None:
            for el in root.iter():
                if localname(el.tag) not in {"entry", "item"}:
                    continue
                stamp = ""
                eid = ""
                for child in list(el):
                    cn = localname(child.tag)
                    if cn in {"id", "guid"} and (child.text or "").strip():
                        eid = child.text.strip()
                    if cn in {"updated", "published", "pubdate"} and (child.text or "").strip():
                        stamp = stamp or child.text.strip()
                dt = parse_stamp(stamp)
                if dt is not None and dt >= cutoff:
                    hits.append(eid or stamp)
    elif source_class == "registry":
        try:
            doc = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, dict):
            urls = doc.get("urls")
            if isinstance(urls, list):
                for item in urls:
                    if not isinstance(item, dict):
                        continue
                    t = str(item.get("upload_time_iso_8601") or item.get("upload_time") or "")
                    dt = parse_stamp(t.replace(" ", "T"))
                    if dt is not None and dt >= cutoff:
                        hits.append(str(item.get("filename") or t))
            time_npm = doc.get("time")
            if isinstance(time_npm, dict):
                modified = parse_stamp(str(time_npm.get("modified") or ""))
                if modified is not None and modified >= cutoff:
                    hits.append("npm-modified:" + str(doc.get("version") or ""))
    return {
        "window_days": 7,
        "cutoff": iso(cutoff),
        "event_count": len(hits),
        "events_head": hits[:8],
    }


def fetch_one(url: str, timeout: float = 25.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "identity"},
        method="GET",
    )
    t0 = time.time()
    observed = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            raw = resp.read(2_000_000)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            status = int(resp.status)
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        raw = exc.read(65536) if exc.fp else b""
        hdrs = exc.headers.items() if exc.headers else []
        return {
            "ok": False,
            "url": url,
            "error": f"HTTP {exc.code}",
            "status": int(exc.code),
            "elapsed_s": round(time.time() - t0, 3),
            "observed_at": iso(observed),
            "headers": {k.lower(): v for k, v in hdrs},
            "body_sha256": sha256_bytes(raw) if raw else "",
            "bytes": len(raw),
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "status": 0,
            "elapsed_s": round(time.time() - t0, 3),
            "observed_at": iso(observed),
            "headers": {},
            "body_sha256": "",
            "bytes": 0,
        }
    source_class = classify(final, headers.get("content-type", ""), raw)
    fp = fingerprint(source_class, raw, headers, final)
    week = week_native_events(source_class, raw, observed)
    return {
        "ok": True,
        "url": url,
        "final_url": final,
        "status": status,
        "error": "",
        "elapsed_s": round(time.time() - t0, 3),
        "observed_at": iso(observed),
        "headers": {
            "etag": headers.get("etag", ""),
            "last-modified": headers.get("last-modified", ""),
            "date": headers.get("date", ""),
            "content-type": headers.get("content-type", ""),
        },
        "source_class": source_class,
        "fingerprint": fp,
        "week_native": week,
        "body_sha256": fp["raw_sha256"],
        "bytes": len(raw),
    }


def fetch_round() -> list[dict[str, Any]]:
    rows = []
    for spec in CANDIDATES:
        row = fetch_one(spec["url"])
        row["id"] = spec["id"]
        rows.append(row)
    return rows


def summarize_fetch(row: dict[str, Any]) -> dict[str, Any]:
    fp = row.get("fingerprint") or {}
    return {
        "id": row.get("id"),
        "ok": row.get("ok"),
        "url": row.get("url"),
        "final_url": row.get("final_url") or row.get("url"),
        "status": row.get("status"),
        "error": row.get("error") or "",
        "observed_at": row.get("observed_at"),
        "source_class": row.get("source_class"),
        "etag": (row.get("headers") or {}).get("etag", ""),
        "last_modified": (row.get("headers") or {}).get("last-modified", ""),
        "date_header": (row.get("headers") or {}).get("date", ""),
        "content_type": (row.get("headers") or {}).get("content-type", ""),
        "bytes": row.get("bytes"),
        "body_sha256": row.get("body_sha256") or fp.get("raw_sha256"),
        "wake_signal": fp.get("wake_signal"),
        "wake_value": fp.get("wake_value"),
        "registry_version": fp.get("registry_version"),
        "entry_id_count": len(fp.get("entry_ids") or []),
        "release_tag_count": len(fp.get("release_tags") or []),
        "week_native": row.get("week_native") or {},
    }


def pair_rows(r1: dict[str, Any], r2: dict[str, Any]) -> dict[str, Any]:
    if not r1.get("ok") or not r2.get("ok"):
        return {"id": r1.get("id") or r2.get("id"), "paired": False, "reason": "fetch-failed"}
    decision = decide_wake(r1["fingerprint"], r2["fingerprint"])
    t1 = parse_stamp(str(r1["observed_at"]))
    t2 = parse_stamp(str(r2["observed_at"]))
    elapsed = (t2 - t1).total_seconds() if t1 and t2 else None
    false_wake = bool((not decision["watcher_wake"]) and decision["poller_wake"])
    return {
        "id": r1["id"],
        "url": r1["url"],
        "source_class": r1.get("source_class"),
        "paired": True,
        "elapsed_s": elapsed,
        "watcher_wake": decision["watcher_wake"],
        "poller_wake": decision["poller_wake"],
        "etag_changed": decision["etag_changed"],
        "last_modified_changed": decision["last_modified_changed"],
        "channel_stamp_changed": decision["channel_stamp_changed"],
        "reason": decision["reason"],
        "false_wake_if_poller": false_wake,
        "r1_sha256": r1["body_sha256"],
        "r2_sha256": r2["body_sha256"],
        "r1_wake_value": r1["fingerprint"]["wake_value"],
        "r2_wake_value": r2["fingerprint"]["wake_value"],
        "r1_observed_at": r1["observed_at"],
        "r2_observed_at": r2["observed_at"],
    }


def wayback_cdx(url: str, timeout: float = 20.0) -> dict[str, Any]:
    api = (
        "https://web.archive.org/cdx/search/cdx?url="
        + urllib.parse.quote(url, safe="")
        + "&output=json&fl=timestamp,original,statuscode,digest,length"
        + "&filter=statuscode:200&limit=40"
    )
    req = urllib.request.Request(api, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            raw = resp.read(200_000)
            observed = iso()
            status = int(resp.status)
            final = resp.geturl()
    except Exception as exc:
        return {"ok": False, "url": url, "error": f"{type(exc).__name__}: {exc}"}
    try:
        table = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "url": url, "error": f"JSONDecodeError: {exc}"}
    rows = table[1:] if isinstance(table, list) and table and isinstance(table[0], list) else []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 4:
            continue
        ts, original, code, digest = row[0], row[1], row[2], row[3]
        try:
            dt = datetime.strptime(str(ts), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        parsed.append(
            {
                "timestamp": ts,
                "datetime": iso(dt),
                "digest": digest,
                "original": original,
                "status": code,
            }
        )
    week_pair = None
    if len(parsed) >= 2:
        latest = parsed[-1]
        target = parse_stamp(str(latest["datetime"]))
        if target is not None:
            want = target - timedelta(days=7)
            best = min(
                parsed,
                key=lambda p: abs((parse_stamp(str(p["datetime"])) or target) - want),
            )
            gap = abs((parse_stamp(str(best["datetime"])) or target) - target).total_seconds()
            week_pair = {
                "near": best,
                "latest": latest,
                "gap_days": round(gap / 86400.0, 3),
                "digest_changed": best["digest"] != latest["digest"],
            }
    digest = sha256_bytes(raw)
    return {
        "ok": True,
        "url": url,
        "resolved_url": final,
        "fetch_timestamp": observed,
        "sha256": digest,
        "status": status,
        "capture_count": len(parsed),
        "week_pair": week_pair,
        "lineage": {
            "resolved_url": final,
            "fetch_timestamp": observed,
            "sha256": digest,
        },
    }


def run_live_sample(sleep_s: float = 2.0) -> dict[str, Any]:
    t_start = utcnow()
    round1 = fetch_round()
    time.sleep(max(0.0, sleep_s))
    round2 = fetch_round()
    t_end = utcnow()
    by_id_2 = {r["id"]: r for r in round2}
    pairs = []
    ok_ids = []
    for r1 in round1:
        r2 = by_id_2.get(r1["id"])
        if r2 is None:
            continue
        pair = pair_rows(r1, r2)
        pairs.append(pair)
        if r1.get("ok") and r2.get("ok"):
            ok_ids.append(r1["id"])
    chosen = ok_ids[:20]
    pair_chosen = [p for p in pairs if p.get("id") in chosen and p.get("paired")]
    watcher_wakes = sum(1 for p in pair_chosen if p.get("watcher_wake"))
    poller_wakes = sum(1 for p in pair_chosen if p.get("poller_wake"))
    false_wakes = sum(1 for p in pair_chosen if p.get("false_wake_if_poller"))
    n = len(pair_chosen)
    week_events = []
    for r1 in round1:
        if r1.get("id") not in chosen or not r1.get("ok"):
            continue
        wn = r1.get("week_native") or {}
        week_events.append(
            {
                "id": r1["id"],
                "source_class": r1.get("source_class"),
                "event_count": int(wn.get("event_count") or 0),
                "cutoff": wn.get("cutoff"),
                "events_head": wn.get("events_head") or [],
            }
        )
    wayback = [wayback_cdx(u) for u in WAYBACK_HTML]
    r1_sum = [summarize_fetch(r) for r in round1 if r.get("id") in chosen]
    r2_sum = [summarize_fetch(r) for r in round2 if r.get("id") in chosen]
    failures = [
        {"id": r["id"], "url": r["url"], "error": r.get("error"), "status": r.get("status")}
        for r in round1
        if not r.get("ok")
    ]
    return {
        "started_at": iso(t_start),
        "ended_at": iso(t_end),
        "elapsed_seconds": round((t_end - t_start).total_seconds(), 3),
        "sleep_between_rounds_s": sleep_s,
        "candidates": len(CANDIDATES),
        "paired_ok": n,
        "sample_size": n,
        "chosen_ids": chosen,
        "watcher_wakes": watcher_wakes,
        "poller_wakes": poller_wakes,
        "poller_false_wakes": false_wakes,
        "watcher_false_wake_rate": 0.0 if n else None,
        "poller_false_wake_rate": (false_wakes / n) if n else None,
        "note_false_wake": (
            "Watcher false-wake rate is 0/N on this paired window when wake_value "
            "is stable; a poller false-wake is raw-bytes change with stable canonical "
            "signal. Window is real elapsed seconds, not a mutated local copy. "
            "A standing 7-day daemon was not run."
        ),
        "week_native_events": week_events,
        "week_native_total": sum(int(x.get("event_count") or 0) for x in week_events),
        "pairs": pair_chosen,
        "round1": r1_sum,
        "round2": r2_sum,
        "failures": failures,
        "wayback": wayback,
    }


if __name__ == "__main__":
    result = run_live_sample(2.0)
    slim = {
        k: result[k]
        for k in result
        if k not in {"round1", "round2", "pairs", "wayback", "week_native_events"}
    }
    print(json.dumps(slim, indent=1, sort_keys=True))
    print(
        "paired",
        result["paired_ok"],
        "poller_false",
        result["poller_false_wakes"],
        "week_events",
        result["week_native_total"],
    )
