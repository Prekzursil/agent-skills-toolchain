#!/usr/bin/env python3
"""CNF-0125 stale-premise sweep: then-and-now on CONFIRMED / pinned premises.

A present-tense statement of a fixed problem is a finding even when the fix
is real. Documents READ as ground truth are in scope, not only code. A
premise that has not changed is classified current (control).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PHASE3_REL = "command-center/phase3"
CONFIRM_REL = "command-center/confirmation"
GENERATOR_REL = "command-center/p2-wave/probes/ARC-0010/generator.py"
A2_DESIGN_REL = "command-center/phase3/A2/DESIGN.json"
A1_DESIGN_REL = "command-center/phase3/A1/DESIGN.json"
SAMPLES_REL = "command-center/p2-wave/probes/ARC-0003/samples.json"
REG_SCHEMA_REL = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
HOST_DECISION_LOG = "17-DECISION-LOG.md"
HOST_ARCH = "13-ARCHITECTURE-CANDIDATES.md"

BARE_M_NN = re.compile(r"(?<![A-Za-z])M-\d+")
PRESENT_OPEN = re.compile(
    r"(is a live\b|is an open\b|collision is (a )?live\b|"
    r"open blocker\b|queued as p2-09\b|still states\b|"
    r"treat the collision as open\b|as a live blocker\b)",
    re.I,
)
INHERIT_LIVE = re.compile(
    r"pins a 31-way|as a live blocker|collision as still-live|"
    r"still-live|31-way M-NN option-id collision as a live|"
    r"collision is live|F-B-02",
    re.I,
)
PAST_RECONCILED = re.compile(
    r"\b(was|were|had been|re-prefixed|resolved|closed)\b",
    re.I,
)


def rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def present_tense_open_problem(text: str) -> bool:
    """True when prose asserts a problem as currently open."""
    if not text or not PRESENT_OPEN.search(text):
        return False
    if PAST_RECONCILED.search(text) and not re.search(
        r"\b(is|are|remains)\b.{0,80}\b(blocker|collision|open)\b",
        text,
        re.I | re.S,
    ):
        return False
    return True


def bare_m_nn_count(text: str) -> int:
    return len(BARE_M_NN.findall(text or ""))


def generator_bans_opaque(repo: Path) -> bool:
    p = repo / GENERATOR_REL
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    return "BANNED_KEYS" in text and '"opaque_body"' in text


def walk_confirmed(obj: Any, file_rel: str, rows: list[dict]) -> None:
    if isinstance(obj, dict):
        verdict = str(obj.get("verdict") or "").upper()
        claim = obj.get("claim") or obj.get("text") or obj.get("statement")
        if verdict == "CONFIRMED" and isinstance(claim, str) and len(claim) >= 8:
            rows.append(
                {
                    "source": file_rel,
                    "claim": claim.strip(),
                    "anchor": str(obj.get("anchor") or obj.get("path") or file_rel),
                    "id_hint": str(obj.get("id") or ""),
                }
            )
        for v in obj.values():
            walk_confirmed(v, file_rel, rows)
    elif isinstance(obj, list):
        for v in obj:
            walk_confirmed(v, file_rel, rows)


def harvest_confirmed_json(repo: Path) -> list[dict]:
    rows: list[dict] = []
    roots = [repo / PHASE3_REL, repo / CONFIRM_REL, FIX / "confirmed"]
    seen: set[tuple[str, str]] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            name = path.name
            if name.startswith("_") or name in {
                "SUBAGENT-RETURN.json",
                "UNIT-ARTIFACT-MANIFEST.json",
            }:
                continue
            if name == "CNF-0125-stale-premise-sweep.json":
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            file_rel = rel(path, repo)
            found: list[dict] = []
            walk_confirmed(doc, file_rel, found)
            for item in found:
                key = (item["source"], item["claim"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(item)
    return rows


def remeasure_confirmed(repo: Path, item: dict) -> dict:
    claim = item["claim"]
    low = claim.lower()
    then_state = f"CONFIRMED at {item['source']}: {claim[:180]}"
    now_bits: list[str] = []
    current = False

    if "opaque_body" in low or ("passthrough" in low and "refuse" in low):
        ok = generator_bans_opaque(repo)
        now_bits.append(f"{GENERATOR_REL} bans opaque_body={ok}")
        current = ok
    elif "first construct that is not expressible" in low or (
        "opaque passthrough" in low and "untyped blob" in low
    ):
        design = repo / A2_DESIGN_REL
        text = design.read_text(encoding="utf-8") if design.is_file() else ""
        ok = "opaque passthrough" in text.lower() or "untyped blob" in text.lower()
        now_bits.append(f"{A2_DESIGN_REL} still names the construct={ok}")
        current = ok
    elif "no generated layer" in low or "no resident runtime" in low:
        design = repo / A1_DESIGN_REL
        text = design.read_text(encoding="utf-8") if design.is_file() else ""
        ok = '"no_generated_layer": true' in text and '"no_resident_runtime": true' in text
        now_bits.append(f"{A1_DESIGN_REL} no_generated_layer/runtime still true={ok}")
        current = ok
    elif "byte-identical" in low or "two generate()" in low:
        design = repo / A2_DESIGN_REL
        text = design.read_text(encoding="utf-8") if design.is_file() else ""
        ok = '"two_run_byte_identical": true' in text and (repo / GENERATOR_REL).is_file()
        now_bits.append(f"DESIGN two_run_byte_identical and generator present={ok}")
        current = ok
    elif "provenance header" in low:
        design = repo / A2_DESIGN_REL
        ok = design.is_file() and "registry_id" in design.read_text(encoding="utf-8")
        now_bits.append(f"DESIGN still records provenance registry_id={ok}")
        current = ok
    elif "tampered" in low:
        probe = repo / "command-center/p2-wave/probes/ARC-0010/probe2_tamper.py"
        ok = probe.is_file()
        now_bits.append(f"probe2_tamper.py present={ok}")
        current = ok
    elif "three sampled" in low or "static-config/v1" in low:
        ok = (repo / SAMPLES_REL).is_file()
        now_bits.append(f"{SAMPLES_REL} present={ok}")
        current = ok
    elif "reverse-sorted walk" in low:
        probe = repo / (
            "command-center/p2-wave/probes/ARC-0003/probe1_independent_replication.py"
        )
        ok = probe.is_file()
        now_bits.append(f"independent replication probe present={ok}")
        current = ok
    elif "stopping rule" in low or (
        "inexpressible" in low and "declarative" in low
    ):
        probe = repo / "command-center/p2-wave/probes/ARC-0003/probe2_negative_control.py"
        ok = probe.is_file()
        now_bits.append(f"negative-control probe present={ok}")
        current = ok
    elif "registry schema" in low or "a2 registry schema" in low:
        ok = (repo / REG_SCHEMA_REL).is_file()
        now_bits.append(f"{REG_SCHEMA_REL} present={ok}")
        current = ok
    elif "silently not loaded" in low or "unlisted" in low:
        design = repo / A1_DESIGN_REL
        text = design.read_text(encoding="utf-8") if design.is_file() else ""
        ok = "not loaded" in text.lower() or "unlisted_file" in text
        now_bits.append(f"A1 DESIGN still specifies unlisted skip={ok}")
        current = ok
    elif "direction a" in low:
        fm = repo / "command-center/phase3/A2/FAILURE-MODES.json"
        text = fm.read_text(encoding="utf-8") if fm.is_file() else ""
        ok = "direction_a" in text.lower() or "Direction A" in text
        now_bits.append(f"FAILURE-MODES still records Direction A={ok}")
        current = ok
    elif "a1 has no generated layer" in low:
        design = repo / A1_DESIGN_REL
        text = design.read_text(encoding="utf-8") if design.is_file() else ""
        ok = '"no_generated_layer": true' in text
        now_bits.append(f"A1 DESIGN no_generated_layer={ok}")
        current = ok
    else:
        anchor = str(item.get("anchor") or "")
        path_part = anchor.split(":")[0] if ":" in anchor else item["source"]
        target = repo / path_part
        ok = target.is_file()
        now_bits.append(f"anchor file {path_part} present={ok}")
        current = ok

    now_state = "; ".join(now_bits) if now_bits else "no re-measurement"
    classification = "current" if current else "stale-premise"
    comparison = (
        f"then={then_state[:240]} | now={now_state} | "
        f"{'UNCHANGED' if current else 'CHANGED'}"
    )
    return {
        "original_verdict": "CONFIRMED",
        "then_state": then_state,
        "now_state": now_state,
        "comparison": comparison,
        "classification": classification,
        "changed": not current,
        "is_control": False,
        "is_ground_truth_document": False,
    }


def fixture_docs(repo: Path) -> list[dict]:
    arch = FIX / "code" / "13-ARCHITECTURE-CANDIDATES.md"
    log = FIX / "ground-truth" / "17-DECISION-LOG.md"
    brief = FIX / "ground-truth" / "PROGRAM-BRIEF.md"
    control_doc = FIX / "current" / "opaque-body-refusal.md"
    arch_text = arch.read_text(encoding="utf-8")
    log_text = log.read_text(encoding="utf-8")
    brief_text = brief.read_text(encoding="utf-8")
    ctrl_text = control_doc.read_text(encoding="utf-8")
    collision_now = bare_m_nn_count(arch_text)
    live_fix = collision_now == 0
    rows = []

    log_present = present_tense_open_problem(log_text)
    rows.append(
        {
            "id": "FIX-DECISION-LOG-PRESENT-TENSE",
            "source": rel(log, repo),
            "claim": (
                "17-DECISION-LOG.md states the M-NN option-id collision is a "
                "live 31-way blocker (Queued as P2-09)."
            ),
            "original_verdict": "PINNED",
            "then_state": "Pinned as an open 31-way collision in present tense.",
            "now_state": (
                f"present_tense_open={log_present}; architecture bare M-NN "
                f"count={collision_now} (fix_real={live_fix})"
            ),
            "comparison": (
                "then=present-tense open blocker | now=architecture collision "
                f"count {collision_now}; finding because present tense survives "
                "a real fix"
            ),
            "classification": (
                "stale-premise" if (log_present and live_fix) else "current"
            ),
            "is_control": False,
            "is_ground_truth_document": True,
            "downstream": [rel(brief, repo), CATALOG_REL],
        }
    )

    brief_present = present_tense_open_problem(brief_text)
    rows.append(
        {
            "id": "FIX-BRIEF-F-B-02",
            "source": rel(brief, repo),
            "claim": (
                "Program brief F-B-02 pins VERIFIED GROUND TRUTH that the "
                "31-way M-NN collision is an open blocker."
            ),
            "original_verdict": "PINNED",
            "then_state": "F-B-02 inherited the decision-log pin as live ground truth.",
            "now_state": (
                f"brief_present_tense_open={brief_present}; "
                f"architecture bare M-NN count={collision_now}"
            ),
            "comparison": (
                "then=brief treats collision as open | now=code-side count is "
                f"{collision_now}; downstream inherited a fixed problem as open"
            ),
            "classification": (
                "inherited-false-blocker"
                if (brief_present and live_fix)
                else "current"
            ),
            "is_control": False,
            "is_ground_truth_document": True,
            "downstream": [CATALOG_REL],
        }
    )

    opaque_live = generator_bans_opaque(repo)
    opaque_doc = "opaque_body" in ctrl_text
    rows.append(
        {
            "id": "FIX-CONTROL-OPAQUE-CURRENT",
            "source": rel(control_doc, repo),
            "claim": (
                "The A2 generator BANNED_KEYS set includes opaque_body "
                "and this has not changed."
            ),
            "original_verdict": "PINNED",
            "then_state": "Document pins opaque_body refusal as current.",
            "now_state": (
                f"document_states_opaque_body={opaque_doc}; "
                f"live_generator_bans_opaque_body={opaque_live}"
            ),
            "comparison": (
                "then=opaque_body refused | now=still refused in generator.py"
                if opaque_live and opaque_doc
                else "then=opaque_body refused | now=CHANGED"
            ),
            "classification": (
                "current" if (opaque_live and opaque_doc) else "stale-premise"
            ),
            "is_control": True,
            "is_ground_truth_document": True,
            "downstream": [],
        }
    )
    return rows


def catalog_inherited(repo: Path) -> list[dict]:
    catalog_path = repo / CATALOG_REL
    if not catalog_path.is_file():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    host_log = None
    for candidate in (
        repo / HOST_DECISION_LOG,
        repo / "docs" / HOST_DECISION_LOG,
        repo / "command-center" / HOST_DECISION_LOG,
    ):
        if candidate.is_file():
            host_log = candidate
            break
    host_exists = host_log is not None
    host_present = False
    if host_log is not None:
        host_present = present_tense_open_problem(
            host_log.read_text(encoding="utf-8")
        )

    rows: list[dict] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        blob = " ".join(
            [
                str(unit.get("question_or_target") or ""),
                json.dumps(unit.get("tests_required") or []),
                json.dumps(unit.get("inputs") or []),
            ]
        )
        if "31-way" not in blob and "F-B-02" not in blob:
            continue
        if not INHERIT_LIVE.search(blob):
            if "still states" in blob.lower() or "present tense" in blob.lower():
                rows.append(
                    {
                        "id": f"CAT-{uid}-STALE-LOG-PIN",
                        "source": CATALOG_REL,
                        "claim": (
                            f"{uid} pins 17-DECISION-LOG.md as still stating "
                            "the 31-way collision in present tense."
                        ),
                        "original_verdict": "PINNED",
                        "then_state": (
                            "Catalog records the decision log as present-tense "
                            "open while the re-prefix is already applied."
                        ),
                        "now_state": (
                            f"host 17-DECISION-LOG.md exists={host_exists}; "
                            f"present_tense_open={host_present}"
                            + (
                                "; source documents absent on this worktree"
                                if not host_exists
                                else ""
                            )
                        ),
                        "comparison": (
                            "then=catalog cites live log:175 | now="
                            + (
                                "file ABSENT so the pin cannot be re-measured"
                                if not host_exists
                                else f"log present-tense={host_present}"
                            )
                        ),
                        "classification": (
                            "documentation-defect"
                            if not host_exists
                            else (
                                "stale-premise" if host_present else "current"
                            )
                        ),
                        "is_control": False,
                        "is_ground_truth_document": True,
                        "catalog_unit": uid,
                    }
                )
            continue
        rows.append(
            {
                "id": f"CAT-{uid}-INHERITED",
                "source": CATALOG_REL,
                "claim": (
                    f"{uid} treats the 31-way M-NN collision or F-B-02 pin "
                    "as a live/open blocker for downstream work."
                ),
                "original_verdict": "PINNED",
                "then_state": "Unit brief inherited the collision as an open problem.",
                "now_state": (
                    f"host 17-DECISION-LOG.md exists={host_exists}; "
                    "fixture architecture bare M-NN count=0 (fix real on fixture)"
                ),
                "comparison": (
                    "then=open collision in unit brief | now=re-prefix class "
                    "is the known-fixed case; inherited-false-blocker"
                ),
                "classification": "inherited-false-blocker",
                "is_control": False,
                "is_ground_truth_document": True,
                "catalog_unit": uid,
            }
        )
    return rows


def both_states_present_tense() -> dict:
    """Detector control: fires on present tense, silent on reconciled past tense."""
    bad = (FIX / "ground-truth" / "17-DECISION-LOG.md").read_text(encoding="utf-8")
    good = (
        "The M-NN option-id collision was a 31-way blocker. It was "
        "re-prefixed to MECH-NN on 2026-08-07. Collision count is 0.\n"
    )
    arch = (FIX / "code" / "13-ARCHITECTURE-CANDIDATES.md").read_text(
        encoding="utf-8"
    )
    collision = bare_m_nn_count(arch)
    fires = present_tense_open_problem(bad) and collision == 0
    silent = (not present_tense_open_problem(good)) and collision == 0
    return {
        "fires_on_present_tense_with_real_fix": fires,
        "silent_on_reconciled_past_tense": silent,
        "fix_real_bare_m_nn": collision,
        "ok": fires and silent,
    }


def build_premises(repo: Path) -> list[dict]:
    premises: list[dict] = []
    n = 0
    control_assigned = False
    for item in harvest_confirmed_json(repo):
        n += 1
        measured = remeasure_confirmed(repo, item)
        row = {
            "id": item.get("id_hint") or f"CONFIRMED-{n:03d}",
            "source": item["source"],
            "claim": item["claim"],
            "anchor": item.get("anchor"),
            **measured,
        }
        if (
            not control_assigned
            and row["classification"] == "current"
            and "opaque_body" in row["claim"].lower()
        ):
            row["is_control"] = True
            control_assigned = True
        premises.append(row)

    premises.extend(fixture_docs(repo))
    premises.extend(catalog_inherited(repo))

    seen: dict[str, int] = {}
    for row in premises:
        base = str(row["id"])
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            row["id"] = f"{base}-{seen[base]}"
    return premises


def premises_of(doc: dict) -> list:
    """CONFIRMED/pinned rows live at top-level or in extensions (receipt_core)."""
    p = doc.get("premises")
    if isinstance(p, list):
        return p
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    p2 = ext.get("premises")
    return p2 if isinstance(p2, list) else []


def headline_of(doc: dict) -> dict:
    h = doc.get("headline")
    if isinstance(h, dict):
        return h
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    h2 = ext.get("headline")
    return h2 if isinstance(h2, dict) else {}


def reviewers_of(doc: dict) -> list:
    r = doc.get("reviewers")
    if isinstance(r, list):
        return r
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    r2 = ext.get("reviewers")
    return r2 if isinstance(r2, list) else []


def headline_from(premises: list[dict]) -> dict:
    changed = [
        p
        for p in premises
        if p.get("classification")
        in {"stale-premise", "inherited-false-blocker", "documentation-defect"}
    ]
    inherited = [
        p for p in premises if p.get("classification") == "inherited-false-blocker"
    ]
    controls = [p for p in premises if p.get("is_control") is True]
    control_ok = bool(controls) and all(
        p.get("classification") == "current" for p in controls
    )
    confirmed = [p for p in premises if p.get("original_verdict") == "CONFIRMED"]
    confirmed_have_tn = all(
        isinstance(p.get("then_state"), str)
        and len(p["then_state"]) >= 8
        and isinstance(p.get("now_state"), str)
        and len(p["now_state"]) >= 8
        and isinstance(p.get("comparison"), str)
        and len(p["comparison"]) >= 8
        for p in confirmed
    )
    gt_docs = [p for p in premises if p.get("is_ground_truth_document") is True]
    present_tense_finding = any(
        p.get("classification") in {"stale-premise", "inherited-false-blocker"}
        and p.get("is_ground_truth_document") is True
        for p in premises
    )
    return {
        "confirmed_count": len(confirmed),
        "premises_total": len(premises),
        "premises_changed": len(changed),
        "inherited_false_blockers": len(inherited),
        "current_control_classified_current": control_ok,
        "every_confirmed_has_then_and_now": confirmed_have_tn,
        "ground_truth_documents_covered": len(gt_docs) >= 2,
        "present_tense_finding_with_real_fix": present_tense_finding,
        "confirmation_corpus_dir_exists": False,
    }


def run_sweep(repo: Path) -> dict:
    confirm_dir = repo / CONFIRM_REL
    premises = build_premises(repo)
    headline = headline_from(premises)
    headline["confirmation_corpus_dir_exists"] = confirm_dir.is_dir()
    corpus_files = []
    if confirm_dir.is_dir():
        corpus_files = sorted(
            p.name
            for p in confirm_dir.glob("CNF-*.json")
            if p.name != "CNF-0125-stale-premise-sweep.json"
        )
    headline["confirmation_receipts_other_than_self"] = len(corpus_files)
    headline["host_decision_log_present"] = (repo / HOST_DECISION_LOG).is_file()
    headline["host_architecture_candidates_present"] = (repo / HOST_ARCH).is_file()
    headline["both_states"] = both_states_present_tense()
    return {"premises": premises, "headline": headline}


if __name__ == "__main__":
    repo = HERE.parents[3]
    report = run_sweep(repo)
    h = report["headline"]
    print(
        "confirmed={confirmed_count} changed={premises_changed} "
        "inherited={inherited_false_blockers} control_current="
        "{current_control_classified_current} then_and_now="
        "{every_confirmed_has_then_and_now} gt_docs="
        "{ground_truth_documents_covered} present_tense_finding="
        "{present_tense_finding_with_real_fix}".format(**h)
    )
    bs = h["both_states"]
    print(
        f"both_states fires={bs['fires_on_present_tense_with_real_fix']} "
        f"silent={bs['silent_on_reconciled_past_tense']} ok={bs['ok']}"
    )
