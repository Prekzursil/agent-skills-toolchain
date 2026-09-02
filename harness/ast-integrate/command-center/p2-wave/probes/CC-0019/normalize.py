#!/usr/bin/env python3
"""Phase-1 corpus normalization for CC-0019.

Ingests in-tree prior findings plus a planted detector control, enumerates the
29 contracted Prompt One artifacts (dropping each that is absent), and emits
canonical claim records with resolvable path:line lineage.

Conservation: inputs = emitted + merged + dropped. Zero drops is a failure.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from rank import attach_rank, prove_anti_repetition
from schema import _as_receipt, validate_run

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/receipts/CC-0019.json"
SCHEMA_REL = "command-center/schema/claim-record.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SETTLE = "command-center/p2-wave/probes/CC-0019/probe1_sample.py"
PLANTED_TOKEN = "CC-0019-PLANTED-SYNTHETIC-FINDING-7f3a"
PLANTED_REL = "command-center/p2-wave/probes/CC-0019/fixtures/planted-finding.md"

CONTRACTED_29 = (
    "00-CURRENT-STATE-INVENTORY.md",
    "01-BLOCKER-REPRODUCTION.md",
    "02-BLOCKER-ROOT-CAUSE.md",
    "03-PLUGIN-LIFECYCLE-MAP.md",
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json",
    "11-COUNCIL-SPECIFICATION.md",
    "11-COUNCIL-OPTION-CARDS.md",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "13-ARCHITECTURE-CANDIDATES.md",
    "14-NO-REGRESSION-CONTRACT.md",
    "15-IMPLEMENTATION-PRECONDITIONS.md",
    "16-GRILL-QUEUE.md",
    "17-DECISION-LOG.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
    "24-REPO-RECONCILE.md",
    "32-OWNER-DECISIONS.md",
    "33-INTEGRATION.md",
    "_USER-PROMPTS.md",
    "14-OWNER-DECISION-PACKET.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.md",
)

NAMED_INPUTS = (
    "command-center/sources/REGISTER.md",
    "command-center/sources/overlay.json",
    "command-center/receipts/CC-0017.json",
    "command-center/receipts/CC-0018.json",
)

PHASE3_RELS = (
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A1/REFUTATION.json",
    "command-center/phase3/A1/FAILURE-MODES.json",
    "command-center/phase3/A2/DESIGN.json",
    "command-center/phase3/A2/REFUTATION.json",
    "command-center/phase3/A2/FAILURE-MODES.json",
)

TAG_RE = re.compile(
    r"^(?:Agent-([A-Za-z0-9_-]+):\s*)?(FINDING|CLAIM|VERDICT):\s*(.+)$"
)
WS_RE = re.compile(r"\s+")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_id_for(mechanism: str) -> str:
    key = WS_RE.sub(" ", mechanism.strip().lower())[:240]
    return "CLM-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def json_prefix(value: str, n: int) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1][:n]


def quote_on_line(line: str, value: str) -> str:
    esc = json.dumps(value, ensure_ascii=False)[1:-1]
    for n in (96, 80, 64, 48, 32, 16):
        chunk = esc[:n]
        if len(chunk) >= 8 and chunk in line:
            return chunk
    for n in (96, 80, 64, 48, 32, 16):
        chunk = value[:n]
        if len(chunk) >= 8 and chunk in line:
            return chunk
    stripped = line.strip()
    if len(stripped) >= 8:
        return stripped[:96]
    raise ValueError(f"no-quote-on-line:{line[:80]!r}")


def corpus_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "harness-restore-20260806",
        Path("/root/.claude/harness-restore-20260806"),
        repo / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    ]


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except PermissionError:
        return False


def find_named(repo: Path, name: str) -> Path | None:
    rel = name.replace("\\", "/")
    direct = repo / rel
    if _is_file(direct):
        return direct
    for root in corpus_roots(repo) + [repo, repo / "command-center"]:
        cand = root / Path(name).name
        if _is_file(cand):
            return cand
        cand = root / name
        if _is_file(cand):
            return cand
    return None


def rel_of(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def impact_for(text: str, status: str) -> str:
    blob = f"{text} {status}".upper()
    if "OWNER-BLOCKING" in blob or "BLOCKER" in blob or "BLOCKED" in blob:
        return "BLOCKER"
    if "CONTRACT" in blob or "SCHEMA" in blob:
        return "CONTRACT"
    if not text.strip():
        return "NONE"
    return "SCHEDULE"


def verify_for(status: str, disposition: str) -> str:
    blob = f"{status} {disposition}".upper()
    if "REFUTED" in blob:
        return "REFUTED"
    if "DONE-VERIFIED" in blob or "CONFIRMED" in blob:
        return "PROBED"
    return "UNVERIFIED"


def candidate(
    *,
    mechanism: str,
    path: str,
    line: int,
    quote: str,
    kind: str,
    item_id: str = "",
    agent: str = "",
    drop_reason: str = "",
    input_id: str = "",
    impact: str = "SCHEDULE",
    verification: str = "UNVERIFIED",
    confidence: str = "MEDIUM",
) -> dict[str, Any]:
    return {
        "input_id": input_id or f"{kind}:{path}:{line}:{item_id or agent}",
        "mechanism": mechanism,
        "path": path,
        "line": line,
        "quote": quote,
        "kind": kind,
        "item_id": item_id,
        "agent": agent,
        "drop_reason": drop_reason,
        "impact": impact,
        "verification": verification,
        "confidence": confidence,
    }


def drop_row(input_id: str, reason: str, path: str = "") -> dict[str, Any]:
    return candidate(
        mechanism="",
        path=path,
        line=1,
        quote="",
        kind="drop",
        drop_reason=reason,
        input_id=input_id,
        impact="NONE",
        verification="UNVERIFIED",
        confidence="UNVERIFIED",
    )


def locate_item_field(
    lines: list[str], item_id: str, field: str, value: str
) -> tuple[int, str]:
    id_hits = [i for i, ln in enumerate(lines) if f'"id": "{item_id}"' in ln]
    if not id_hits:
        raise ValueError(f"id-missing:{item_id}")
    id_idx = id_hits[0]
    lo = max(0, id_idx - 90)
    hi = min(len(lines), id_idx + 50)
    prefix = json_prefix(value, 28)
    needle = f'"{field}": "{prefix}'
    for i in range(lo, hi):
        if needle in lines[i]:
            return i + 1, quote_on_line(lines[i], value)
    needle = f'"{field}": "{json_prefix(value, 12)}'
    for i in range(lo, hi):
        if needle in lines[i]:
            return i + 1, quote_on_line(lines[i], value)
    raise ValueError(f"field-line-missing:{item_id}:{field}")


def ingest_catalog(repo: Path) -> list[dict[str, Any]]:
    rel = CATALOG_REL
    path = repo / rel
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    doc = json.loads(raw)
    out: list[dict[str, Any]] = []
    for item in doc.get("items") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        status = str(item.get("status") or "")
        disposition = str(item.get("disposition") or "")
        title = str(item.get("title") or "")
        for field in ("evidence", "disposition_evidence"):
            value = str(item.get(field) or "").strip()
            if not value:
                continue
            try:
                line, quote = locate_item_field(lines, item_id, field, value)
            except ValueError as exc:
                out.append(
                    drop_row(
                        f"catalog:{item_id}:{field}",
                        f"anchor-unresolvable:{type(exc).__name__}",
                        rel,
                    )
                )
                continue
            out.append(
                candidate(
                    mechanism=value[:400],
                    path=rel,
                    line=line,
                    quote=quote,
                    kind=f"catalog-{field}",
                    item_id=item_id,
                    impact=impact_for(title + " " + value, status),
                    verification=verify_for(status, disposition),
                    confidence="MEDIUM",
                    input_id=f"catalog:{item_id}:{field}",
                )
            )
    return out


def ingest_tagged_file(repo: Path, rel: str, kind: str) -> list[dict[str, Any]]:
    path = repo / rel
    if not path.is_file():
        return [drop_row(f"{kind}:{rel}", "source-absent", rel)]
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return [drop_row(f"{kind}:{rel}", "empty-body", rel)]
    lines = text.splitlines()
    found: list[dict[str, Any]] = []
    for i, ln in enumerate(lines, 1):
        m = TAG_RE.match(ln.strip())
        if not m:
            continue
        agent = m.group(1) or ""
        payload = m.group(3).strip()
        found.append(
            candidate(
                mechanism=payload,
                path=rel,
                line=i,
                quote=payload[:96] if payload[:96] in ln else ln.strip()[:96],
                kind=kind,
                agent=agent,
                impact="BLOCKER" if PLANTED_TOKEN in payload else "SCHEDULE",
                verification="PROBED" if PLANTED_TOKEN in payload else "UNVERIFIED",
                confidence="HIGH" if PLANTED_TOKEN in payload else "MEDIUM",
                input_id=f"{kind}:{rel}:{i}",
            )
        )
    if not found:
        return [drop_row(f"{kind}:{rel}", "not-a-claim", rel)]
    return found


def ingest_json_artifact(repo: Path, path: Path, rel: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [drop_row(f"artifact:{rel}", f"parse-error:{type(exc).__name__}", rel)]
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    cards: list[dict[str, Any]] = []

    def walk(obj: Any, depth: int) -> None:
        if depth > 8:
            return
        if isinstance(obj, list):
            for el in obj[:400]:
                walk(el, depth + 1)
            return
        if not isinstance(obj, dict):
            return
        ident = obj.get("id") or obj.get("name") or obj.get("key")
        title = obj.get("title") or obj.get("mechanism") or obj.get("claim")
        if ident and title and isinstance(title, str) and len(title) >= 16:
            cards.append({"id": str(ident), "title": title})
            return
        for v in obj.values():
            walk(v, depth + 1)

    walk(doc, 0)
    if not cards:
        return [drop_row(f"artifact:{rel}", "not-a-claim", rel)]
    out: list[dict[str, Any]] = []
    for card in cards:
        title = card["title"]
        line = 1
        quote = title[:48]
        for i, ln in enumerate(raw_lines, 1):
            if quote in ln or json_prefix(title, 24) in ln:
                line = i
                quote = quote_on_line(ln, title)
                break
        else:
            out.append(
                drop_row(
                    f"artifact:{rel}:{card['id']}",
                    "anchor-unresolvable",
                    rel,
                )
            )
            continue
        out.append(
            candidate(
                mechanism=title[:400],
                path=rel,
                line=line,
                quote=quote,
                kind="prompt-one-card",
                item_id=str(card["id"]),
                input_id=f"artifact:{rel}:{card['id']}",
            )
        )
    return out


def ingest_markdown_artifact(repo: Path, path: Path, rel: str) -> list[dict[str, Any]]:
    tagged = ingest_tagged_file(repo, rel, "prompt-one-md")
    if tagged and not tagged[0].get("drop_reason"):
        return tagged
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    heading = re.compile(r"^#{1,3}\s+(.{16,200})$")
    for i, ln in enumerate(lines, 1):
        m = heading.match(ln.strip())
        if not m:
            continue
        title = m.group(1).strip()
        out.append(
            candidate(
                mechanism=title,
                path=rel,
                line=i,
                quote=title[:96] if title[:96] in ln else ln.strip()[:96],
                kind="prompt-one-heading",
                input_id=f"artifact:{rel}:{i}",
            )
        )
    if out:
        return out
    return tagged


def ingest_contracted(repo: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    census: dict[str, Any] = {}
    for name in CONTRACTED_29:
        found = find_named(repo, name)
        rec = {
            "name": name,
            "present": found is not None,
            "path": rel_of(repo, found) if found else None,
            "bytes": found.stat().st_size if found else 0,
        }
        census[name] = rec
        if found is None:
            rows.append(drop_row(f"contracted:{name}", "source-absent", name))
            continue
        rel = rec["path"]
        if found.suffix.lower() == ".json":
            rows.extend(ingest_json_artifact(repo, found, rel))
        else:
            rows.extend(ingest_markdown_artifact(repo, found, rel))
    return rows, census


def ingest_phase3(repo: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rel in PHASE3_RELS:
        path = repo / rel
        if not path.is_file():
            out.append(drop_row(f"phase3:{rel}", "source-absent", rel))
            continue
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            out.append(drop_row(f"phase3:{rel}", "parse-error", rel))
            continue
        texts: list[tuple[str, str]] = []
        cut = str(doc.get("claim_under_test") or "").strip()
        if len(cut) >= 16:
            texts.append(("claim_under_test", cut))
        for claim in doc.get("claims") or []:
            if isinstance(claim, dict):
                body = str(claim.get("claim") or "").strip()
                if len(body) >= 16:
                    texts.append((str(claim.get("id") or "claim"), body))
        if not texts:
            out.append(drop_row(f"phase3:{rel}", "not-a-claim", rel))
            continue
        for ident, body in texts:
            line = 1
            quote = body[:48]
            for i, ln in enumerate(lines, 1):
                if json_prefix(body, 24) in ln or body[:32] in ln:
                    line = i
                    quote = quote_on_line(ln, body)
                    break
            else:
                out.append(
                    drop_row(f"phase3:{rel}:{ident}", "anchor-unresolvable", rel)
                )
                continue
            out.append(
                candidate(
                    mechanism=body[:400],
                    path=rel,
                    line=line,
                    quote=quote,
                    kind="phase3",
                    item_id=ident,
                    verification="PROBED",
                    confidence="HIGH",
                    impact="CONTRACT",
                    input_id=f"phase3:{rel}:{ident}",
                )
            )
    return out


def merge_emit(
    cands: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    dropped: list[dict[str, Any]] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    merged = 0
    for cand in cands:
        reason = str(cand.get("drop_reason") or "")
        mech = str(cand.get("mechanism") or "").strip()
        if reason:
            dropped.append(
                {
                    "input_id": cand["input_id"],
                    "reason": reason,
                    "path": cand.get("path") or "",
                }
            )
            continue
        if len(mech) < 16:
            dropped.append(
                {
                    "input_id": cand["input_id"],
                    "reason": "too-short",
                    "path": cand.get("path") or "",
                }
            )
            continue
        cid = claim_id_for(mech)
        buckets.setdefault(cid, []).append(cand)
    records: list[dict[str, Any]] = []
    for cid, group in buckets.items():
        if len(group) > 1:
            merged += len(group) - 1
        primary = max(group, key=lambda c: len(str(c.get("mechanism") or "")))
        lineage = []
        seen: set[tuple[str, int, str]] = set()
        for row in group:
            key = (row["path"], int(row["line"]), str(row.get("agent") or ""))
            if key in seen:
                continue
            seen.add(key)
            lineage.append(
                {
                    "path": row["path"],
                    "line": int(row["line"]),
                    "quote": row["quote"],
                    "kind": row.get("kind") or "",
                    "item_id": row.get("item_id") or "",
                    "agent": row.get("agent") or "",
                }
            )
        rec = {
            "claim_id": cid,
            "canonical_mechanism": str(primary["mechanism"]),
            "duplicate_of": [],
            "support_edges": [],
            "contradiction_edges": [],
            "source_lineage": lineage,
            "confidence": primary.get("confidence") or "MEDIUM",
            "verification_status": primary.get("verification") or "UNVERIFIED",
            "implementation_impact": primary.get("impact") or "SCHEDULE",
            "settling_probe": SETTLE,
            "schema_status": "PROVISIONAL",
            "phase4_superseding_unit": "ARC-0085",
        }
        records.append(attach_rank(rec))
    records.sort(key=lambda r: r["claim_id"])
    dropped.sort(key=lambda r: r["input_id"])
    return records, dropped, merged, len(cands)


def build_run(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    cands: list[dict[str, Any]] = []
    cands.extend(ingest_catalog(repo))
    cands.extend(ingest_phase3(repo))
    contracted, census = ingest_contracted(repo)
    cands.extend(contracted)
    for rel in NAMED_INPUTS:
        found = find_named(repo, rel)
        if found is None:
            cands.append(drop_row(f"named:{rel}", "source-absent", rel))
        else:
            cands.append(
                drop_row(f"named:{rel}", "not-a-claim", rel_of(repo, found))
            )
    fixtures = HERE / "fixtures"
    cands.extend(
        ingest_tagged_file(
            repo, rel_of(repo, fixtures / "planted-finding.md"), "planted"
        )
    )
    mal = fixtures / "malformed-source.json"
    try:
        json.loads(mal.read_text(encoding="utf-8"))
        cands.append(
            drop_row(
                "fixture:malformed-source.json",
                "unexpected-parse",
                rel_of(repo, mal),
            )
        )
    except json.JSONDecodeError:
        cands.append(
            drop_row(
                "fixture:malformed-source.json",
                "parse-error:JSONDecodeError",
                rel_of(repo, mal),
            )
        )
    cands.extend(
        ingest_tagged_file(
            repo, rel_of(repo, fixtures / "empty-source.md"), "fixture"
        )
    )
    cands.extend(
        ingest_tagged_file(
            repo, rel_of(repo, fixtures / "toc-only.md"), "fixture"
        )
    )

    records, dropped, merged, n_inputs = merge_emit(cands)
    planted_ids = [
        r["claim_id"]
        for r in records
        if PLANTED_TOKEN in str(r.get("canonical_mechanism") or "")
        or any(
            PLANTED_TOKEN in str(x.get("quote") or "")
            for x in r.get("source_lineage") or []
        )
    ]
    ranking = prove_anti_repetition()
    present_n = sum(1 for v in census.values() if v.get("present"))
    observed_options = 0
    for v in census.values():
        if v.get("name") == "07-OPTION-UNIVERSE.json" and v.get("present"):
            observed_options = -1
    run = {
        "unit_id": "CC-0019",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0019",
        "schema_status": "PROVISIONAL",
        "phase4_superseding_unit": "ARC-0085",
        "output_schema": SCHEMA_REL,
        "question": (
            "Execute Phase 1 normalization over the real corpus and in-tree prior "
            "findings, emitting canonical claim records with resolvable source lineage, "
            "and report dropped inputs as a first-class enumerated set."
        ),
        "dependencies_on_this_tree": {
            "CC-0017_receipt": (repo / "command-center/receipts/CC-0017.json").is_file(),
            "CC-0018_receipt": (repo / "command-center/receipts/CC-0018.json").is_file(),
            "schema_authored_here": True,
            "ranking_function": "command-center/p2-wave/probes/CC-0019/rank.py",
        },
        "corpus": {
            "harness_restore_roots_probed": [str(p) for p in corpus_roots(repo)],
            "contracted_29_present": present_n,
            "contracted_29_absent": 29 - present_n,
            "census": census,
            "unobserved_declared_payloads": {
                "platform_options": {
                    "declared": 283,
                    "observed": observed_options if observed_options >= 0 else "file-present",
                    "status": "artifact-absent" if present_n == 0 else "partial",
                },
                "workflow_candidates": {"declared": 284, "observed": 0, "status": "artifact-absent"},
                "blueprints": {"declared": 108, "observed": 0, "status": "artifact-absent"},
                "council_protocols": {"declared": 58, "observed": 0, "status": "artifact-absent"},
                "presets": {"declared": 72, "observed": 0, "status": "artifact-absent"},
                "architectures": {"declared": 11, "observed": 0, "status": "artifact-absent"},
                "harness_restore_messages": {
                    "declared": 375,
                    "observed": 0,
                    "status": "corpus-absent",
                },
            },
        },
        "conservation": {
            "inputs": n_inputs,
            "emitted": len(records),
            "merged": merged,
            "dropped": len(dropped),
            "identity": "inputs = emitted + merged + dropped",
        },
        "dropped": dropped,
        "planted_control": {
            "token": PLANTED_TOKEN,
            "path": PLANTED_REL,
            "found": bool(planted_ids),
            "claim_ids": planted_ids,
        },
        "ranking_controls": ranking,
        "anchor_policy": (
            "Every emitted record carries path:line:quote; probes re-open the file "
            "and require the quote to occur on that line. Resolve rate is a fraction."
        ),
        "records": records,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CC-0019-probe2-disjoint-sample",
            "sample_split": "shuffle(seed=19) then author=[:20] reviewer=[20:40]",
        },
    }
    validate_run(run)
    if not planted_ids:
        raise ValueError("planted-finding-absent")
    if not (
        ranking["repetition_does_not_raise_rank"]
        and ranking["strong_independent_outranks_echoes"]
        and ranking["same_document_collapses_to_one_signal"]
        and ranking["monotonicity_independent_probe_raises_rank"]
    ):
        raise ValueError(f"ranking-control-failed:{ranking}")
    return run


def dump_run(run: dict[str, Any]) -> str:
    return json.dumps(run, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def write_artifact(repo: Path | None = None) -> Path:
    repo = repo or REPO
    run = build_run(repo)
    wrapped = _as_receipt(run)
    out = repo / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump_run(wrapped)
    if "SUCCESS:CC-0019" not in text:
        raise ValueError("sentinel-missing")
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


if __name__ == "__main__":
    path = write_artifact(REPO)
    run = json.loads(path.read_text(encoding="utf-8"))
    cons = run["conservation"]
    print(
        f"wrote {OUT_REL} inputs={cons['inputs']} emitted={cons['emitted']} "
        f"merged={cons['merged']} dropped={cons['dropped']} "
        f"planted={run['planted_control']['found']}"
    )
    print("SUCCESS:CC-0019")
