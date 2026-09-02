"""Mechanical rationale recovery from frozen captures.

A recovered quote MUST be a contiguous substring of a capture's CRLF-normalised
bytes. The engine never copies a mechanism title into a rationale. Silent
history that does not contain the declared needles yields
NO-RATIONALE-RECOVERABLE rather than a plausible invention.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RAW = HERE / "captures" / "raw"
INDEX = HERE / "captures" / "index.json"

from corpus import MECHANISMS, RAILS, SENTINEL, UNIT_ID  # noqa: E402

NO_RATIONALE = "NO-RATIONALE-RECOVERABLE"
TAG_QUOTED = "QUOTED"
TAG_INFERRED = "INFERRED"

WINDOW = 220


def digest_bytes(raw: bytes) -> tuple[str, int, bytes]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), norm


def digest_file(path: Path) -> tuple[str, int]:
    sha, n, _ = digest_bytes(path.read_bytes())
    return sha, n


def load_index() -> dict:
    if not INDEX.is_file():
        raise FileNotFoundError(f"missing capture index {INDEX}")
    return json.loads(INDEX.read_text(encoding="utf-8"))


def rail_by_id(index: dict) -> dict[str, dict]:
    return {r["id"]: r for r in (index.get("rails") or []) if isinstance(r, dict)}


def read_capture(cid: str) -> tuple[str, bytes]:
    path = RAW / cid
    raw = path.read_bytes()
    _, _, norm = digest_bytes(raw)
    text = norm.decode("utf-8", errors="replace")
    return text, norm


def _window_around(text: str, needle: str) -> str | None:
    idx = text.find(needle)
    if idx < 0:
        return None
    start = max(0, idx - 40)
    end = min(len(text), idx + len(needle) + WINDOW)
    chunk = text[start:end]
    # Trim to nearby newlines so the quote is a clean block, but keep needle.
    nl = chunk.find("\n")
    if 0 <= nl < 40 and needle not in chunk[: nl + 1]:
        chunk = chunk[nl + 1 :]
    chunk = chunk.strip()
    if needle not in chunk:
        return needle
    if len(chunk) > 500:
        # Keep a bounded quote still containing the needle.
        nidx = chunk.find(needle)
        left = max(0, nidx - 60)
        right = min(len(chunk), nidx + len(needle) + 180)
        chunk = chunk[left:right].strip()
    return chunk


def extract_quotes(text: str, needles: list[str]) -> list[dict]:
    found = []
    seen = set()
    for needle in needles:
        if needle in seen:
            continue
        quote = _window_around(text, needle)
        if quote is None:
            continue
        seen.add(needle)
        found.append(
            {
                "needle": needle,
                "quote": quote,
                "tag": TAG_QUOTED,
            }
        )
    return found


def join_captures(cids: list[str]) -> tuple[str, list[dict]]:
    parts: list[str] = []
    meta: list[dict] = []
    for cid in cids:
        text, norm = read_capture(cid)
        sha, n, _ = digest_bytes(norm)
        parts.append(text)
        meta.append({"id": cid, "sha256": sha, "bytes": n})
    return "\n".join(parts), meta


def lineage_rows(cids: list[str], rails: dict[str, dict], role: str) -> list[dict]:
    rows = []
    for cid in cids:
        rec = rails.get(cid) or {}
        path = RAW / cid
        sha, n = digest_file(path)
        rows.append(
            {
                "rail": role,
                "capture_id": cid,
                "resolved_url": rec.get("permalink") or rec.get("final_url") or cid,
                "fetch_timestamp": rec.get("fetch_timestamp") or "",
                "sha256": sha,
                "bytes": n,
                "http_status": rec.get("http_status"),
                "kind": rec.get("kind") or "",
                "path": f"command-center/p2-wave/probes/RES-0181/captures/raw/{cid}",
                "independent_verification_path": (
                    "python3 -B command-center/p2-wave/probes/RES-0181/"
                    "probe1_quote_lineage.py"
                ),
            }
        )
    return rows


def docs_contradict(hist_quotes: list[str], docs_quotes: list[str], pairs: list[list[str]]) -> list[str]:
    h = "\n".join(hist_quotes).lower()
    d = "\n".join(docs_quotes).lower()
    hits = []
    for a, b in pairs:
        if a.lower() in h and b.lower() in d:
            hits.append(f"{a!r} vs {b!r}")
    return hits


def recover_one(mech: dict, rails: dict[str, dict]) -> dict:
    hist_text, _ = join_captures(mech["history_capture_ids"])
    docs_text, _ = join_captures(mech["docs_capture_ids"])
    hist_hits = extract_quotes(hist_text, list(mech["history_needles"]))
    docs_hits = extract_quotes(docs_text, list(mech["docs_needles"]))
    silent = bool(mech.get("silent"))
    if not hist_hits:
        status = NO_RATIONALE
        tag = TAG_QUOTED
        vs_docs = "NOT-APPLICABLE"
        band = "almost-certain"
        tier = "E1"
        caveat = (
            "History captures contain none of the declared needles; the engine "
            "does not invent a rationale from the mechanism name."
        )
    else:
        status = "RATIONALE-RECOVERED"
        tag = TAG_QUOTED
        hits = docs_contradict(
            [h["quote"] for h in hist_hits],
            [h["quote"] for h in docs_hits],
            list(mech.get("oppositions") or []),
        )
        vs_docs = "CONTRADICTS-DOCS" if hits else "CONSISTENT"
        band = "likely" if vs_docs == "CONTRADICTS-DOCS" else "almost-certain"
        tier = "E1"
        caveat = (
            "Contradiction is a purpose-phrase opposition between a quoted "
            "history window and a quoted current-docs window, not a behaviour test."
            if hits
            else "Recovered purpose phrases also appear in current docs (or docs "
            "do not assert an opposing purpose)."
        )
        if silent:
            # A silent mechanism must not recover; if needles were planted in
            # history the fixture is broken.
            status = "RATIONALE-RECOVERED"
            caveat = "silent fixture contained needles — fixture defect"

    hist_lineage = lineage_rows(mech["history_capture_ids"], rails, "history")
    docs_lineage = lineage_rows(mech["docs_capture_ids"], rails, "docs")
    signals = []
    seen_sha: set[str] = set()
    for row in hist_lineage + docs_lineage:
        sha = str(row.get("sha256") or "")
        if not sha or sha in seen_sha:
            continue
        seen_sha.add(sha)
        signals.append(
            {
                "id": f"rail-{len(signals)+1}",
                "class": row.get("kind") or row.get("rail") or "source",
                "anchor": row["resolved_url"],
                "sha256": sha,
                "capture_id": row.get("capture_id"),
            }
        )
        if len(signals) >= 2:
            break

    return {
        "claim_id": f"{UNIT_ID}:{mech['id']}",
        "mechanism_id": mech["id"],
        "canonical_mechanism": mech["canonical_mechanism"],
        "dependency_surface": mech["dependency_surface"],
        "silent_negative_control": silent,
        "recovery_status": status,
        "rationale_tag": tag,
        "vs_current_docs": vs_docs,
        "sherman_kent_band": band,
        "evidence_tier": tier,
        "verification_status": "CHECKED",
        "implementation_impact": (
            "guides whether this program should trust current docs for WHY, "
            "or pin the historical quote"
        ),
        "settling_probe": (
            "python3 -B command-center/p2-wave/probes/RES-0181/probe1_quote_lineage.py"
        ),
        "history_quotes": hist_hits,
        "docs_quotes": docs_hits,
        "opposition_hits": docs_contradict(
            [h["quote"] for h in hist_hits],
            [h["quote"] for h in docs_hits],
            list(mech.get("oppositions") or []),
        )
        if hist_hits
        else [],
        "source_lineage": hist_lineage + docs_lineage,
        "independent_signals": signals,
        "strongest_caveat": caveat,
        "inferred": False,
    }


def recover_all(mechanisms: list[dict] | None = None) -> dict[str, dict]:
    index = load_index()
    rails = rail_by_id(index)
    out = {}
    for mech in mechanisms if mechanisms is not None else MECHANISMS:
        out[mech["id"]] = recover_one(mech, rails)
    return out


def recover_with_history_override(mech: dict, history_text: str) -> dict:
    """Used by probe2 both-states: run extraction on injected history text."""
    hist_hits = extract_quotes(history_text, list(mech["history_needles"]))
    if not hist_hits:
        return {"recovery_status": NO_RATIONALE, "history_quotes": []}
    return {
        "recovery_status": "RATIONALE-RECOVERED",
        "history_quotes": hist_hits,
    }


def quote_in_captures(quote: str, cids: list[str]) -> bool:
    if not quote:
        return False
    for cid in cids:
        text, _ = read_capture(cid)
        if quote in text:
            return True
    return False
