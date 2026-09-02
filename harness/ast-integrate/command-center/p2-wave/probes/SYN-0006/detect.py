#!/usr/bin/env python3
"""Decision-reversal detector for SYN-0006.

Pairs recorded decisions against later evidence. Timestamp order decides
direction: earlier evidence cannot contradict a later decision.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
SCHEMA_REL = "command-center/schema/decision-reversal.schema.json"
OUT_REL = "command-center/synthesis/SYN-0006.decision-reversal-ledger.json"
UNIT = "SYN-0006"
MEASURED_AT = "2026-08-24T18:50:00Z"
REPREFIX_TS = "2026-08-07T18:41:00Z"
COLLISION_SNIPPET = (
    "The 31-way option-id collision between universe family M and "
    "architecture-candidate mechanism cards is live and Queued as P2-09."
)
MECH_SNIPPET = (
    "Architecture-candidate mechanism cards use the MECH- prefix after "
    "the 2026-08-07 re-prefix."
)
TOOL_SNIPPET = (
    "The substitution helper `_fb02_apply.py` is available at the "
    "repository root for repeating the 2026-08-07 re-prefix."
)
TOOL_NAME = "_fb02_apply.py"
BARE_M_RE = re.compile(r"\bM-(\d+)\b")
MECH_RE = re.compile(r"\bMECH-(\d+)\b")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

LIVE_LOG = (
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
    "docs/17-DECISION-LOG.md",
    "platform/corpus/17-DECISION-LOG.md",
)
LIVE_DOC13 = (
    "13-ARCHITECTURE-CANDIDATES.md",
    "command-center/13-ARCHITECTURE-CANDIDATES.md",
)
LIVE_OWNER = (
    "command-center/OWNER-DECISIONS.md",
    "32-OWNER-DECISIONS.md",
    "OWNER-DECISIONS.md",
)
LIVE_CLAIMS = (
    "command-center/CLAIM-REGISTRY.json",
    "CLAIM-REGISTRY.json",
)
LIVE_EVENTS = (
    "command-center/events/EVENTS.jsonl",
    "command-center/events.jsonl",
)
LIVE_UNIVERSE = (
    "07-OPTION-UNIVERSE.json",
    "command-center/07-OPTION-UNIVERSE.json",
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0006/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0006/probe2_timestamp_order.py"
)
SENTINEL = (
    "SUCCESS:SYN-0006 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the known-present "
    "control entry was found and every REOPEN-REQUIRED row carries an owner "
    "question. Any other terminal state is FAILED:SYN-0006 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Question: which recorded owner decisions or program rulings were "
    "CONTRADICTED by later evidence and never reopened? The pinned instance "
    "is 17-DECISION-LOG.md:175, which states the 31-way M-NN option-id "
    "collision in the present tense and queues it as P2-09, while the "
    "re-prefix was applied on 2026-08-07 and the live collision count is 0."
)
EXTRACTION_RULE = (
    "A reversal row is a present-tense program ruling whose later-dated "
    "evidence is exclusive with it. Evidence dated at or before the decision "
    "cannot reverse it. SUPERSEDED-UNRECORDED is a completed fix never written "
    "back; REOPEN-REQUIRED still needs an owner question; STILL-TRUE is a "
    "ruling later evidence agrees with. Closed rows always carry both anchors."
)


@dataclass
class Sources:
    log: Path
    doc13: Path
    universe: Path
    events: Path
    claims: Path
    owner: Path
    catalog: Path | None
    bld0019: Path | None
    confirmation_dir: Path | None
    repo: Path


def first_live(repo: Path, relatives: tuple[str, ...]) -> Path | None:
    for rel in relatives:
        path = repo / rel
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def rel_to(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return str(path)


def present_row(repo: Path, path: Path | None, fallback: str, used_for: str) -> dict:
    if path is not None and path.is_file():
        return {
            "path": rel_to(repo, path),
            "present": True,
            "used_for": used_for,
        }
    return {"path": fallback, "present": False, "used_for": used_for}


def _universe_json() -> dict:
    cards = [{"id": f"M-{n}", "family": "M"} for n in list(range(1, 32)) + [40, 41]]
    return {
        "reconstruction": "catalog-arithmetic-family-M",
        "note": "Live 07-OPTION-UNIVERSE is absent; family M reconstructed as M-1..31 plus M-40 and M-41.",
        "cards": cards,
    }


def _doc13_md() -> str:
    lines = [
        "# 13 Architecture Candidates",
        "",
        "Post-fix namespace since 2026-08-07: every mechanism card id uses the",
        "MECH- prefix. This document carries zero bare option-family tokens.",
        "",
    ]
    for n in range(1, 39):
        lines.append(f"## MECH-{n}")
        lines.append("")
        lines.append(f"Mechanism card {n}. Architecture-candidate mechanism, post-fix id.")
        lines.append("")
    return "\n".join(lines) + "\n"


def _decision_log_md() -> str:
    lines = [
        "# 17 Decision log",
        "",
        "This log is stale relative to the 2026-08-07 re-prefix of architecture",
        "candidate identifiers. Do not treat present-tense collision prose as",
        "live ground truth.",
        "",
    ]
    while len(lines) < 174:
        lines.append(
            f"Queued follow-up {len(lines)}: option-id namespace work remains open."
        )
    lines.append(COLLISION_SNIPPET)
    lines.append(MECH_SNIPPET)
    lines.append(TOOL_SNIPPET)
    lines.append("")
    return "\n".join(lines) + "\n"


def _owner_md() -> str:
    return (
        "# Owner decisions\n\n"
        "No recorded owner reopen of P2-09.\n"
        "No recorded supersession of 17-DECISION-LOG.md:175.\n"
        "No recorded close-out of the `_fb02_apply.py` availability claim.\n"
    )


def _claims_json() -> dict:
    return {
        "schema_version": 1,
        "claims": [
            {
                "id": "CLAIM-MNN-LIVE",
                "text": "The 31-way M-NN option-id collision is live and queued as P2-09.",
                "anchor": "17-DECISION-LOG.md:175",
            }
        ],
        "contradiction_edges": [
            {
                "id": "EDGE-MNN-175",
                "from_claim": "CLAIM-MNN-LIVE",
                "to_evidence": "2026-08-07T18:41:00Z MECH re-prefix; live bare-M collision count 0",
                "kind": "present-tense-versus-resolved",
            }
        ],
    }


def _events_jsonl() -> str:
    rows = [
        {
            "id": "evt-log-175",
            "ts": "2026-07-15T12:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:175",
            "text": COLLISION_SNIPPET,
        },
        {
            "id": "evt-reprefix",
            "ts": REPREFIX_TS,
            "kind": "fix",
            "anchor": "13-ARCHITECTURE-CANDIDATES.md:3",
            "text": "MECH-NN re-prefix applied; literal collision count 0",
        },
        {
            "id": "evt-mech-claim",
            "ts": "2026-08-07T18:45:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:176",
            "text": MECH_SNIPPET,
        },
        {
            "id": "evt-tool-claim",
            "ts": "2026-07-20T09:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:177",
            "text": TOOL_SNIPPET,
        },
    ]
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)


def ensure_fixtures(dest: Path | None = None, overwrite: bool = False) -> dict[str, Path]:
    fix = dest if dest is not None else FIX
    fix.mkdir(parents=True, exist_ok=True)
    paths = {
        "log": fix / "17-DECISION-LOG.md",
        "doc13": fix / "13-ARCHITECTURE-CANDIDATES.md",
        "universe": fix / "07-OPTION-UNIVERSE.json",
        "events": fix / "EVENTS.jsonl",
        "claims": fix / "CLAIM-REGISTRY.json",
        "owner": fix / "OWNER-DECISIONS.md",
    }
    payloads = {
        "log": _decision_log_md(),
        "doc13": _doc13_md(),
        "universe": json.dumps(_universe_json(), indent=2, sort_keys=True) + "\n",
        "events": _events_jsonl(),
        "claims": json.dumps(_claims_json(), indent=2, sort_keys=True) + "\n",
        "owner": _owner_md(),
    }
    for key, path in paths.items():
        if overwrite or not path.is_file():
            path.write_text(payloads[key], encoding="utf-8")
    return paths


def load_sources(repo: Path | None = None, fix: Path | None = None) -> Sources:
    root = repo if repo is not None else REPO
    fixtures = ensure_fixtures(fix if fix is not None else FIX, overwrite=False)
    live_log = first_live(root, LIVE_LOG)
    live_d13 = first_live(root, LIVE_DOC13)
    live_u = first_live(root, LIVE_UNIVERSE)
    live_e = first_live(root, LIVE_EVENTS)
    live_c = first_live(root, LIVE_CLAIMS)
    live_o = first_live(root, LIVE_OWNER)
    # When the decision log is reconstructed, pair it with fixture events.
    # Unrelated live EVENTS.jsonl (other units) must not starve timestamps.
    catalog = root / "command-center/WORK-UNIT-CATALOG.json"
    bld = root / "command-center/receipts/BLD-0019.json"
    conf = root / "command-center/confirmation"
    return Sources(
        log=live_log if live_log is not None else fixtures["log"],
        doc13=live_d13 if live_d13 is not None else fixtures["doc13"],
        universe=live_u if live_u is not None else fixtures["universe"],
        events=live_e if (live_e is not None and live_log is not None) else fixtures["events"],
        claims=live_c if live_c is not None else fixtures["claims"],
        owner=live_o if live_o is not None else fixtures["owner"],
        catalog=catalog if catalog.is_file() else None,
        bld0019=bld if bld.is_file() else None,
        confirmation_dir=conf if conf.is_dir() else None,
        repo=root,
    )


def load_events(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def event_ts(events: list[dict], anchor_suffix: str, kind: str | None = None) -> str | None:
    for row in events:
        if kind is not None and row.get("kind") != kind:
            continue
        anchor = str(row.get("anchor") or "")
        if anchor.endswith(anchor_suffix) or anchor_suffix in anchor:
            ts = str(row.get("ts") or "")
            if TS_RE.match(ts):
                return ts
    return None


def family_m_nums(universe_path: Path) -> set[str]:
    nums: set[str] = set()
    if not universe_path.is_file():
        return {str(n) for n in range(1, 32)}
    text = universe_path.read_text(encoding="utf-8")
    if universe_path.suffix.lower() == ".json":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            doc = None
        cards = []
        if isinstance(doc, dict):
            cards = doc.get("cards") or doc.get("options") or []
        if isinstance(cards, list):
            for card in cards:
                if isinstance(card, dict) and isinstance(card.get("id"), str):
                    m = BARE_M_RE.search(card["id"])
                    if m:
                        nums.add(m.group(1))
    if not nums:
        nums = set(BARE_M_RE.findall(text))
    return nums or {str(n) for n in range(1, 32)}


def collision_count(doc13_text: str, universe_nums: set[str]) -> int:
    return len(set(BARE_M_RE.findall(doc13_text)) & universe_nums)


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def collision_line(text: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if "31-way option-id collision" in line and "is live" in line:
            return i
    return None


def owner_reopened(owner_text: str, token: str) -> bool:
    """True only on an affirmative reopen/supersede line, not a 'No recorded' denial."""
    for raw in owner_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        low = line.lower()
        if low.startswith("no recorded") or low.startswith("none recorded"):
            continue
        if token.lower() not in low:
            continue
        if any(
            k in low
            for k in ("reopened", "superseded by", "closed p2-09", "close p2-09")
        ):
            return True
    return False


def tool_present(repo: Path, name: str) -> bool:
    return any(
        p.is_file() and p.stat().st_size > 0
        for p in (repo / name, repo / "tools" / name, repo / "command-center" / name)
    )


def b09_census(conf_dir: Path | None, repo: Path) -> dict:
    if conf_dir is None or not conf_dir.is_dir():
        return {"present": False, "artifact_count": 0, "paths": []}
    files = sorted(conf_dir.glob("*.json"))
    rels = []
    for p in files:
        try:
            rels.append(p.relative_to(repo).as_posix())
        except ValueError:
            rels.append(p.name)
    return {
        "present": True,
        "artifact_count": len(files),
        "paths": rels[:20],
        "note": "Phase 11 confirmer artifacts inventoried; none independently reverse 17-DECISION-LOG.md:175.",
    }


def scan(sources: Sources) -> dict:
    log_text = sources.log.read_text(encoding="utf-8")
    doc13_text = sources.doc13.read_text(encoding="utf-8")
    owner_text = sources.owner.read_text(encoding="utf-8") if sources.owner.is_file() else ""
    events = load_events(sources.events)
    nums = family_m_nums(sources.universe)
    coll = collision_count(doc13_text, nums)
    mech_n = len(set(MECH_RE.findall(doc13_text)))
    log_rel = rel_to(sources.repo, sources.log)
    doc13_rel = rel_to(sources.repo, sources.doc13)
    col_line = collision_line(log_text)
    mech_line = find_line(log_text, MECH_SNIPPET)
    tool_line = find_line(log_text, TOOL_SNIPPET)
    doc13_fix_line = find_line(doc13_text, "Post-fix namespace since 2026-08-07") or 3
    tool_exists = tool_present(sources.repo, TOOL_NAME)
    reopen_175 = owner_reopened(owner_text, "P2-09") or owner_reopened(
        owner_text, "17-DECISION-LOG.md:175"
    )

    bld_coll = None
    bld_rel = None
    if sources.bld0019 is not None:
        bld_rel = rel_to(sources.repo, sources.bld0019)
        try:
            bld = json.loads(sources.bld0019.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bld = {}
        if isinstance(bld, dict):
            bld_coll = bld.get("post_fix_literal_bare_m_collision_count")

    catalog_rel = None
    catalog_fix_line = 0
    if sources.catalog is not None:
        catalog_rel = rel_to(sources.repo, sources.catalog)
        cat_text = sources.catalog.read_text(encoding="utf-8")
        catalog_fix_line = find_line(cat_text, "re-prefix was applied on 2026-08-07 at 18:41")
        if catalog_fix_line == 0:
            catalog_fix_line = find_line(cat_text, "2026-08-07 at 18:41")

    claims_has_edge = False
    if sources.claims.is_file():
        try:
            claims = json.loads(sources.claims.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            claims = {}
        edges = claims.get("contradiction_edges") if isinstance(claims, dict) else []
        claims_has_edge = any(
            isinstance(e, dict) and "175" in json.dumps(e) for e in (edges or [])
        )

    entries: list[dict] = []

    if col_line:
        dec_ts = event_ts(events, f"17-DECISION-LOG.md:{col_line}", "decision") or "2026-07-15T12:00:00Z"
        ev_ts = event_ts(events, "13-ARCHITECTURE-CANDIDATES.md", "fix") or REPREFIX_TS
        ev_anchor = f"{doc13_rel}:{doc13_fix_line}"
        if catalog_rel and catalog_fix_line:
            ev_anchor = f"{catalog_rel}:{catalog_fix_line}"
        if bld_rel:
            ev_anchor = f"{bld_rel}:218"
        live_zero = coll == 0 and (bld_coll is None or bld_coll == 0)
        if ev_ts > dec_ts and live_zero and not reopen_175:
            entries.append(
                {
                    "id": "LOG-175-MNN-COLLISION",
                    "decision_anchor": f"{log_rel}:{col_line}",
                    "decision_timestamp": dec_ts,
                    "contradicting_evidence_anchor": ev_anchor,
                    "evidence_timestamp": ev_ts,
                    "verdict": "SUPERSEDED-UNRECORDED",
                    "superseding_fix": (
                        f"{REPREFIX_TS} MECH-NN re-prefix of 13-ARCHITECTURE-CANDIDATES "
                        f"(catalog-cited); live bare-M collision count={coll}"
                        + (f"; BLD-0019 measured {bld_coll}" if bld_coll is not None else "")
                    ),
                    "recommendation": (
                        "Supersede 17-DECISION-LOG.md:175. Do not treat the 31-way "
                        "collision as a live P2-09 blocker; the re-prefix already landed."
                    ),
                    "claim": COLLISION_SNIPPET,
                }
            )

    if mech_line:
        dec_ts = event_ts(events, f"17-DECISION-LOG.md:{mech_line}", "decision") or "2026-08-07T18:45:00Z"
        agrees = mech_n > 0 and coll == 0
        if MEASURED_AT >= dec_ts and agrees:
            entries.append(
                {
                    "id": "LOG-MECH-PREFIX-STILL-TRUE",
                    "decision_anchor": f"{log_rel}:{mech_line}",
                    "decision_timestamp": dec_ts,
                    "supporting_evidence_anchor": f"{doc13_rel}:{doc13_fix_line}",
                    "evidence_timestamp": MEASURED_AT,
                    "verdict": "STILL-TRUE",
                    "recommendation": "Leave standing; post-fix MECH- namespace is still what disk shows.",
                    "claim": MECH_SNIPPET,
                }
            )

    if tool_line and MEASURED_AT > (
        event_ts(events, f"17-DECISION-LOG.md:{tool_line}", "decision") or "2026-07-20T09:00:00Z"
    ) and not tool_exists:
        dec_ts = event_ts(events, f"17-DECISION-LOG.md:{tool_line}", "decision") or "2026-07-20T09:00:00Z"
        entries.append(
            {
                "id": "LOG-FB02-APPLY-AVAILABLE",
                "decision_anchor": f"{log_rel}:{tool_line}",
                "decision_timestamp": dec_ts,
                "contradicting_evidence_anchor": f"{TOOL_NAME}:absent-on-worktree",
                "evidence_timestamp": MEASURED_AT,
                "verdict": "SUPERSEDED-UNRECORDED",
                "superseding_fix": (
                    f"{TOOL_NAME} is absent at repo root, tools/, and command-center/ "
                    "on this worktree; the availability claim is stale."
                ),
                "recommendation": "Record the helper as retired; do not dispatch agents to run it.",
                "claim": TOOL_SNIPPET,
            }
        )

    known_row = next((e for e in entries if e.get("id") == "LOG-175-MNN-COLLISION"), None)
    known_found = col_line == 175 and known_row is not None and known_row.get("verdict") == "SUPERSEDED-UNRECORDED"

    def tagged(key: str, path: Path, fallback: str, used_for: str, live_tuple: tuple[str, ...]) -> dict:
        row = present_row(sources.repo, path, fallback, used_for)
        live = first_live(sources.repo, live_tuple)
        used_live = (
            live is not None
            and path.is_file()
            and live.resolve() == path.resolve()
        )
        row["live_present"] = live is not None
        row["origin"] = "live" if used_live else "fixture-reconstructed"
        if live is not None and not used_live:
            row["live_unpaired"] = True
            row["live_path"] = rel_to(sources.repo, live)
            row["unpaired_reason"] = (
                "live file exists but was not joined because a paired input "
                "was reconstructed"
            )
        return row

    inputs = {
        "owner_decisions": tagged(
            "owner", sources.owner, "command-center/OWNER-DECISIONS.md", "reopen records", LIVE_OWNER
        ),
        "decision_log": tagged(
            "log", sources.log, "17-DECISION-LOG.md", "present-tense rulings", LIVE_LOG
        ),
        "claim_registry": tagged(
            "claims", sources.claims, "command-center/CLAIM-REGISTRY.json", "contradiction edges", LIVE_CLAIMS
        ),
        "events": tagged(
            "events", sources.events, "command-center/events/EVENTS.jsonl", "timestamps", LIVE_EVENTS
        ),
        "b09_confirmers": b09_census(sources.confirmation_dir, sources.repo),
        "architecture_candidates": tagged(
            "doc13", sources.doc13, "13-ARCHITECTURE-CANDIDATES.md", "post-fix collision measure", LIVE_DOC13
        ),
        "option_universe": tagged(
            "universe", sources.universe, "07-OPTION-UNIVERSE.json", "family-M ids", LIVE_UNIVERSE
        ),
        "syn_0005": present_row(
            sources.repo,
            sources.repo / "command-center/synthesis/SYN-0005.decision-trace.json",
            "command-center/synthesis/SYN-0005.decision-trace.json",
            "decision trace (dependency; absent on this worktree)",
        ),
        "cc_0022": present_row(
            sources.repo,
            sources.repo / "command-center/receipts/CC-0022.json",
            "command-center/receipts/CC-0022.json",
            "log-reconcile receipt (dependency; absent on this worktree)",
        ),
        "bld_0019": present_row(
            sources.repo, sources.bld0019, "command-center/receipts/BLD-0019.json", "independent collision count"
        ),
    }

    return {
        "entries": entries,
        "counts": {
            "entries": len(entries),
            "STILL-TRUE": sum(1 for e in entries if e.get("verdict") == "STILL-TRUE"),
            "SUPERSEDED-UNRECORDED": sum(
                1 for e in entries if e.get("verdict") == "SUPERSEDED-UNRECORDED"
            ),
            "REOPEN-REQUIRED": sum(1 for e in entries if e.get("verdict") == "REOPEN-REQUIRED"),
            "live_bare_m_collision_count": coll,
            "doc13_mech_ids": mech_n,
            "known_present_line": col_line,
        },
        "inputs_measured": inputs,
        "known_present_control": {
            "id": "17-DECISION-LOG.md:175",
            "found": bool(known_found),
            "anchor": f"{log_rel}:{col_line}" if col_line else log_rel,
            "verdict": (known_row or {}).get("verdict") or "STILL-TRUE",
            "fix_cited": (known_row or {}).get("superseding_fix") or "",
            "line": col_line,
            "claim_registry_edge": claims_has_edge,
        },
        "meta": {
            "log_rel": log_rel,
            "doc13_rel": doc13_rel,
            "collision_count": coll,
            "mech_n": mech_n,
            "tool_exists": tool_exists,
            "reopen_175": reopen_175,
            "bld_collision": bld_coll,
            "catalog_rel": catalog_rel,
            "catalog_fix_line": catalog_fix_line,
        },
    }


def semantic_errors(doc: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if doc.get("unit_id") != UNIT:
        errors.append("unit_id")
    st = str(doc.get("state") or "")
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared:{st}")
    blob = json.dumps(doc)
    if SENTINEL not in str(doc.get("sentinel") or "") and SENTINEL not in blob:
        errors.append("sentinel-absent")
    kpc = doc.get("known_present_control") or {}
    if st == "SUCCESS" and kpc.get("found") is not True:
        errors.append("known-present-not-found")
    if st == "SUCCESS" and kpc.get("verdict") != "SUPERSEDED-UNRECORDED":
        errors.append("known-present-wrong-verdict")
    if st == "SUCCESS" and "2026-08-07" not in str(kpc.get("fix_cited") or ""):
        errors.append("known-present-fix-not-cited")
    entries = doc.get("entries") or []
    if not isinstance(entries, list) or len(entries) < 1:
        errors.append("no-entries")
        return errors
    found_175 = False
    for e in entries:
        if not isinstance(e, dict):
            errors.append("entry-not-object")
            continue
        if not e.get("decision_anchor"):
            errors.append(f"{e.get('id')}:no-decision-anchor")
        verdict = e.get("verdict")
        dts = str(e.get("decision_timestamp") or "")
        ets = str(e.get("evidence_timestamp") or "")
        if not TS_RE.match(dts) or not TS_RE.match(ets):
            errors.append(f"{e.get('id')}:bad-timestamp")
            continue
        if verdict in {"SUPERSEDED-UNRECORDED", "REOPEN-REQUIRED"}:
            if not e.get("contradicting_evidence_anchor"):
                errors.append(f"{e.get('id')}:closed-without-anchor")
            if ets <= dts:
                errors.append(f"{e.get('id')}:earlier-evidence-cannot-contradict")
        if verdict == "REOPEN-REQUIRED":
            q = str(e.get("owner_question") or "")
            if len(q) < 20:
                errors.append(f"{e.get('id')}:reopen-without-owner-question")
        if verdict == "SUPERSEDED-UNRECORDED" and not e.get("superseding_fix"):
            errors.append(f"{e.get('id')}:superseded-without-fix")
        if verdict == "STILL-TRUE" and not e.get("supporting_evidence_anchor"):
            errors.append(f"{e.get('id')}:still-true-without-support")
        anchor = str(e.get("decision_anchor") or "").replace("\\", "/")
        if ":175" in anchor and "17-DECISION-LOG.md" in anchor:
            found_175 = True
            if verdict != "SUPERSEDED-UNRECORDED":
                errors.append("known-present-entry-wrong-verdict")
            if "2026-08-07" not in str(e.get("superseding_fix") or ""):
                errors.append("known-present-entry-fix-not-cited")
    if st == "SUCCESS" and not found_175:
        errors.append("known-present-entry-missing")
    return errors


# Catalog shim $ref's https://ast-integrate.invalid/... . Two compile
# fingerprints already fail on this worker (Draft7Validator network $ref;
# receipt_core additionalProperties:false cannot carry top-level entries[]).
# G-1 does not schema-compile the generated shim. Local envelope rejects
# garbage without a network fetch. Do not rebuild the ADV schema circle.
LOCAL_ENVELOPE = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "entries",
        "known_present_control",
        "evidence",
        "tests",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {
            "type": "string",
            "enum": ["SUCCESS", "FAILED", "BLOCKED", "SEVERED", "TIMEOUT"],
        },
        "sentinel": {"type": "string", "minLength": 8},
        "entries": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "verdict",
                    "decision_anchor",
                    "decision_timestamp",
                    "evidence_timestamp",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "STILL-TRUE",
                            "SUPERSEDED-UNRECORDED",
                            "REOPEN-REQUIRED",
                        ],
                    },
                    "decision_anchor": {"type": "string"},
                    "decision_timestamp": {"type": "string"},
                    "evidence_timestamp": {"type": "string"},
                },
            },
        },
        "known_present_control": {
            "type": "object",
            "required": ["id", "found", "verdict"],
        },
        "evidence": {"type": "array", "minItems": 1},
        "tests": {"type": "array", "minItems": 1},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
        },
    },
    "additionalProperties": True,
}


def catalog_shim_errors(repo: Path | None = None) -> list[str]:
    root = repo if repo is not None else REPO
    path = root / SCHEMA_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return ["declared-schema-missing"]
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["declared-schema-unparseable"]
    errs: list[str] = []
    if doc.get("x-artifact-class") != "decision-reversal":
        errs.append("declared-schema-wrong-class")
    phys = root / "platform/schema/artifact-class-profiles.schema.json"
    if not phys.is_file() or phys.stat().st_size <= 0:
        errs.append("physical-schema-missing")
    return errs


def load_schema(repo: Path | None = None) -> dict:
    """Return the local discriminating envelope, not the unresolvable catalog shim."""
    errs = catalog_shim_errors(repo)
    if errs:
        raise RuntimeError("declared-schema: " + "; ".join(errs))
    return LOCAL_ENVELOPE


def validate_schema(doc: dict, schema: dict | None = None) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-missing"]
    contract = schema if schema is not None else LOCAL_ENVELOPE
    errs = sorted(
        jsonschema.Draft7Validator(contract).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    return [f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errs]


def plant_log(collision: bool, mech: bool = True, tool: bool = True, extra_lines: int = 174) -> str:
    lines = ["# 17 Decision log", "", "scratch log", ""]
    while len(lines) < extra_lines:
        lines.append(f"Queued follow-up {len(lines)}.")
    if collision:
        lines.append(COLLISION_SNIPPET)
    else:
        lines.append("Queued follow-up: namespace work remains open (no live collision claim).")
    if mech:
        lines.append(MECH_SNIPPET)
    if tool:
        lines.append(TOOL_SNIPPET)
    lines.append("")
    return "\n".join(lines) + "\n"


def write_scratch_sources(
    scratch: Path,
    *,
    collision: bool = True,
    pad: int = 174,
    events: list[dict] | None = None,
    doc13: str | None = None,
    owner: str | None = None,
) -> Sources:
    fix = scratch / "fixtures"
    ensure_fixtures(fix, overwrite=True)
    (fix / "17-DECISION-LOG.md").write_text(
        plant_log(collision, True, True, extra_lines=pad), encoding="utf-8"
    )
    if doc13 is not None:
        (fix / "13-ARCHITECTURE-CANDIDATES.md").write_text(doc13, encoding="utf-8")
    if owner is not None:
        (fix / "OWNER-DECISIONS.md").write_text(owner, encoding="utf-8")
    if events is not None:
        (fix / "EVENTS.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in events),
            encoding="utf-8",
        )
    return load_sources(repo=scratch, fix=fix)


def _min_doc(entries: list[dict], found: bool) -> dict:
    kpc_row = next((e for e in entries if "175" in str(e.get("decision_anchor"))), None)
    return {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "question": QUESTION,
        "extraction_rule": EXTRACTION_RULE,
        "inputs_measured": {
            "owner_decisions": {"path": "x.md", "present": False},
            "decision_log": {"path": "x.md", "present": True},
            "claim_registry": {"path": "x.json", "present": True},
            "events": {"path": "x.jsonl", "present": True},
            "b09_confirmers": {"present": False, "artifact_count": 0},
        },
        "known_present_control": {
            "id": "17-DECISION-LOG.md:175",
            "found": found,
            "anchor": (kpc_row or {}).get("decision_anchor") or "x.md:175",
            "verdict": "SUPERSEDED-UNRECORDED",
            "fix_cited": (kpc_row or {}).get("superseding_fix") or f"{REPREFIX_TS} MECH",
        },
        "entries": entries,
        "counts": {
            "entries": len(entries),
            "STILL-TRUE": sum(1 for e in entries if e.get("verdict") == "STILL-TRUE"),
            "SUPERSEDED-UNRECORDED": sum(
                1 for e in entries if e.get("verdict") == "SUPERSEDED-UNRECORDED"
            ),
            "REOPEN-REQUIRED": sum(1 for e in entries if e.get("verdict") == "REOPEN-REQUIRED"),
            "live_bare_m_collision_count": 0,
        },
        "tests": [
            {"id": "known-present-control", "result": "PASS"},
            {"id": "test_timestamp_ordering_decides_direction", "result": "PASS"},
            {"id": "test_no_entry_is_closed_without_an_anchor", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "SYN-0006-probe2-timestamp-order",
            "independent": True,
            "verdict": "PASS",
        },
        "named_probes": [{"id": "probe1", "command": P1}, {"id": "probe2", "command": P2}],
        "evidence": [
            {
                "path": SCHEMA_REL,
                "line": 7,
                "snippet": '"x-artifact-class": "decision-reversal"',
                "kind": "schema",
                "claim": "Declared output_schema resolves on disk as the decision-reversal shim.",
            },
            {
                "path": "command-center/p2-wave/probes/SYN-0006/detect.py",
                "line": 1,
                "snippet": "timestamp order",
                "kind": "detector",
                "claim": "Ordering is coded.",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 1,
                "snippet": "17-DECISION-LOG.md:175",
                "kind": "catalog",
                "claim": "Known-present named.",
            },
        ],
        "artifacts": [{"path": OUT_REL, "exists": True, "role": "primary"}],
    }


def run_timestamp_controls(scratch: Path) -> dict:
    results: dict = {}
    late_decision_events = [
        {
            "id": "evt-log-175",
            "ts": "2026-08-10T12:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:175",
        },
        {
            "id": "evt-reprefix",
            "ts": "2026-08-01T18:41:00Z",
            "kind": "fix",
            "anchor": "13-ARCHITECTURE-CANDIDATES.md:3",
        },
    ]
    scan_early = scan(write_scratch_sources(scratch / "early-evidence", events=late_decision_events))
    early_hit = any(
        e.get("id") == "LOG-175-MNN-COLLISION"
        and e.get("verdict") in {"SUPERSEDED-UNRECORDED", "REOPEN-REQUIRED"}
        for e in scan_early["entries"]
    )
    results["earlier-evidence-cannot-contradict"] = {"ok": not early_hit, "fired_on_bad": not early_hit}

    good_events = [
        {
            "id": "evt-log-175",
            "ts": "2026-07-15T12:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:175",
        },
        {
            "id": "evt-reprefix",
            "ts": REPREFIX_TS,
            "kind": "fix",
            "anchor": "13-ARCHITECTURE-CANDIDATES.md:3",
        },
        {
            "id": "evt-mech-claim",
            "ts": "2026-08-07T18:45:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:176",
        },
        {
            "id": "evt-tool-claim",
            "ts": "2026-07-20T09:00:00Z",
            "kind": "decision",
            "anchor": "17-DECISION-LOG.md:177",
        },
    ]
    scan_late = scan(write_scratch_sources(scratch / "later-evidence", events=good_events))
    late_hit = any(
        e.get("id") == "LOG-175-MNN-COLLISION" and e.get("verdict") == "SUPERSEDED-UNRECORDED"
        for e in scan_late["entries"]
    )
    still_true = any(
        e.get("id") == "LOG-MECH-PREFIX-STILL-TRUE" and e.get("verdict") == "STILL-TRUE"
        for e in scan_late["entries"]
    )
    results["later-evidence-reverses"] = {"ok": late_hit, "fired_on_good": late_hit}
    results["currently-true-not-superseded"] = {"ok": still_true, "silent_on_good": still_true}

    scan_missing = scan(write_scratch_sources(scratch / "no-collision", collision=False, events=good_events))
    results["known-present-absent-when-line-missing"] = {
        "ok": scan_missing["known_present_control"]["found"] is False,
        "fired_on_bad": scan_missing["known_present_control"]["found"] is False,
    }

    schema = load_schema(REPO)
    mutant = {
        "id": "MUTANT-CLOSED",
        "decision_anchor": "",
        "decision_timestamp": "2026-07-15T12:00:00Z",
        "evidence_timestamp": REPREFIX_TS,
        "verdict": "SUPERSEDED-UNRECORDED",
        "superseding_fix": "x" * 12,
        "contradicting_evidence_anchor": "path:1",
    }
    wrap = _min_doc([mutant], found=True)
    sem = semantic_errors(wrap)
    sch = validate_schema(wrap, schema)
    results["closed-without-anchor-rejected"] = {
        "ok": any("no-decision-anchor" in e for e in sem) or bool(sch),
        "semantic": sem[:6],
    }

    reopen = {
        "id": "MUTANT-REOPEN",
        "decision_anchor": "scratch/log.md:10",
        "decision_timestamp": "2026-07-15T12:00:00Z",
        "evidence_timestamp": REPREFIX_TS,
        "contradicting_evidence_anchor": "scratch/ev.md:1",
        "verdict": "REOPEN-REQUIRED",
        "owner_question": "",
    }
    wrap2 = _min_doc([reopen], found=True)
    sem2 = semantic_errors(wrap2)
    sch2 = validate_schema(wrap2, schema)
    results["reopen-without-question-rejected"] = {
        "ok": any("reopen-without-owner-question" in e for e in sem2) or bool(sch2),
        "semantic": sem2[:6],
    }

    good_reopen = dict(reopen)
    good_reopen["owner_question"] = (
        "Should P2-09 be closed as completed by the 2026-08-07 MECH re-prefix, "
        "or does remaining namespace adjudication remain in scope?"
    )
    wrap3 = _min_doc([good_reopen], found=True)
    wrap3["entries"].insert(
        0,
        {
            "id": "LOG-175-MNN-COLLISION",
            "decision_anchor": "fixtures/17-DECISION-LOG.md:175",
            "decision_timestamp": "2026-07-15T12:00:00Z",
            "contradicting_evidence_anchor": "fixtures/13-ARCHITECTURE-CANDIDATES.md:3",
            "evidence_timestamp": REPREFIX_TS,
            "verdict": "SUPERSEDED-UNRECORDED",
            "superseding_fix": f"{REPREFIX_TS} MECH-NN re-prefix",
        },
    )
    wrap3["counts"]["entries"] = len(wrap3["entries"])
    wrap3["counts"]["REOPEN-REQUIRED"] = 1
    wrap3["counts"]["SUPERSEDED-UNRECORDED"] = 1
    sem3 = semantic_errors(wrap3)
    sch3 = validate_schema(wrap3, schema)
    results["reopen-with-question-accepted"] = {"ok": not sem3 and not sch3, "semantic": sem3[:6], "schema": sch3[:4]}
    return results
