"""Licence-file classifier for WFA-0033.

Signal A is the fetched LICENSE/COPYING/SPDX-header text.
Signal B is the host's declared licence metadata field.
The graph's rule-based old_class is never used as a classification input.
Unfetchable nodes stay UNCLASSIFIED and are escalated; they are never
defaulted to PERMISSIVE.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Callable, Mapping

FetchResult = Mapping[str, Any]

COMMONS_HEADING = '"Commons Clause" License Condition v1.0'
PERMISSIVE = "PERMISSIVE"
ATTRIBUTION_REQUIRED = "ATTRIBUTION-REQUIRED"
COPYLEFT = "COPYLEFT"
WEAK_COPYLEFT = "WEAK-COPYLEFT"
RIDER_RESTRICTED = "RIDER-RESTRICTED"
UNCLASSIFIED = "UNCLASSIFIED"

# Old graph classes (inadmissible as signal B).
OLD_THIRD_PARTY = "THIRD-PARTY"
OLD_OWNER = "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY"
OLD_ATTR = "ATTRIBUTION-REQUIRED"
OLD_RIDER = "RIDER-RESTRICTED"
OLD_UNCLASS = "UNCLASSIFIED"


def sha256_text(text: str) -> str:
    raw = text.replace("\r\n", "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_rider_verbatim(text: str) -> str | None:
    """Return the Commons Clause block verbatim, or None if absent."""
    if COMMONS_HEADING not in text:
        # Tolerate curly quotes from some postings.
        curly = "“Commons Clause” License Condition v1.0"
        if curly in text:
            start = text.index(curly)
        else:
            return None
    else:
        start = text.index(COMMONS_HEADING)
    block = text[start:]
    # Cut after Licensor line when present; otherwise keep the clause body.
    m = re.search(r"\nLicensor:[^\n]*\n", block)
    if m:
        return block[: m.end()].strip("\n")
    # Fallback: four paragraphs after the heading.
    parts = re.split(r"\n\s*\n", block, maxsplit=5)
    return "\n\n".join(parts[:5]).strip()


def classify_license_text(text: str) -> dict[str, Any]:
    """Classify from licence FILE text only. Empty text is UNCLASSIFIED."""
    if not (text or "").strip():
        return {
            "class": UNCLASSIFIED,
            "spdx": None,
            "rider_obligations_verbatim": None,
            "reason": "no-licence-text",
        }
    head = text[:1200]
    rider = extract_rider_verbatim(text)
    if rider is not None:
        return {
            "class": RIDER_RESTRICTED,
            "spdx": "Apache-2.0 WITH Commons-Clause",
            "rider_obligations_verbatim": rider,
            "reason": "commons-clause-present",
        }
    low_head = head.lower()
    low_all = text[:8000].lower()
    if "creative commons" in low_all and "attribution" in low_all:
        sa = "sharealike" in low_all.replace("share alike", "sharealike")
        return {
            "class": ATTRIBUTION_REQUIRED,
            "spdx": "CC-BY-SA-4.0" if sa else "CC-BY-4.0",
            "rider_obligations_verbatim": None,
            "reason": "cc-by-legalcode",
        }
    if "gnu general public license" in low_all or "gnu gpl" in low_head:
        return {
            "class": COPYLEFT,
            "spdx": "GPL-3.0-only" if "version 3" in low_all else "GPL-2.0-only",
            "rider_obligations_verbatim": None,
            "reason": "gpl-text",
        }
    if "mozilla public license" in low_all:
        return {
            "class": WEAK_COPYLEFT,
            "spdx": "MPL-2.0",
            "rider_obligations_verbatim": None,
            "reason": "mpl-text",
        }
    mit_grant = (
        "permission is hereby granted, free of charge" in low_head
        or "mit license" in low_head
    )
    apache = "apache license" in low_head and "version 2.0" in low_head
    bsd = "redistribution and use in source and binary forms" in low_head
    if mit_grant and not apache:
        return {
            "class": PERMISSIVE,
            "spdx": "MIT",
            "rider_obligations_verbatim": None,
            "reason": "mit-grant",
        }
    if apache:
        return {
            "class": PERMISSIVE,
            "spdx": "Apache-2.0",
            "rider_obligations_verbatim": None,
            "reason": "apache-2.0-text",
        }
    if bsd:
        clause = "BSD-3-Clause" if "names of" in low_head or "neither the name" in low_all else "BSD-2-Clause"
        return {
            "class": PERMISSIVE,
            "spdx": clause,
            "rider_obligations_verbatim": None,
            "reason": "bsd-text",
        }
    return {
        "class": UNCLASSIFIED,
        "spdx": None,
        "rider_obligations_verbatim": None,
        "reason": "unrecognised-licence-text",
    }


def extract_node(node: Mapping[str, Any], fetched: FetchResult) -> dict[str, Any]:
    """Apply A (file) and B (host metadata). old_class is recorded, never consulted."""
    old = node.get("old_class")
    host = node.get("host_declared_spdx")
    host_src = node.get("host_declared_source") or "host-declared-licence-metadata"
    if not fetched.get("ok"):
        row = {
            "id": node["id"],
            "name": node.get("name") or node["id"],
            "old_class": old,
            "fetch_ok": False,
            "fetch_error": fetched.get("error") or "source-unreachable",
            "retrieval_anchor": fetched.get("anchor") or node.get("origin"),
            "retrieval_date": fetched.get("date"),
            "licence_sha256": None,
            "licence_bytes": 0,
            "licence_excerpt": None,
            "signal_a_class": UNCLASSIFIED,
            "signal_a_spdx": None,
            "signal_a_reason": "unfetchable",
            "signal_b_spdx": host,
            "signal_b_source": host_src,
            "new_class": UNCLASSIFIED,
            "spdx": None,
            "rider_obligations_verbatim": None,
            "escalated": True,
            "a_b_disagree": bool(host),
            "inadmissible_signal": "graph-rule-based-old_class-not-used",
        }
        return row
    text = str(fetched.get("text") or "")
    verdict = classify_license_text(text)
    excerpt = text.replace("\r\n", "\n")[:800]
    row = {
        "id": node["id"],
        "name": node.get("name") or node["id"],
        "old_class": old,
        "fetch_ok": True,
        "fetch_error": None,
        "retrieval_anchor": fetched.get("anchor") or node.get("retrieval_anchor"),
        "retrieval_date": fetched.get("date") or node.get("retrieval_date"),
        "licence_sha256": sha256_text(text),
        "licence_bytes": len(text.replace("\r\n", "\n").encode("utf-8")),
        "licence_excerpt": excerpt,
        "signal_a_class": verdict["class"],
        "signal_a_spdx": verdict["spdx"],
        "signal_a_reason": verdict["reason"],
        "signal_b_spdx": host,
        "signal_b_source": host_src,
        "new_class": verdict["class"],
        "spdx": verdict["spdx"],
        "rider_obligations_verbatim": verdict["rider_obligations_verbatim"],
        "escalated": verdict["class"] == UNCLASSIFIED,
        "a_b_disagree": bool(host) and bool(verdict["spdx"]) and host != verdict["spdx"],
        "inadmissible_signal": "graph-rule-based-old_class-not-used",
    }
    return row


def histogram(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    c: Counter[str] = Counter()
    for r in rows:
        k = r.get(key)
        if k:
            c[str(k)] += 1
    return dict(sorted(c.items()))


def explain_diff(
    rows: list[Mapping[str, Any]],
    old_hist: Mapping[str, int],
    new_hist: Mapping[str, int],
) -> list[dict[str, Any]]:
    transitions: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        a, b = str(r.get("old_class") or ""), str(r.get("new_class") or "")
        if a != b:
            transitions.setdefault((a, b), []).append(str(r["id"]))
    keys = sorted(set(old_hist) | set(new_hist))
    out = []
    for k in keys:
        o = int(old_hist.get(k, 0))
        n = int(new_hist.get(k, 0))
        if o == n:
            continue
        left = []
        entered = []
        for (a, b), ids in transitions.items():
            if a == k and b != k:
                left.extend(ids)
            if b == k and a != k:
                entered.extend(ids)
        bits = []
        if left:
            bits.append(
                f"{len(left)} node(s) left {k} after file-derived reclass: "
                + ", ".join(left[:8])
                + ("…" if len(left) > 8 else "")
            )
        if entered:
            bits.append(
                f"{len(entered)} node(s) entered {k} from file-derived class: "
                + ", ".join(entered[:8])
                + ("…" if len(entered) > 8 else "")
            )
        if not bits:
            bits.append(
                f"count changed {o}->{n} without a recorded per-node transition "
                "(histogram keys differ in spelling)"
            )
        out.append(
            {
                "class": k,
                "old_count": o,
                "new_count": n,
                "delta": n - o,
                "explanation": "; ".join(bits),
            }
        )
    return out


def extract_all(
    nodes: list[Mapping[str, Any]],
    fetcher: Callable[[Mapping[str, Any]], FetchResult],
) -> dict[str, Any]:
    rows = [extract_node(n, fetcher(n)) for n in nodes]
    old_hist = histogram(rows, "old_class")
    new_hist = histogram(rows, "new_class")
    escalations = [r["id"] for r in rows if r.get("escalated")]
    unfetchable = [r for r in rows if not r.get("fetch_ok")]
    for r in unfetchable:
        if r["new_class"] != UNCLASSIFIED:
            raise RuntimeError(
                f"unfetchable node {r['id']} classified {r['new_class']} "
                "(must stay UNCLASSIFIED)"
            )
        if r["new_class"] == PERMISSIVE:
            raise RuntimeError("unfetchable defaulted to PERMISSIVE")
    rider_rows = [r for r in rows if r.get("new_class") == RIDER_RESTRICTED]
    return {
        "rows": rows,
        "old_histogram": old_hist,
        "new_histogram": new_hist,
        "histogram_diff": explain_diff(rows, old_hist, new_hist),
        "escalations": escalations,
        "rider_node_ids": [r["id"] for r in rider_rows],
        "unfetchable_ids": [r["id"] for r in unfetchable],
        "node_count": len(rows),
    }
