"""Harvest authoring-time Sherman-Kent bands and later settlements.

Scored claims are later-independent settlements only (a band plus a later
CONFIRMED/REFUTED that is not the same just-executed measurement).

Contemporaneous almost-certain measurements (P2-BUILD 'directly executed')
are listed and excluded from the score — scoring them would tautologically hit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from bands import MAPPING

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SEED = 20260824

P2R1 = REPO / "command-center/p2-wave/P2-BUILD-ROUND1.md"
P2R3 = REPO / "command-center/p2-wave/P2-BUILD-ROUND3.md"
AUD0085 = (
    REPO / "command-center/p2-wave/probes/AUD-0085/_extract_out.json",
    REPO / "command-center/p2-wave/probes/AUD-0085/_extract2_out.json",
)


def _cid(*parts: str) -> str:
    blob = "\x1f".join(parts).encode("utf-8")
    return "CNF69-" + hashlib.sha256(blob).hexdigest()[:16]


def _walk(obj, found: list) -> None:
    if isinstance(obj, dict):
        conf = obj.get("confidence") or obj.get("band") or obj.get("confidence_band")
        verd = obj.get("verdict") or obj.get("outcome")
        claim = obj.get("claim")
        if (
            isinstance(conf, str)
            and conf.lower() in MAPPING
            and isinstance(claim, str)
            and claim.strip()
        ):
            found.append(
                {
                    "band": conf.lower(),
                    "outcome": str(verd).upper() if isinstance(verd, str) else "UNSETTLED",
                    "claim": claim.strip(),
                    "anchor": str(obj.get("anchor") or ""),
                }
            )
        for v in obj.values():
            _walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, found)


def harvest_later_refutes() -> list[dict]:
    """AUD-0085 refute-stage evidence: almost-certain claims later REFUTED."""
    seen: set[str] = set()
    out: list[dict] = []
    for path in AUD0085:
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows: list[dict] = []
        _walk(doc, rows)
        for row in rows:
            key = row["claim"]
            if key in seen:
                continue
            seen.add(key)
            outcome = row["outcome"]
            kind = "later-refute" if outcome in {"CONFIRMED", "REFUTED"} else "unsettled"
            out.append(
                {
                    "id": _cid(rel, row["band"], key),
                    "band": row["band"],
                    "outcome": outcome if outcome in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"} else "UNSETTLED",
                    "settlement_kind": kind,
                    "claim": key,
                    "source": rel,
                    "anchor": row["anchor"],
                }
            )
    return out


def _split_semicolon_items(paragraph: str) -> list[str]:
    parts = [p.strip().strip(".").strip() for p in paragraph.split(";")]
    return [p for p in parts if len(p) > 12]


def harvest_p2_build() -> list[dict]:
    """Parse P2-BUILD ROUND1/ROUND3 Sherman-Kent sections."""
    claims: list[dict] = []
    text1 = P2R1.read_text(encoding="utf-8") if P2R1.is_file() else ""
    text3 = P2R3.read_text(encoding="utf-8") if P2R3.is_file() else ""

    m = re.search(
        r"\*\*ALMOST CERTAIN \(90-99%\)\*\*[^\n]*\n(?P<body>.*?)\n\n\*\*LIKELY",
        text1,
        re.S,
    )
    if m:
        body = re.sub(r"\s+", " ", m.group("body")).strip()
        for item in _split_semicolon_items(body):
            claims.append(
                {
                    "id": _cid("P2-BUILD-ROUND1.md", "almost-certain", item),
                    "band": "almost-certain",
                    "outcome": "UNSETTLED",
                    "settlement_kind": "contemporaneous-measurement",
                    "claim": item,
                    "source": "command-center/p2-wave/P2-BUILD-ROUND1.md",
                    "anchor": "P2-BUILD-ROUND1.md:C10",
                }
            )

    m = re.search(
        r"\*\*LIKELY \(55-80%\)\*\*:\s*(?P<body>.*?)\n\n\*\*",
        text1,
        re.S,
    )
    if m:
        body = re.sub(r"\s+", " ", m.group("body")).strip()
        claims.append(
            {
                "id": _cid("P2-BUILD-ROUND1.md", "likely", body),
                "band": "likely",
                "outcome": "UNSETTLED",
                "settlement_kind": "unsettled",
                "claim": body,
                "source": "command-center/p2-wave/P2-BUILD-ROUND1.md",
                "anchor": "P2-BUILD-ROUND1.md:C10",
                "why_unsettled": "author named a settling experiment in AUD-0030 residual_unknowns; no later independent adjudication is on disk",
            }
        )

    m = re.search(
        r"Almost-certain \(90-99%\)[^\n]*:\s*(?P<body>.*?)\s+Likely \(55-80%\):\s*(?P<likely>.*?)\s+Deliberately not claimed",
        text3,
        re.S,
    )
    if m:
        body = re.sub(r"\s+", " ", m.group("body")).strip()
        for item in _split_semicolon_items(body):
            claims.append(
                {
                    "id": _cid("P2-BUILD-ROUND3.md", "almost-certain", item),
                    "band": "almost-certain",
                    "outcome": "UNSETTLED",
                    "settlement_kind": "contemporaneous-measurement",
                    "claim": item,
                    "source": "command-center/p2-wave/P2-BUILD-ROUND3.md",
                    "anchor": "P2-BUILD-ROUND3.md:CONFIDENCE",
                }
            )
        likely = re.sub(r"\s+", " ", m.group("likely")).strip()
        claims.append(
            {
                "id": _cid("P2-BUILD-ROUND3.md", "likely", likely),
                "band": "likely",
                "outcome": "UNSETTLED",
                "settlement_kind": "unsettled",
                "claim": likely,
                "source": "command-center/p2-wave/P2-BUILD-ROUND3.md",
                "anchor": "P2-BUILD-ROUND3.md:CONFIDENCE",
                "why_unsettled": "author stated no human adjudication of REAL-WORK labels",
            }
        )
    return claims


def harvest() -> dict:
    later = harvest_later_refutes()
    p2 = harvest_p2_build()
    # Dedup by id; later-refute wins over p2 if any collision (there should be none).
    by_id = {c["id"]: c for c in p2}
    for c in later:
        by_id[c["id"]] = c
    claims = [by_id[k] for k in sorted(by_id)]
    frame = [c["id"] for c in claims]
    return {
        "seed": SEED,
        "sampling_rule": "take-all (live banded claim count below 200; seed recorded for redraw identity)",
        "sampling_frame": frame,
        "sampled_ids": list(frame),
        "claims": claims,
    }
