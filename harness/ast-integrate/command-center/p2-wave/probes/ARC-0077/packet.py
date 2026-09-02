#!/usr/bin/env python3
"""Mechanical checks for the ARC-0077 owner-ratification packet.

Evaluated on the packet file itself (not on stored checklist booleans):
  1. exactly one foundation-level decision prompt
  2. a recommendation that names a declared option
  3. one-sentence strongest tradeoff
  4. default-if-unanswered is a declared reversible option

Also: durability of the recorded ruling, and default-safety (the default
is the reversible option; the other option is marked irreversible so the
check is not vacuous).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PACKET_REL = "command-center/phase3/ARCHITECTURE-RATIFICATION.json"
OWNER_REL = "command-center/OWNER-DECISIONS.md"
LOG_REL = "command-center/phase3/DECISION-LOG.md"
RULING_ID = "ARC-0077"


def load_json(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    return doc


def load_packet(repo: Path | None = None) -> dict:
    root = repo or REPO
    return load_json(root / PACKET_REL)


def options_by_id(doc: dict) -> dict:
    out = {}
    for row in doc.get("options") or []:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            out[row["id"]] = row
    return out


def count_decision_prompts(doc: dict) -> int:
    prompts = doc.get("decision_prompts")
    if not isinstance(prompts, list):
        return -1
    n = 0
    for row in prompts:
        if not isinstance(row, dict):
            return -1
        prompt = str(row.get("prompt") or "").strip()
        kind = str(row.get("kind") or "")
        if not prompt or kind != "foundation":
            return -1
        n += 1
    return n


def prompt_is_compound(prompt: str) -> bool:
    """A compound question (two interrogatives) fails the single-question rule."""
    return prompt.count("?") != 1


def one_sentence(text: str) -> bool:
    s = text.strip()
    if len(s) < 24:
        return False
    if "\n" in s:
        return False
    return s.endswith(".") and s.count(".") == 1


def four_item_checklist(doc: dict) -> list[dict]:
    """Recompute the spec's four owner-interaction rules on the packet."""
    prompts = doc.get("decision_prompts") if isinstance(doc.get("decision_prompts"), list) else []
    n = count_decision_prompts(doc)
    prompt_text = ""
    if n == 1 and prompts:
        prompt_text = str(prompts[0].get("prompt") or "").strip()
    opts = options_by_id(doc)
    rec = doc.get("recommendation") if isinstance(doc.get("recommendation"), dict) else {}
    rec_choice = rec.get("choice")
    trade = str(doc.get("strongest_tradeoff") or "").strip()
    default = (
        doc.get("default_if_unanswered")
        if isinstance(doc.get("default_if_unanswered"), dict)
        else {}
    )
    def_choice = default.get("choice")
    def_opt = opts.get(def_choice) if isinstance(def_choice, str) else None
    question = str(doc.get("question") or "").strip()
    items = [
        {
            "id": "one_foundation_question",
            "rule": "one foundation-level question at a time",
            "ok": (
                n == 1
                and bool(prompt_text)
                and not prompt_is_compound(prompt_text)
                and question == prompt_text
            ),
        },
        {
            "id": "recommendation",
            "rule": "a recommendation",
            "ok": isinstance(rec_choice, str) and rec_choice in opts and len(str(rec.get("text") or "")) >= 16,
        },
        {
            "id": "strongest_tradeoff",
            "rule": "the strongest tradeoff",
            "ok": one_sentence(trade),
        },
        {
            "id": "default_if_unanswered",
            "rule": "the default if unanswered",
            "ok": (
                isinstance(def_choice, str)
                and def_opt is not None
                and def_opt.get("reversible") is True
                and len(str(default.get("text") or "")) >= 16
            ),
        },
    ]
    return items


def checklist_pass(doc: dict) -> tuple[bool, list[dict]]:
    items = four_item_checklist(doc)
    return all(bool(i["ok"]) for i in items), items


def default_safety(doc: dict) -> tuple[bool, str]:
    """Default must be the reversible option; the other option must not be.

    Vacuity guard: if every option is reversible, the check cannot fail.
    """
    opts = options_by_id(doc)
    if len(opts) < 2:
        return False, "need-two-options"
    reversible = [k for k, v in opts.items() if v.get("reversible") is True]
    irreversible = [k for k, v in opts.items() if v.get("reversible") is False]
    if not reversible:
        return False, "no-reversible-option"
    if not irreversible:
        return False, "vacuous-all-reversible"
    default = doc.get("default_if_unanswered") if isinstance(doc.get("default_if_unanswered"), dict) else {}
    choice = default.get("choice")
    if choice not in reversible:
        return False, f"default-not-reversible:{choice}"
    if choice in irreversible:
        return False, f"default-marked-irreversible:{choice}"
    rec = doc.get("recommendation") if isinstance(doc.get("recommendation"), dict) else {}
    rec_choice = rec.get("choice")
    if rec_choice not in opts:
        return False, "recommendation-unknown"
    return True, "ok"


def durability(repo: Path | None, doc: dict | None = None) -> tuple[bool, str]:
    root = repo or REPO
    packet = doc or load_packet(root)
    dur = packet.get("durability") if isinstance(packet.get("durability"), dict) else {}
    ruling_id = str(dur.get("ruling_id") or RULING_ID)
    owner_rel = str(dur.get("owner_decisions_path") or OWNER_REL).replace("\\", "/")
    log_rel = str(dur.get("decision_log_path") or LOG_REL).replace("\\", "/")
    owner = root / owner_rel
    log = root / log_rel
    if not owner.is_file() or owner.stat().st_size <= 0:
        return False, "owner-decisions-absent"
    if not log.is_file() or log.stat().st_size <= 0:
        return False, "decision-log-absent"
    owner_text = owner.read_text(encoding="utf-8")
    log_text = log.read_text(encoding="utf-8")
    if ruling_id not in owner_text:
        return False, "owner-decisions-missing-ruling-id"
    if ruling_id not in log_text:
        return False, "decision-log-missing-ruling-id"
    applied = packet.get("recorded_ruling") if isinstance(packet.get("recorded_ruling"), dict) else {}
    choice = str(applied.get("choice") or "")
    if choice and choice not in owner_text:
        return False, "owner-decisions-missing-choice"
    if "DEFAULT-APPLIED" not in owner_text and "default-applied" not in owner_text.lower():
        return False, "owner-decisions-missing-default-applied"
    return True, "ok"


def mutant_second_question(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    prompts = list(m.get("decision_prompts") or [])
    prompts.append(
        {
            "id": "Q-MUTANT",
            "kind": "foundation",
            "prompt": "Also, which bikeshed colour should the control plane use?",
        }
    )
    m["decision_prompts"] = prompts
    return m


def mutant_irreversible_default(doc: dict) -> dict:
    m = copy.deepcopy(doc)
    opts = options_by_id(m)
    irreversible = [k for k, v in opts.items() if v.get("reversible") is False]
    if not irreversible:
        raise ValueError("mutant needs an irreversible option")
    choice = irreversible[0]
    default = dict(m.get("default_if_unanswered") or {})
    default["choice"] = choice
    default["text"] = f"MUTANT default locks {choice} which is not reversible."
    m["default_if_unanswered"] = default
    return m
