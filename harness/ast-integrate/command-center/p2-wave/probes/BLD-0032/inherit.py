#!/usr/bin/env python3
"""Premise-to-recommendation inheritance detector for BLD-0032.

A recommendation cites a claim; that claim carries a verification tag; claims
may rest on other claims. The detector computes the transitive premise set and
flags a recommendation when that set contains UNVERIFIED or NOT-CHECKED while
the heading itself is unqualified.

Two edge builders (catalog retry_policy):
  * token: CLM-* tokens in heading+body
  * explicit: recs.json cites[] plus claim rests_on[]
Default audit uses the union, then the rests_on closure.
"""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL = HERE / "fixtures" / "control-packet"
LIVE_REGISTRY = REPO / "command-center" / "CLAIM-REGISTRY.json"

CLAIM_TOKEN = re.compile(r"\b(?:CLM|CC)-[A-Z0-9-]+\b")
WEAK_TAGS = frozenset({"UNVERIFIED", "NOT-CHECKED"})
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
REC_HINT = re.compile(r"recommend", re.IGNORECASE)


@dataclass
class Claim:
    id: str
    statement: str
    verification_status: str
    path: str
    line: int
    rests_on: list[str] = field(default_factory=list)
    tag_location: str = ""

    @property
    def tag(self) -> str:
        return self.verification_status


@dataclass
class Recommendation:
    id: str
    heading: str
    path: str
    line: int
    body: str
    cites: list[str] = field(default_factory=list)


@dataclass
class Finding:
    rec: Recommendation
    cls: str
    claim_id: str
    tag: str
    tag_location: str
    hops: int
    qualified: bool
    cited: list[str]
    premise_ids: list[str]
    method: str

    def as_dict(self) -> dict:
        return {
            "id": self.rec.id,
            "class": self.cls,
            "heading": self.rec.heading,
            "path": self.rec.path,
            "line": self.rec.line,
            "claim_id": self.claim_id,
            "tag": self.tag,
            "tag_location": self.tag_location,
            "qualified": self.qualified,
            "hops": self.hops,
            "cited_claim_ids": self.cited,
            "premise_ids": self.premise_ids,
            "method": self.method,
        }


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tag_line_for_claim(raw_lines: list[str], claim_id: str, status: str) -> int:
    """Line of the verification_status value for this claim, else the id line."""
    in_claim = False
    id_line = 1
    for i, line in enumerate(raw_lines, 1):
        if f'"{claim_id}"' in line and '"id"' in line:
            in_claim = True
            id_line = i
            continue
        if in_claim and "verification_status" in line and status in line:
            return i
        if in_claim and line.strip().startswith("}") and i > id_line:
            return id_line
    return id_line


def load_claims(path: Path) -> dict[str, Claim]:
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    doc = load_json(path)
    out: dict[str, Claim] = {}
    for row in doc.get("claims") or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        cid = str(row["id"])
        status = str(
            row.get("verification_status") or row.get("verdict") or ""
        ).upper()
        rests = [
            str(x)
            for x in (row.get("rests_on") or row.get("premises") or [])
            if isinstance(x, str)
        ]
        line = tag_line_for_claim(raw_lines, cid, status)
        rpath = rel(path)
        out[cid] = Claim(
            id=cid,
            statement=str(row.get("statement") or row.get("text") or ""),
            verification_status=status,
            path=rpath,
            line=line,
            rests_on=rests,
            tag_location=f"{rpath}:{line}",
        )
    return out


