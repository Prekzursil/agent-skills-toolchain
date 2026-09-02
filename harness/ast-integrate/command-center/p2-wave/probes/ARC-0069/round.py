"""Blind independent scoring round: isolated submissions, full-read gate, unanimity."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deidentify import leak_hits, scrub
from fixtures import FIXTURE_ENTRIES, GATE, LIVE_LENS, LENS_KEYS, PANEL, RUBRIC
from gate import admit
from judges import (
    apply_nameless_abstention_rule,
    dimension_signature,
    forced_dissent,
    score_entry,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUBMISSIONS = HERE / "submissions"
ENTRY_IDS = [f"E-0{i}" for i in range(1, 10)]
LIVE_INPUTS = {
    "rubric": [
        "command-center/phase3/RUBRIC.json",
        "command-center/phase3/RUBRIC.json",
    ],
    "panel": [
        "command-center/phase3/JUDGE-PANEL.json",
        "command-center/phase3/JUDGE-PANEL.json",
    ],
    "gate": [
        "command-center/phase3/FULL-READ-GATE.json",
        "command-center/phase3/FULL-READ-GATE.json",
    ],
    "bundle": [
        "command-center/phase3/BLIND-BUNDLE/INDEX.json",
        "command-center/phase3/BLIND-BUNDLE/INDEX.json",
    ],
}


def _first_existing(rels: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    for rel in rels:
        path = REPO / rel
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8")), rel
    return None, None


def resolve_inputs() -> dict[str, Any]:
    found: dict[str, Any] = {}
    for key, rels in LIVE_INPUTS.items():
        doc, rel = _first_existing(rels)
        found[key] = {"present": doc is not None, "path": rel, "used": "live" if doc else "fixture"}
    return {
        "live": found,
        "rubric": _first_existing(LIVE_INPUTS["rubric"])[0] or RUBRIC,
        "panel": _first_existing(LIVE_INPUTS["panel"])[0] or PANEL,
        "gate": _first_existing(LIVE_INPUTS["gate"])[0] or GATE,
        "honest_note": (
            "ARC-0066/0067/0068/0002 outputs are absent on this worktree. "
            "This unit uses probe-local fixtures and does not write those paths. "
            "Not an ADV rebuild of A3–A9."
        ),
    }


def _lift_nested(merged: dict[str, Any]) -> None:
    del merged  # unused; live sections stay as lens keys only


def _merge_live(eid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    meta: dict[str, Any] = {"entry_id": eid, "origin": "fixture", "lenses": []}
    merged: dict[str, Any] = {}
    used_live = False
    for rel in LIVE_LENS[eid]:
        path = REPO / rel
        key = LENS_KEYS[Path(rel).name]
        present = path.is_file()
        meta["lenses"].append({"path": rel, "present": present, "section": key})
        if not present:
            continue
        used_live = True
        merged[key] = scrub(json.loads(path.read_text(encoding="utf-8")))
    if not used_live:
        return FIXTURE_ENTRIES[eid], meta
    merged["digest"] = {"one_paragraph": "de-identified live dossier digest"}
    meta["origin"] = "live-deidentified"
    return merged, meta


def build_entries() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    sealed: dict[str, Any] = {"note": "not judge-visible", "map": {}}
    for eid in ENTRY_IDS:
        if eid in LIVE_LENS:
            doc, meta = _merge_live(eid)
        else:
            doc = FIXTURE_ENTRIES[eid]
            meta = {
                "entry_id": eid,
                "origin": "fixture",
                "reason": (
                    "phase3 live dossier set absent; ARC-0067 blind bundle absent; "
                    "fixture used so the scoring-round procedure can run. "
                    "Not an ADV rebuild of A3–A9."
                ),
            }
        meta["leak_hits"] = leak_hits(doc)
        entries[eid] = doc
        sealed["map"][eid] = meta
    return entries, sealed


def judge_ids(panel: dict[str, Any]) -> list[str]:
    judges = panel.get("judges") or PANEL["judges"]
    ids = [
        j["id"]
        for j in judges
        if isinstance(j, dict) and j.get("id") in ("J-A", "J-B", "J-C")
    ]
    if len(ids) >= 3:
        return ids[:3]
    return [j["id"] for j in PANEL["judges"]]


def _write_isolated(judge_id: str, entry_id: str, card: dict[str, Any]) -> Path:
    dest = SUBMISSIONS / judge_id
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{entry_id}.json"
    body = json.dumps(card, indent=2, sort_keys=True) + "\n"
    path.write_text(body, encoding="utf-8")
    return path


def first_pass(
    judge_id: str,
    entries: dict[str, dict[str, Any]],
    peer_dirs_unread: list[str],
) -> list[dict[str, Any]]:
    cards = []
    for eid, dossier in entries.items():
        dims = apply_nameless_abstention_rule(score_entry(judge_id, dossier))
        card: dict[str, Any] = {
            "judge_id": judge_id,
            "entry_id": eid,
            "dimensions": dims,
            "read_set": ["rubric", f"entry:{eid}"],
            "peer_scorecards_in_read_set": [],
            "peer_dirs_present_on_disk_but_unread": list(peer_dirs_unread),
            "pass": "first",
        }
        gate_row = admit(dossier, card)
        card["gate"] = gate_row["gate"]
        card["coverage"] = gate_row["coverage"]
        path = _write_isolated(judge_id, eid, card)
        card["submission_path"] = str(path.relative_to(REPO)).replace("\\", "/")
        card["mtime_ns"] = path.stat().st_mtime_ns
        cards.append(card)
        time.sleep(0.002)
    return cards


def unanimous_entries(cards: list[dict[str, Any]]) -> list[str]:
    by_entry: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        by_entry.setdefault(card["entry_id"], []).append(card)
    hits = []
    for eid, group in by_entry.items():
        if len(group) < 2:
            continue
        sigs = [dimension_signature(c["dimensions"]) for c in group]
        if len(set(sigs)) == 1:
            hits.append(eid)
    return sorted(hits)


def apply_unanimity(
    cards: list[dict[str, Any]],
    entries: dict[str, dict[str, Any]],
    triggered: list[str],
) -> list[dict[str, Any]]:
    standing: list[dict[str, Any]] = []
    for card in cards:
        if card["entry_id"] not in triggered:
            card["standing"] = True
            card["instant_unanimity"] = False
            standing.append(card)
            continue
        card["standing"] = False
        card["instant_unanimity"] = True
        card["superseded"] = True
        reeval = dict(card)
        reeval["pass"] = "forced-dissent"
        reeval["dimensions"] = apply_nameless_abstention_rule(
            forced_dissent(card["judge_id"], card["dimensions"])
        )
        gate_row = admit(entries[card["entry_id"]], reeval)
        reeval["gate"] = gate_row["gate"]
        reeval["coverage"] = gate_row["coverage"]
        reeval["standing"] = True
        reeval["instant_unanimity"] = True
        reeval["first_pass_superseded"] = True
        path = _write_isolated(
            card["judge_id"], f"{card['entry_id']}.forced-dissent", reeval
        )
        reeval["submission_path"] = str(path.relative_to(REPO)).replace("\\", "/")
        reeval["mtime_ns"] = path.stat().st_mtime_ns
        standing.append(reeval)
    return standing


def run_round() -> dict[str, Any]:
    inputs = resolve_inputs()
    entries, sealed = build_entries()
    panel = inputs["panel"] if isinstance(inputs["panel"].get("judges"), list) else PANEL
    jids = judge_ids(panel)
    if SUBMISSIONS.exists():
        for old in SUBMISSIONS.glob("*/*.json"):
            old.unlink()
    SUBMISSIONS.mkdir(parents=True, exist_ok=True)
    all_first: list[dict[str, Any]] = []
    isolation: list[dict[str, Any]] = []
    completed: list[str] = []
    for jid in jids:
        t0 = datetime.now(timezone.utc).isoformat()
        cards = first_pass(jid, entries, peer_dirs_unread=list(completed))
        t1 = datetime.now(timezone.utc).isoformat()
        isolation.append(
            {
                "judge_id": jid,
                "started_at": t0,
                "finished_at": t1,
                "submissions": len(cards),
                "peer_dirs_unread": list(completed),
            }
        )
        all_first.extend(cards)
        completed.append(jid)
        time.sleep(0.003)
    triggered = unanimous_entries(all_first)
    standing = apply_unanimity(all_first, entries, triggered)
    admitted = [c for c in standing if c.get("standing") and c.get("gate") == "PASS"]
    rejected = [c for c in standing if c.get("standing") and c.get("gate") != "PASS"]
    rubric_raw = json.dumps(RUBRIC, sort_keys=True).encode("utf-8")
    return {
        "inputs": inputs,
        "entries": entries,
        "sealed": sealed,
        "judges": jids,
        "isolation": isolation,
        "first_pass": all_first,
        "triggered": triggered,
        "standing": standing,
        "admitted": admitted,
        "rejected": rejected,
        "rubric_sha256": hashlib.sha256(rubric_raw).hexdigest(),
        "entry_ids": ENTRY_IDS,
    }
