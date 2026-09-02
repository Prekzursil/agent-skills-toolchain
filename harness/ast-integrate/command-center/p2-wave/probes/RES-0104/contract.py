#!/usr/bin/env python3
"""Discriminating contract for RES-0104 research-claim-record.

A garbage object, a BLOCKED self-declaration, a single-rail 'measured fact',
or a pattern missing catalog_size_observed must fail.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SENTINEL = (
    "SUCCESS:RES-0104 in the receipt AND a pattern list annotated with "
    "observed catalog sizes and one documented breaking point"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UID = "RES-0104"
RAIL_FIELDS = ("permalink", "fetched_at", "http_status", "sha256", "kind")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fail(why: str) -> tuple[bool, str]:
    return False, why


def snippet_ok(repo: Path, rail: dict) -> tuple[bool, str]:
    rel = str(rail.get("capture_path") or "")
    if not rel:
        return fail("rail-capture-path-absent")
    path = repo / rel
    if not path.is_file():
        return fail(f"capture-missing:{rel}")
    raw = path.read_bytes()
    want = str(rail.get("sha256") or "")
    if not SHA_RE.match(want):
        return fail("rail-sha256-malformed")
    got = sha256_bytes(raw)
    if got != want:
        return fail(f"rail-sha-mismatch:{rail.get('id')}")
    snippet = str(rail.get("snippet") or "")
    if len(snippet) < 12:
        return fail("rail-snippet-too-short")
    text = raw.decode("utf-8", errors="replace")
    line = int(rail.get("line") or 0)
    if line < 1:
        return fail("rail-line-missing")
    lines = text.splitlines()
    if line > len(lines):
        return fail(f"rail-line-oob:{line}")
    # Allow the snippet to straddle a wrapped line by searching nearby.
    window = "\n".join(lines[max(0, line - 3) : min(len(lines), line + 2)])
    if snippet not in text:
        return fail(f"rail-snippet-absent:{rail.get('id')}")
    if snippet not in window and snippet not in lines[line - 1]:
        return fail(f"rail-snippet-wrong-line:{rail.get('id')}:{line}")
    status = int(rail.get("http_status") or 0)
    if status != 200:
        return fail(f"rail-http-not-200:{status}")
    kind = str(rail.get("kind") or "")
    if kind not in {"api", "prose"}:
        return fail(f"rail-kind:{kind}")
    if not str(rail.get("permalink") or "").startswith("http"):
        return fail("rail-permalink")
    if not str(rail.get("fetched_at") or ""):
        return fail("rail-fetched_at")
    return True, "ok"


def rails_independent(rails: list) -> tuple[bool, str]:
    kinds = {str(r.get("kind")) for r in rails}
    if "api" not in kinds or "prose" not in kinds:
        return fail("rails-not-api-and-prose")
    urls = [str(r.get("permalink") or "") for r in rails]
    if len(set(urls)) < 2:
        return fail("rails-same-permalink")
    return True, "ok"


def check_claim(repo: Path, claim: dict, *, as_fact: bool) -> tuple[bool, str]:
    cid = str(claim.get("id") or "?")
    for key in (
        "id",
        "canonical_mechanism",
        "source_lineage",
        "evidence_tier",
        "confidence_band",
        "settling_probe",
        "strongest_caveat",
        "verdict",
    ):
        if not claim.get(key):
            return fail(f"claim-missing:{cid}:{key}")
    rails = claim.get("source_lineage")
    if not isinstance(rails, list) or not rails:
        return fail(f"claim-no-lineage:{cid}")
    for rail in rails:
        if not isinstance(rail, dict):
            return fail(f"claim-rail-not-object:{cid}")
        for f in RAIL_FIELDS:
            if rail.get(f) in (None, ""):
                return fail(f"claim-rail-missing:{cid}:{f}")
        ok, why = snippet_ok(repo, rail)
        if not ok:
            return fail(f"{cid}:{why}")
    tier = str(claim.get("evidence_tier") or "")
    cited = bool(claim.get("cited_as_measured_fact"))
    if cited and tier == "E3":
        return fail(f"e3-cited-as-fact:{cid}")
    if as_fact or cited:
        if len(rails) < 2:
            return fail(f"single-rail-cited:{cid}")
        ok, why = rails_independent(rails)
        if not ok:
            return fail(f"{cid}:{why}")
        if tier not in {"E1", "E2"}:
            return fail(f"fact-tier:{cid}:{tier}")
    if len(rails) < 2 and tier != "E3":
        return fail(f"single-rail-must-be-e3:{cid}")
    verdict = str(claim.get("verdict") or "")
    if verdict not in {"CONFIRMED", "PARTIAL", "REFUTED", "NOT-CHECKED"}:
        return fail(f"verdict:{cid}:{verdict}")
    return True, "ok"


def check(doc, repo: Path | None = None) -> tuple[bool, str]:
    repo = repo or REPO
    if not isinstance(doc, dict):
        return fail("not-object")
    if doc.get("unit_id") != UID:
        return fail("unit_id")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return fail(f"self-declared:{state}")
    if state != "SUCCESS":
        return fail(f"state:{state}")
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        return fail("sentinel-absent")
    if not isinstance(doc.get("source_lineage"), list):
        return fail("doc-source_lineage")
    patterns = doc.get("patterns")
    if not isinstance(patterns, list) or len(patterns) < 3:
        return fail("patterns-min-3")
    sizes = []
    for p in patterns:
        if not isinstance(p, dict):
            return fail("pattern-not-object")
        if not p.get("id") or not p.get("name"):
            return fail("pattern-id-name")
        if "catalog_size_observed" not in p:
            return fail(f"pattern-size-absent:{p.get('id')}")
        try:
            n = int(p["catalog_size_observed"])
        except (TypeError, ValueError):
            return fail(f"pattern-size-not-int:{p.get('id')}")
        if n < 1:
            return fail(f"pattern-size-nonpositive:{p.get('id')}")
        if not p.get("catalog_size_unit"):
            return fail(f"pattern-unit-absent:{p.get('id')}")
        sizes.append(n)
    bp = doc.get("breaking_point")
    if not isinstance(bp, dict):
        return fail("breaking_point-absent")
    try:
        br = int(bp.get("breaks_above"))
    except (TypeError, ValueError):
        return fail("breaks_above-not-int")
    if br < 1:
        return fail("breaks_above-nonpositive")
    if not bp.get("pattern_id") or not bp.get("size_unit"):
        return fail("breaking_point-fields")
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 4:
        return fail("claims-min-4")
    cited_n = 0
    e3_n = 0
    refuted_n = 0
    for c in claims:
        if not isinstance(c, dict):
            return fail("claim-not-object")
        cited = bool(c.get("cited_as_measured_fact"))
        ok, why = check_claim(repo, c, as_fact=cited)
        if not ok:
            return fail(why)
        if cited:
            cited_n += 1
        if c.get("evidence_tier") == "E3":
            e3_n += 1
        if c.get("verdict") == "REFUTED":
            refuted_n += 1
        if not c.get("strongest_caveat"):
            return fail(f"caveat-absent:{c.get('id')}")
    if cited_n < 2:
        return fail("too-few-measured-facts")
    if e3_n < 1:
        return fail("missing-e3-control-claim")
    if refuted_n < 1:
        return fail("missing-refuted-claim")
    ans = doc.get("answer_for_500")
    if not isinstance(ans, dict) or not ans.get("pattern_id"):
        return fail("answer_for_500-absent")
    ans_id = ans["pattern_id"]
    match = [p for p in patterns if p.get("id") == ans_id]
    if not match:
        return fail("answer_pattern-missing")
    if int(match[0]["catalog_size_observed"]) < 500:
        return fail("answer_pattern-size-below-500")
    rev = doc.get("reviewer")
    if not isinstance(rev, dict) or not rev.get("verdict") or not rev.get("reviewer_id"):
        return fail("reviewer")
    if "tests" not in doc or "negative_controls" not in doc:
        return fail("tests-or-controls-absent")
    return True, "ok"


def check_file(path: Path, repo: Path | None = None) -> tuple[bool, str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    return check(doc, repo=repo)
