#!/usr/bin/env python3
"""BLD-0061 typed-claim extraction and contradiction detection.

Subject identity is exact (file path, quantity+scope, named proposition id).
Similar wording is never a grouping key — that is the DRIFTED-two-files
false-positive the estate already measured.

On a split verdict the named probe wins over agent_count. Two probe-backed
opposite verdicts are a contradiction; they are settled from the raw source
or escalated with both probes attached. Same-file disagreement is a
detector-failure, not a finding.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LANE_DIR = HERE / "fixtures" / "lanes"
SELF_CONTRA = HERE / "fixtures" / "detector-failure" / "self-contradict.json"
OWNER_SRC = HERE / "fixtures" / "sources" / "OWNER-DECISIONS-excerpt.md"
BASELINE_SRC = HERE / "fixtures" / "sources" / "BASELINE-SNAPSHOT-excerpt.json"

OPPOSITE = {
    frozenset({"CONFIRMED", "REFUTED"}),
    frozenset({"TRUE", "FALSE"}),
    frozenset({"PASS", "FAIL"}),
}
SKIP_LIVE_PARTS = {
    "node_modules",
    ".git",
    "__pycache__",
    "fixtures",
}


@dataclass
class Claim:
    id: str
    lane: str
    subject: str
    kind: str
    proposition: str
    verdict: str | None
    value: int | float | None
    denominator: str | None
    path: str
    line: int
    probe: str | None
    settling_source: str | None
    agent_count: int | None
    origin: str

    def as_public(self) -> dict[str, Any]:
        d = asdict(self)
        d["anchor"] = f"{self.path}:{self.line}"
        return d


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def line_of(path: Path, needle: str) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 1
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return 1


def _num(v: Any) -> int | float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    return None


def claim_from_obj(obj: dict[str, Any], *, path: Path, lane: str, origin: str) -> Claim | None:
    cid = str(obj.get("id") or "").strip()
    subject = str(obj.get("subject") or "").strip()
    kind = str(obj.get("kind") or "").strip().lower()
    if not cid or not subject or kind not in {"verdict", "count"}:
        return None
    probe = obj.get("probe")
    if probe is not None:
        probe = str(probe).strip() or None
    src = obj.get("settling_source")
    if src is not None:
        src = str(src).strip() or None
    ac = obj.get("agent_count")
    if ac is not None and not isinstance(ac, int):
        ac = None
    verd = obj.get("verdict")
    if verd is not None:
        verd = str(verd).strip().upper() or None
    return Claim(
        id=cid,
        lane=lane,
        subject=subject,
        kind=kind,
        proposition=str(obj.get("proposition") or obj.get("claim") or "").strip(),
        verdict=verd,
        value=_num(obj.get("value")),
        denominator=(str(obj["denominator"]).strip() if obj.get("denominator") else None),
        path=rel(path),
        line=line_of(path, cid),
        probe=probe,
        settling_source=src,
        agent_count=ac,
        origin=origin,
    )


def load_typed_file(path: Path, *, origin: str) -> list[Claim]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    lane = str(doc.get("lane") or path.stem)
    out: list[Claim] = []
    for item in doc.get("claims") or []:
        if isinstance(item, dict):
            c = claim_from_obj(item, path=path, lane=lane, origin=origin)
            if c:
                out.append(c)
    return out


def planted_lane_claims() -> list[Claim]:
    claims: list[Claim] = []
    for name in ("b09-confirmations.json", "b10-refutations.json", "b12-tally.json"):
        claims.extend(load_typed_file(LANE_DIR / name, origin="planted-lane"))
    return claims


def detector_failure_claims() -> list[Claim]:
    return load_typed_file(SELF_CONTRA, origin="planted-self-contradiction")


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def extract_architecture_claims(path: Path, doc: dict[str, Any]) -> list[Claim]:
    unit = str(doc.get("unit_id") or doc.get("architecture_id") or path.stem)
    probe = None
    for item in doc.get("named_probes") or []:
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            probe = item["command"]
            break
    out: list[Claim] = []
    for item in doc.get("claims") or []:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or "").strip()
        text = str(item.get("claim") or item.get("proposition") or "").strip()
        verd = str(item.get("verdict") or "").strip().upper()
        if not cid or not text or not verd:
            continue
        subject = f"proposition:{_norm(text)}"
        anchor = str(item.get("anchor") or "")
        line = 1
        if ":" in anchor:
            try:
                line = int(anchor.rsplit(":", 1)[-1])
            except ValueError:
                line = line_of(path, cid)
        else:
            line = line_of(path, f'"id": "{cid}"') if cid else 1
        out.append(
            Claim(
                id=f"{unit}:{cid}",
                lane=unit,
                subject=subject,
                kind="verdict",
                proposition=text,
                verdict=verd,
                value=None,
                denominator=None,
                path=rel(path),
                line=line,
                probe=probe,
                settling_source=anchor or rel(path),
                agent_count=None,
                origin="live-architecture-claim",
            )
        )
    return out


def extract_scoped_counts(path: Path, doc: Any, *, lane: str) -> list[Claim]:
    """Walk JSON for integer count fields, scoping by pairing/as_of/path.

    Two different pairings (registry-vs-generated vs dossier-vs-phase3)
    must not share a subject even when the field name is identical.
    """
    out: list[Claim] = []

    def walk(node: Any, pairing: str | None, as_of: str | None) -> None:
        if isinstance(node, dict):
            p = node.get("pairing")
            pairing2 = str(p).strip() if isinstance(p, str) and p.strip() else pairing
            a = node.get("as_of")
            as_of2 = str(a).strip() if isinstance(a, str) and a.strip() else as_of
            for key in (
                "direction_a_orphan_registry_count",
                "direction_b_orphan_output_count",
                "ci_test_steps_executed",
                "generated_file_count",
                "files_affected_by_one_shared_path_bug",
                "registry_entry_count",
                "output_file_count",
            ):
                if key in node and isinstance(node[key], int):
                    scope = pairing2 or as_of2 or rel(path)
                    subject = f"count:{key}|scope:{scope}"
                    cid = f"{rel(path)}:{key}:{scope}"
                    out.append(
                        Claim(
                            id=cid[:180],
                            lane=lane,
                            subject=subject,
                            kind="count",
                            proposition=f"{key} = {node[key]} (scope {scope})",
                            verdict=None,
                            value=node[key],
                            denominator=scope,
                            path=rel(path),
                            line=line_of(path, f'"{key}"'),
                            probe=None,
                            settling_source=rel(path),
                            agent_count=None,
                            origin="live-scoped-count",
                        )
                    )
            rbp = node.get("remaining_by_prefix")
            if isinstance(rbp, dict):
                for pref, n in rbp.items():
                    if isinstance(n, int):
                        scope = as_of2 or rel(path)
                        subject = f"count:remaining_by_prefix.{pref}|scope:{scope}"
                        out.append(
                            Claim(
                                id=f"leftover-{pref}-{scope}"[:180],
                                lane=lane,
                                subject=subject,
                                kind="count",
                                proposition=f"remaining_by_prefix[{pref}] = {n}",
                                verdict=None,
                                value=n,
                                denominator=scope,
                                path=rel(path),
                                line=line_of(path, f'"{pref}"'),
                                probe=None,
                                settling_source=rel(path),
                                agent_count=None,
                                origin="live-leftover-prefix",
                            )
                        )
            for val in node.values():
                walk(val, pairing2, as_of2)
        elif isinstance(node, list):
            for item in node:
                walk(item, pairing, as_of)

    walk(doc, None, None)
    return out


def leftover_internal_claims(path: Path, doc: dict[str, Any]) -> list[Claim]:
    """Same-file leftover totals that must agree, else detector-failure.

    The 2026-08-24 leftover snapshot originally carried remaining_by_prefix,
    remaining_if_log_success_skipped, and remaining_ids. A later rewrite dropped
    the first two and kept remaining_ids. Missing fields are not a count clash;
    duplicate remaining_ids would be.
    """
    as_of = str(doc.get("as_of") or rel(path))
    out: list[Claim] = []

    def add(cid: str, subject: str, value: int | None, needle: str) -> None:
        if value is None:
            return
        out.append(
            Claim(
                id=cid,
                lane="LEFTOVER",
                subject=subject,
                kind="count",
                proposition="Leftover remaining-unit total",
                verdict=None,
                value=value,
                denominator=as_of,
                path=rel(path),
                line=line_of(path, needle),
                probe=None,
                settling_source=rel(path),
                agent_count=None,
                origin="leftover-internal",
            )
        )

    rbp = doc.get("remaining_by_prefix")
    if isinstance(rbp, dict) and rbp:
        summed = sum(v for v in rbp.values() if isinstance(v, int))
        declared = doc.get("remaining_if_log_success_skipped")
        ids = doc.get("remaining_ids")
        idn = len(ids) if isinstance(ids, list) else None
        subject = f"count:leftover.remaining_total|scope:{as_of}"
        add("leftover-prefix-sum", subject, summed, "remaining_by_prefix")
        add(
            "leftover-declared-remaining",
            subject,
            declared if isinstance(declared, int) else None,
            "remaining_if_log_success_skipped",
        )
        add("leftover-id-list-len", subject, idn, "remaining_ids")

    ids = doc.get("remaining_ids")
    if isinstance(ids, list):
        subject = f"count:leftover.remaining_ids_cardinality|scope:{as_of}"
        add("leftover-id-list-len-card", subject, len(ids), "remaining_ids")
        add(
            "leftover-id-unique-card",
            subject,
            len({str(x) for x in ids}),
            "remaining_ids",
        )
    return out


def extract_claim_registry(path: Path, doc: Any) -> list[Claim]:
    records: Iterable[Any]
    if isinstance(doc, dict):
        records = doc.get("claims") or doc.get("records") or doc.get("entries") or []
    elif isinstance(doc, list):
        records = doc
    else:
        return []
    out: list[Claim] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or item.get("claim_id") or "").strip()
        subject = str(item.get("subject") or item.get("canonical_mechanism") or "").strip()
        text = str(
            item.get("claim") or item.get("statement") or item.get("proposition") or ""
        ).strip()
        verd = str(item.get("verdict") or item.get("verification_status") or "").strip().upper() or None
        if not cid:
            continue
        if not subject:
            subject = f"registry:{cid}"
        kind = "count" if item.get("value") is not None and _num(item.get("value")) is not None else "verdict"
        if kind == "verdict" and not verd:
            continue
        out.append(
            Claim(
                id=cid,
                lane="CLAIM-REGISTRY",
                subject=subject if kind == "count" else (subject or f"proposition:{_norm(text)}"),
                kind=kind,
                proposition=text or subject,
                verdict=verd,
                value=_num(item.get("value")),
                denominator=str(item["denominator"]).strip() if item.get("denominator") else None,
                path=rel(path),
                line=line_of(path, cid),
                probe=(str(item["source_probe"]) if item.get("source_probe") else None),
                settling_source=str(item.get("source") or rel(path)),
                agent_count=item.get("agent_count") if isinstance(item.get("agent_count"), int) else None,
                origin="claim-registry",
            )
        )
    return out


def live_search_roots() -> list[Path]:
    return [
        REPO / "command-center" / "phase3",
        REPO / "command-center" / "CLAIM-REGISTRY.json",
        REPO / "command-center" / "receipts",
        REPO / "command-center" / "adversarial",
        REPO / "command-center" / "audit",
        REPO / "command-center" / "confirmation",
        REPO / "command-center" / "p2-wave" / "P2-CLOUD-LEFTOVER_2026-08-24.json",
    ]


def iter_live_json() -> list[Path]:
    files: list[Path] = []
    for root in live_search_roots():
        if root.is_file() and root.suffix == ".json":
            files.append(root)
            continue
        if not root.is_dir():
            continue
        for p in root.rglob("*.json"):
            if any(part in SKIP_LIVE_PARTS for part in p.parts):
                continue
            if p.name in {"SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"}:
                continue
            if p.name.startswith("_"):
                continue
            files.append(p)
    probes = REPO / "command-center" / "p2-wave" / "probes"
    if probes.is_dir():
        for p in probes.glob("ARC-*/SUBAGENT-RETURN.json"):
            files.append(p)
    uniq = []
    seen = set()
    for p in files:
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        if p.name == "BLD-0061.json":
            continue
        uniq.append(p)
    return uniq


def extract_live_claims() -> tuple[list[Claim], list[dict[str, Any]]]:
    claims: list[Claim] = []
    missing: list[dict[str, Any]] = []
    expected = [
        ("command-center/CLAIM-REGISTRY.json", "CLAIM-REGISTRY"),
        ("command-center/BASELINE-SNAPSHOT.json", "baseline-snapshot"),
        ("command-center/receipts", "lane-receipts-dir"),
    ]
    for rel_path, label in expected:
        p = REPO / rel_path
        present = p.is_file() or (p.is_dir() and any(p.glob("*.json")))
        if not present:
            missing.append({"path": rel_path, "role": label, "present": False})
        else:
            missing.append({"path": rel_path, "role": label, "present": True})

    for path in iter_live_json():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        lane = path.stem
        if path.name == "CLAIM-REGISTRY.json":
            claims.extend(extract_claim_registry(path, doc))
            continue
        if isinstance(doc, dict):
            if isinstance(doc.get("claims"), list):
                claims.extend(extract_architecture_claims(path, doc))
            claims.extend(extract_scoped_counts(path, doc, lane=lane))
            if path.name.startswith("P2-CLOUD-LEFTOVER"):
                claims.extend(leftover_internal_claims(path, doc))
    return claims, missing


def opposite_verdicts(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return frozenset({a, b}) in OPPOSITE


def detect(claims: list[Claim]) -> dict[str, Any]:
    by: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for c in claims:
        by[(c.kind, c.subject)].append(c)

    contradictions: list[dict[str, Any]] = []
    detector_failures: list[dict[str, Any]] = []
    tally_overruled: list[dict[str, Any]] = []
    consistent: list[dict[str, Any]] = []

    for (kind, subject), group in sorted(by.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(group) < 2:
            continue
        paths = {c.path for c in group}
        same_file = len(paths) == 1

        if kind == "verdict":
            probes = [c for c in group if c.probe]
            tallies = [c for c in group if not c.probe]
            probe_vs = {c.verdict for c in probes if c.verdict}
            all_vs = {c.verdict for c in group if c.verdict}

            if len(all_vs) <= 1:
                consistent.append(
                    {
                        "subject": subject,
                        "kind": kind,
                        "claim_ids": [c.id for c in group],
                        "verdict": next(iter(all_vs)) if all_vs else None,
                    }
                )
                continue

            if probes and tallies:
                for t in tallies:
                    if t.verdict and (
                        (len(probe_vs) == 1 and t.verdict not in probe_vs)
                        or (len(probe_vs) > 1)
                    ):
                        tally_overruled.append(
                            {
                                "subject": subject,
                                "tally_claim": t.as_public(),
                                "winning_probe_claims": [c.as_public() for c in probes],
                                "rule": "probe-wins-over-agent-count",
                            }
                        )
                group = probes
                all_vs = probe_vs

            if len(all_vs) <= 1:
                continue

            pair = _opposite_pair(group)
            if not pair:
                continue
            left, right = pair
            rec = _pair_record(left, right, kind, subject)
            rec["escalated_with_both_probes"] = bool(left.probe and right.probe)
            rec["majority_vote_forbidden"] = True
            rec["agent_counts"] = {
                left.id: left.agent_count,
                right.id: right.agent_count,
            }
            rec["settlement"] = settle(left, right)
            if same_file:
                rec["classification"] = "detector-failure"
                detector_failures.append(rec)
            else:
                rec["classification"] = "contradiction"
                contradictions.append(rec)

        elif kind == "count":
            nums = {c.value for c in group if c.value is not None}
            if len(nums) <= 1:
                consistent.append(
                    {
                        "subject": subject,
                        "kind": kind,
                        "claim_ids": [c.id for c in group],
                        "value": next(iter(nums)) if nums else None,
                    }
                )
                continue
            a = next(c for c in group if c.value is not None)
            b = next(c for c in group if c.value is not None and c.value != a.value)
            rec = _pair_record(a, b, kind, subject)
            rec["values"] = {"left": a.value, "right": b.value}
            rec["settlement"] = settle(a, b)
            rec["majority_vote_forbidden"] = True
            rec["escalated_with_both_probes"] = bool(a.probe and b.probe)
            if same_file:
                rec["classification"] = "detector-failure"
                detector_failures.append(rec)
            else:
                rec["classification"] = "contradiction"
                contradictions.append(rec)

    return {
        "contradictions": contradictions,
        "detector_failures": detector_failures,
        "tally_overruled": tally_overruled,
        "consistent_groups": consistent,
        "subjects_grouped": len(by),
        "claims_in": len(claims),
    }


def _opposite_pair(group: list[Claim]) -> tuple[Claim, Claim] | None:
    for i, a in enumerate(group):
        for b in group[i + 1 :]:
            if opposite_verdicts(a.verdict, b.verdict):
                return a, b
    return None


def _pair_record(a: Claim, b: Claim, kind: str, subject: str) -> dict[str, Any]:
    return {
        "id": f"{kind}:{subject}:{a.id}+{b.id}",
        "kind": kind,
        "subject": subject,
        "left": a.as_public(),
        "right": b.as_public(),
        "left_anchor": f"{a.path}:{a.line}",
        "right_anchor": f"{b.path}:{b.line}",
        "left_probe": a.probe,
        "right_probe": b.probe,
        "settling_source_named": a.settling_source or b.settling_source,
    }


def settle(a: Claim, b: Claim) -> dict[str, Any]:
    src = a.settling_source or b.settling_source
    if not src:
        return {
            "status": "ESCALATED",
            "reason": "no raw source named; both probes attached; do not tally agents",
            "winner": None,
        }
    src_path = REPO / src
    if not src_path.is_file():
        return {
            "status": "ESCALATED",
            "reason": f"named source missing on disk: {src}",
            "winner": None,
            "source": src,
        }
    text = src_path.read_text(encoding="utf-8")
    if a.kind == "count" or b.kind == "count":
        parsed = None
        if src_path.suffix == ".json":
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                doc = None
            if isinstance(doc, dict):
                for key in ("ci_test_steps_executed", "value", "count"):
                    if isinstance(doc.get(key), int):
                        parsed = doc[key]
                        break
        if parsed is None:
            return {
                "status": "ESCALATED",
                "reason": "source present but count not mechanically parseable",
                "winner": None,
                "source": src,
            }
        winner = a if a.value == parsed else b if b.value == parsed else None
        return {
            "status": "RESOLVED-FROM-SOURCE" if winner else "ESCALATED",
            "reason": "parsed count from raw source; probe/source wins, agents not tallied",
            "source": src,
            "parsed_value": parsed,
            "winner": winner.id if winner else None,
        }
    if "PR-ONLY" in text and a.subject == "release.mode":
        confirmed = a if a.verdict == "CONFIRMED" else b if b.verdict == "CONFIRMED" else None
        return {
            "status": "RESOLVED-FROM-SOURCE",
            "reason": "raw source contains binding token PR-ONLY; probe/source wins over agent_count",
            "source": src,
            "winner": confirmed.id if confirmed else None,
        }
    if "TOKEN-PRESENT" in text and a.subject == "token.present":
        confirmed = a if a.verdict == "CONFIRMED" else b if b.verdict == "CONFIRMED" else None
        return {
            "status": "RESOLVED-FROM-SOURCE",
            "reason": "raw source contains TOKEN-PRESENT; self-contradiction resolved from source not by counting agents",
            "source": src,
            "winner": confirmed.id if confirmed else None,
        }
    return {
        "status": "ESCALATED",
        "reason": "source exists but does not mechanically decide this subject",
        "source": src,
        "winner": None,
    }


def evaluate_controls(result: dict[str, Any]) -> dict[str, Any]:
    contras = result["contradictions"]
    failures = result["detector_failures"]
    overruled = result["tally_overruled"]

    def has_pair(subject: str, kind: str) -> bool:
        return any(c.get("subject") == subject and c.get("kind") == kind for c in contras)

    def has_failure(subject: str) -> bool:
        return any(c.get("subject") == subject for c in failures)

    opposite_ok = has_pair("release.mode", "verdict")
    count_ok = has_pair("baseline.ci_steps_executed", "count")
    similar_wording_ids = {"B09-DRIFT-ALPHA", "B10-DRIFT-BETA"}
    fp_hit = any(
        similar_wording_ids <= {c.get("left", {}).get("id"), c.get("right", {}).get("id")}
        for c in contras + failures
    )
    tally_ok = any(t.get("subject") == "release.mode" for t in overruled)
    self_count = has_failure("widget.count")
    self_verdict = has_failure("token.present")
    rel_settle = next((c.get("settlement") for c in contras if c.get("subject") == "release.mode"), {})
    ci_settle = next((c.get("settlement") for c in contras if c.get("subject") == "baseline.ci_steps_executed"), {})

    return {
        "opposite_verdict_detected": opposite_ok,
        "count_contradiction_detected": count_ok,
        "similar_wording_different_files_not_flagged": not fp_hit,
        "tally_overruled_by_probe": tally_ok,
        "self_count_classified_detector_failure": self_count,
        "self_verdict_classified_detector_failure": self_verdict,
        "release_mode_not_settled_by_majority": bool(
            next(
                (c.get("majority_vote_forbidden") for c in contras if c.get("subject") == "release.mode"),
                False,
            )
        ),
        "release_mode_settlement": rel_settle,
        "ci_count_settlement": ci_settle,
        "pass": all(
            [
                opposite_ok,
                count_ok,
                not fp_hit,
                tally_ok,
                self_count,
                self_verdict,
            ]
        ),
    }


def run_planted() -> dict[str, Any]:
    claims = planted_lane_claims() + detector_failure_claims()
    result = detect(claims)
    controls = evaluate_controls(result)
    return {
        "claims": [c.as_public() for c in claims],
        **result,
        "controls": controls,
        "owner_source_present": OWNER_SRC.is_file(),
        "baseline_source_present": BASELINE_SRC.is_file(),
    }


def run_live() -> dict[str, Any]:
    claims, missing = extract_live_claims()
    result = detect(claims)
    return {
        "claims": [c.as_public() for c in claims],
        "missing_inputs": missing,
        "search_surface": [rel(p) for p in iter_live_json()],
        **result,
    }
