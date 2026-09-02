"""Pairwise policy-contradiction matrix with file:line citations."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from corpus import HERE, inventory, rel

CLAIM_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "cla-required",
        "inbound-rights",
        re.compile(r"\b(contributor license agreement|\bcla\b)", re.I),
    ),
    (
        "cla-forbidden",
        "inbound-rights",
        re.compile(
            r"does not use a contributor license agreement|"
            r"no\s+(separate\s+)?cla\b|"
            r"there is no\s+(separate\s+)?cla\b",
            re.I,
        ),
    ),
    (
        "dco-required",
        "inbound-rights",
        re.compile(r"\b(developer certificate of origin|\bdco\b|signed-off-by)", re.I),
    ),
    (
        "mit-outbound",
        "outbound-license",
        re.compile(r"\bmit(\s+license)?\b", re.I),
    ),
    (
        "gpl-outbound",
        "outbound-license",
        re.compile(r"\bgnu\s+general\s+public\s+license|\bgpl-?[23]", re.I),
    ),
    (
        "apache-outbound",
        "outbound-license",
        re.compile(r"\bapache(\s+license)?\s*2", re.I),
    ),
    (
        "private-security-disclosure",
        "security-disclosure",
        re.compile(r"privately|security@|do not file a public issue", re.I),
    ),
    (
        "public-security-tracker",
        "security-disclosure",
        re.compile(r"file (an|a) (public )?issue|github issues for vulnerabilities", re.I),
    ),
    (
        "support-committed",
        "support",
        re.compile(r"\b(we support|supported (version|release)|support window)\b", re.I),
    ),
    (
        "unmaintained",
        "support",
        re.compile(r"\b(unmaintained|no support|unsupported)\b", re.I),
    ),
    (
        "deprecation-process",
        "deprecation",
        re.compile(r"\b(deprecat|end-of-life|\beol\b)\b", re.I),
    ),
)

CONTRADICTIONS: tuple[tuple[str, str, str], ...] = (
    ("cla-required", "cla-forbidden", "CLA required vs CLA not used"),
    ("cla-required", "dco-required", "CLA vs DCO-only inbound grant"),
    ("mit-outbound", "gpl-outbound", "MIT outbound vs GPL outbound"),
    ("apache-outbound", "gpl-outbound", "Apache-2.0 outbound vs GPL outbound"),
    (
        "private-security-disclosure",
        "public-security-tracker",
        "private disclosure vs public tracker",
    ),
    ("support-committed", "unmaintained", "support commitment vs unmaintained"),
)


def extract_claims(doc_id: str, path: str, lines: list[str]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    forbidden = next(p for t, _f, p in CLAIM_PATTERNS if t == "cla-forbidden")
    for lineno, line in enumerate(lines, 1):
        for tag, family, pat in CLAIM_PATTERNS:
            if tag == "cla-required" and forbidden.search(line):
                continue
            if pat.search(line):
                claims.append(
                    {
                        "doc_id": doc_id,
                        "path": path,
                        "line": lineno,
                        "tag": tag,
                        "family": family,
                        "sentence": line.strip(),
                        "locus": f"{path}:{lineno}",
                    }
                )
    return claims


def load_fixture_docs(kind: str) -> list[dict[str, Any]]:
    root = HERE / "fixtures" / kind
    out = []
    for name in ("CONTRIBUTING.md", "GOVERNANCE.md"):
        path = root / name
        text = path.read_text(encoding="utf-8")
        out.append(
            {
                "id": name.split(".")[0],
                "path": rel(path),
                "lines": text.splitlines(),
                "present": True,
            }
        )
    return out


def matrix_for(docs: list[dict[str, Any]]) -> dict[str, Any]:
    claims_by_doc: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        if not doc.get("present"):
            claims_by_doc[doc["id"]] = []
            continue
        claims_by_doc[doc["id"]] = extract_claims(
            doc["id"], doc.get("path") or doc["id"], doc.get("lines") or []
        )
    pairs = []
    ids = [d["id"] for d in docs]
    by_id = {d["id"]: d for d in docs}
    contradictions: list[dict[str, Any]] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            da, db = by_id[a], by_id[b]
            both = bool(da.get("present") and db.get("present"))
            hits: list[dict[str, Any]] = []
            if both:
                tags_a = {(c["tag"], c["locus"], c["sentence"]) for c in claims_by_doc[a]}
                tags_b = {(c["tag"], c["locus"], c["sentence"]) for c in claims_by_doc[b]}
                tagset_a = {t[0] for t in tags_a}
                tagset_b = {t[0] for t in tags_b}
                for left, right, note in CONTRADICTIONS:
                    if left in tagset_a and right in tagset_b:
                        ca = next(c for c in claims_by_doc[a] if c["tag"] == left)
                        cb = next(c for c in claims_by_doc[b] if c["tag"] == right)
                        hits.append(
                            {
                                "rule": note,
                                "left": {
                                    "locus": ca["locus"],
                                    "sentence": ca["sentence"],
                                    "tag": left,
                                },
                                "right": {
                                    "locus": cb["locus"],
                                    "sentence": cb["sentence"],
                                    "tag": right,
                                },
                            }
                        )
                    if left in tagset_b and right in tagset_a:
                        ca = next(c for c in claims_by_doc[b] if c["tag"] == left)
                        cb = next(c for c in claims_by_doc[a] if c["tag"] == right)
                        hits.append(
                            {
                                "rule": note,
                                "left": {
                                    "locus": ca["locus"],
                                    "sentence": ca["sentence"],
                                    "tag": left,
                                },
                                "right": {
                                    "locus": cb["locus"],
                                    "sentence": cb["sentence"],
                                    "tag": right,
                                },
                            }
                        )
            pairs.append(
                {
                    "left": a,
                    "right": b,
                    "left_present": bool(da.get("present")),
                    "right_present": bool(db.get("present")),
                    "comparable": both,
                    "contradictions": hits,
                }
            )
            contradictions.extend(hits)
    return {
        "claims": {k: v for k, v in claims_by_doc.items()},
        "pairs": pairs,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "comparable_pair_count": sum(1 for p in pairs if p["comparable"]),
        "missing_docs": [d["id"] for d in docs if not d.get("present")],
    }


def plugin_license_claim(inv: dict[str, Any]) -> list[dict[str, Any]]:
    man = inv.get("plugin_manifest") or {}
    if not man.get("present"):
        return []
    claims = []
    for lineno, line in enumerate(man.get("lines") or [], 1):
        if re.search(r'"license"\s*:\s*"([^"]+)"', line, re.I):
            claims.append(
                {
                    "doc_id": "PLUGIN-MANIFEST",
                    "path": man["path"],
                    "line": lineno,
                    "tag": "mit-outbound"
                    if "MIT" in line.upper()
                    else "declared-license",
                    "family": "outbound-license",
                    "sentence": line.strip(),
                    "locus": f"{man['path']}:{lineno}",
                }
            )
    return claims


def run() -> dict[str, Any]:
    inv = inventory()
    live_docs = [
        {
            "id": d["id"],
            "path": d.get("path"),
            "lines": d.get("lines") or [],
            "present": bool(d.get("present")),
        }
        for d in inv["documents"]
    ]
    live = matrix_for(live_docs)
    live["plugin_license_claims"] = plugin_license_claim(inv)
    planted_bad = matrix_for(load_fixture_docs("planted-contradiction"))
    planted_good = matrix_for(load_fixture_docs("planted-clean"))
    detector_fired = planted_bad["contradiction_count"] >= 1
    silent_on_good = planted_good["contradiction_count"] == 0
    return {
        "probe": "probe1-pairwise-contradiction-matrix",
        "unit_id": "ADV-0057",
        "live": live,
        "planted_contradiction": planted_bad,
        "planted_clean": planted_good,
        "negative_control": {
            "id": "planted-cla-vs-dco",
            "detector_fired": detector_fired,
            "silent_on_good": silent_on_good,
            "ok": detector_fired and silent_on_good,
        },
        "pass": detector_fired and silent_on_good,
        "computed_not_asserted": True,
    }