def parse_markdown_sections(path: Path) -> list[tuple[str, int, str]]:
    """Return (heading, line, body) for each ATX heading."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    headings: list[tuple[str, int]] = []
    for i, line in enumerate(lines, 1):
        m = HEADING_RE.match(line)
        if m:
            headings.append((m.group(2).strip(), i))
    sections: list[tuple[str, int, str]] = []
    for idx, (heading, line_no) in enumerate(headings):
        start = line_no
        end = headings[idx + 1][1] - 1 if idx + 1 < len(headings) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        sections.append((heading, line_no, body))
    return sections


def load_control_recommendations(packet: Path | None = None) -> list[Recommendation]:
    packet = packet or CONTROL
    md = packet / "decision-packet.md"
    meta = load_json(packet / "recs.json")
    sections = {h: (h, ln, body) for h, ln, body in parse_markdown_sections(md)}
    recs: list[Recommendation] = []
    for row in meta.get("recommendations") or []:
        heading = str(row["heading"])
        if heading not in sections:
            raise SystemExit(f"FAILED:BLD-0032 heading not in packet: {heading}")
        _h, line, body = sections[heading]
        recs.append(
            Recommendation(
                id=str(row["id"]),
                heading=heading,
                path=rel(md),
                line=line,
                body=body,
                cites=[str(x) for x in (row.get("cites") or [])],
            )
        )
    return recs


def token_cites(rec: Recommendation, known: Iterable[str] | None = None) -> list[str]:
    blob = f"{rec.heading}\n{rec.body}"
    found = CLAIM_TOKEN.findall(blob)
    if known is not None:
        known_set = set(known)
        found = [c for c in found if c in known_set]
        for cid in known_set:
            if cid in found:
                continue
            if re.search(r"\b" + re.escape(cid) + r"\b", blob):
                found.append(cid)
    # preserve order, unique
    out: list[str] = []
    seen: set[str] = set()
    for cid in found:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def explicit_cites(rec: Recommendation) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for cid in rec.cites:
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def union_cites(rec: Recommendation, known: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for cid in explicit_cites(rec) + token_cites(rec, known):
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def closure(
    start: Iterable[str], claims: dict[str, Claim]
) -> tuple[set[str], dict[str, int]]:
    hops: dict[str, int] = {}
    q: deque[tuple[str, int]] = deque()
    for cid in start:
        q.append((cid, 1))
        hops[cid] = 1
    seen: set[str] = set()
    while q:
        cid, hop = q.popleft()
        if cid in seen:
            continue
        seen.add(cid)
        claim = claims.get(cid)
        if claim is None:
            continue
        for dep in claim.rests_on:
            nxt = hop + 1
            if dep not in hops or nxt < hops[dep]:
                hops[dep] = nxt
            if dep not in seen:
                q.append((dep, nxt))
    return seen, hops


def heading_has_tag(heading: str, tag: str) -> bool:
    return tag.upper() in heading.upper()


def classify(
    rec: Recommendation,
    claims: dict[str, Claim],
    *,
    method: str = "union",
) -> Finding:
    known = list(claims)
    if method == "token":
        cited = token_cites(rec, known)
    elif method == "explicit":
        cited = explicit_cites(rec)
    else:
        cited = union_cites(rec, known)
    resolved = [c for c in cited if c in claims]
    if not resolved:
        return Finding(
            rec=rec,
            cls="UNGROUNDED",
            claim_id="",
            tag="",
            tag_location="",
            hops=0,
            qualified=False,
            cited=cited,
            premise_ids=[],
            method=method,
        )
    premises, hops = closure(resolved, claims)
    weak = [
        cid
        for cid in premises
        if cid in claims and claims[cid].tag in WEAK_TAGS
    ]
    if not weak:
        return Finding(
            rec=rec,
            cls="CLEAN",
            claim_id=resolved[0],
            tag=claims[resolved[0]].tag,
            tag_location=claims[resolved[0]].tag_location,
            hops=hops.get(resolved[0], 1),
            qualified=True,
            cited=cited,
            premise_ids=sorted(premises),
            method=method,
        )
    # worst hop first so transitivity is the recorded chain
    weak.sort(key=lambda cid: (-hops.get(cid, 1), cid))
    missing = [cid for cid in weak if not heading_has_tag(rec.heading, claims[cid].tag)]
    if not missing:
        w = weak[0]
        return Finding(
            rec=rec,
            cls="INHERITED",
            claim_id=w,
            tag=claims[w].tag,
            tag_location=claims[w].tag_location,
            hops=hops.get(w, 1),
            qualified=True,
            cited=cited,
            premise_ids=sorted(premises),
            method=method,
        )
    w = missing[0]
    return Finding(
        rec=rec,
        cls="DROPPED-TAG",
        claim_id=w,
        tag=claims[w].tag,
        tag_location=claims[w].tag_location,
        hops=hops.get(w, 1),
        qualified=False,
        cited=cited,
        premise_ids=sorted(premises),
        method=method,
    )


def audit(
    recs: list[Recommendation],
    claims: dict[str, Claim],
    *,
    method: str = "union",
) -> list[Finding]:
    return [classify(r, claims, method=method) for r in recs]


def control_packet(packet: Path | None = None) -> tuple[list[Recommendation], dict[str, Claim]]:
    packet = packet or CONTROL
    claims = load_claims(packet / "CLAIM-REGISTRY.json")
    recs = load_control_recommendations(packet)
    return recs, claims


def control_audit(method: str = "union") -> list[Finding]:
    recs, claims = control_packet()
    return audit(recs, claims, method=method)


def mutant_b_confirmed() -> list[Finding]:
    recs, claims = control_packet()
    if "CLM-B" not in claims:
        raise SystemExit("FAILED:BLD-0032 CLM-B missing from control registry")
    claims["CLM-B"].verification_status = "CONFIRMED"
    return audit(recs, claims, method="union")


def live_claim_registry_present() -> bool:
    return LIVE_REGISTRY.is_file() and LIVE_REGISTRY.stat().st_size > 0


def harvest_live_claims() -> dict[str, Claim]:
    if not live_claim_registry_present():
        return {}
    return load_claims(LIVE_REGISTRY)


def harvest_live_recommendations() -> list[Recommendation]:
    """Scan live reports (not probe fixtures) for recommendation headings."""
    recs: list[Recommendation] = []
    roots = [
        REPO / "command-center",
    ]
    skip_parts = {"p2-wave", "node_modules", ".git"}
    n = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if any(p in skip_parts for p in path.parts):
                continue
            try:
                sections = parse_markdown_sections(path)
            except OSError:
                continue
            for heading, line, body in sections:
                if not REC_HINT.search(heading):
                    continue
                n += 1
                recs.append(
                    Recommendation(
                        id=f"LIVE-REC-{n:04d}",
                        heading=heading,
                        path=rel(path),
                        line=line,
                        body=body,
                        cites=[],
                    )
                )
        for path in sorted(root.rglob("*.json")):
            if any(p in skip_parts for p in path.parts):
                continue
            if path.name in {
                "WORK-UNIT-CATALOG.json",
                "P2-CLOUD-LEFTOVER_2026-08-24.json",
                "BLD-0032.json",
            }:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            rows = []
            if isinstance(doc, dict) and isinstance(doc.get("recommendations"), list):
                rows = doc["recommendations"]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                heading = str(row.get("heading") or row.get("title") or "")
                if not heading:
                    continue
                n += 1
                recs.append(
                    Recommendation(
                        id=str(row.get("id") or f"LIVE-REC-{n:04d}"),
                        heading=heading,
                        path=rel(path),
                        line=int(row.get("line") or 1),
                        body=str(row.get("body") or row.get("text") or ""),
                        cites=[
                            str(x)
                            for x in (row.get("cites") or row.get("claim_ids") or [])
                            if isinstance(x, str)
                        ],
                    )
                )
    return recs


def live_audit() -> dict:
    claims = harvest_live_claims()
    recs = harvest_live_recommendations()
    findings = audit(recs, claims, method="union") if recs else []
    return {
        "claim_registry_present": live_claim_registry_present(),
        "claim_registry_path": "command-center/CLAIM-REGISTRY.json",
        "live_claim_count": len(claims),
        "live_recommendation_count": len(recs),
        "findings": [f.as_dict() for f in findings],
        "dropped_tag": sum(1 for f in findings if f.cls == "DROPPED-TAG"),
        "ungrounded": sum(1 for f in findings if f.cls == "UNGROUNDED"),
        "inherited": sum(1 for f in findings if f.cls == "INHERITED"),
        "clean": sum(1 for f in findings if f.cls == "CLEAN"),
        "note": (
            "Live CLAIM-REGISTRY.json is absent on this worktree; live "
            "recommendations therefore have no traceable premise and classify "
            "UNGROUNDED. Control-packet findings are the executable proof."
            if not live_claim_registry_present()
            else "Live CLAIM-REGISTRY.json was read."
        ),
    }


def by_id(findings: list[Finding]) -> dict[str, Finding]:
    return {f.rec.id: f for f in findings}
