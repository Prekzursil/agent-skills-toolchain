"""Reconstructed CC-0024-style requirement register for BLD-0013.

CC-0024's receipt is not on this worktree. The spec file _USER-PROMPTS.md is
also absent. This register is reconstructed from catalog rows that transcribe
owner requirements and name the units that would bind them.

spec_source_status is CATALOG-TRANSCRIBED, never a claim that the spec file
was read from disk.
"""
from __future__ import annotations

import json
from pathlib import Path

from catalog_units import CATALOG_REL, catalog_path

CC0024_RECEIPT = "command-center/receipts/CC-0024.json"


def spec_file_present(repo: Path) -> bool:
    candidates = [
        repo / "_USER-PROMPTS.md",
        repo / "command-center/_USER-PROMPTS.md",
        repo / "command-center/p2-wave/_USER-PROMPTS.md",
    ]
    return any(p.is_file() for p in candidates)


def cc0024_receipt_present(repo: Path) -> bool:
    return (repo / CC0024_RECEIPT).is_file()


def _anchor(path: str, line: int) -> str:
    return f"{path}:{line}"


def reconstructed_register(repo: Path) -> list[dict]:
    """Bindings under audit, including planted controls.

    Each row carries demanded_mechanism, disjuncts (OR of ANDs), domain_tokens,
    and bound_unit_id (None = unbound / out of scope).
    """
    cat = CATALOG_REL
    rows = [
        {
            "requirement_id": "REQ-MISBIND-AUDIT",
            "demanded_mechanism": (
                "For each binding, compare the requirement's demanded mechanism "
                "against the unit's actual target and classify SATISFIES / "
                "SUBSTITUTES / SUBSET / MIS-BOUND."
            ),
            "spec_anchor": _anchor(cat, 21476),
            "spec_quote": (
                "For each binding, compare the requirement's demanded mechanism "
                "against the unit's actual target and classify SATISFIES / "
                "SUBSTITUTES (different mechanism, needs owner approval) / "
                "SUBSET (partial, name the residue) / MIS-BOUND."
            ),
            "disjuncts": [
                [
                    "demanded mechanism",
                    "SATISFIES",
                    "SUBSTITUTES",
                    "SUBSET",
                    "MIS-BOUND",
                ]
            ],
            "domain_tokens": ["binding", "requirement", "mechanism", "SATISFIES"],
            "bound_unit_id": "BLD-0013",
            "role": "control-true-bind",
        },
        {
            "requirement_id": "REQ-UNBOUND-EXTRACT",
            "demanded_mechanism": (
                "Extract every imperative and every numeric floor from the spec "
                "into machine-readable requirement records, and bind each to the "
                "work unit or units that satisfy it, so an unbound requirement "
                "surfaces as a measured gap."
            ),
            "spec_anchor": _anchor(cat, 25202),
            "spec_quote": (
                "extract every imperative and every numeric floor from "
                "_USER-PROMPTS.md:10473-11437 into machine-readable requirement "
                "records, and bind each to the work unit or units that satisfy it, "
                "so an unbound requirement surfaces as a measured gap"
            ),
            "disjuncts": [
                [
                    "extract every imperative",
                    "numeric floor",
                    "machine-readable requirement records",
                ]
            ],
            "domain_tokens": ["requirement", "bind", "unbound", "extract"],
            "bound_unit_id": "CC-0024",
            "role": "live",
        },
        {
            "requirement_id": "REQ-UNBOUND-EXTRACT",
            "demanded_mechanism": (
                "Extract every imperative and every numeric floor from the spec "
                "into machine-readable requirement records, and bind each to the "
                "work unit or units that satisfy it, so an unbound requirement "
                "surfaces as a measured gap."
            ),
            "spec_anchor": _anchor(cat, 25202),
            "spec_quote": (
                "extract every imperative and every numeric floor from "
                "_USER-PROMPTS.md:10473-11437 into machine-readable requirement "
                "records, and bind each to the work unit or units that satisfy it, "
                "so an unbound requirement surfaces as a measured gap"
            ),
            "disjuncts": [
                [
                    "extract every imperative",
                    "numeric floor",
                    "machine-readable requirement records",
                ]
            ],
            "domain_tokens": ["requirement", "bind", "unbound", "extract"],
            "bound_unit_id": "BLD-0013",
            "role": "live-false-cover",
        },
        {
            "requirement_id": "REQ-FLOOR-DEFICIT",
            "demanded_mechanism": (
                "For every 'at least N' in the spec, publish the measured count "
                "and the deficit, with a counting rule and a planted-duplicate "
                "control."
            ),
            "spec_anchor": _anchor(cat, 21573),
            "spec_quote": (
                "for every 'at least N' in the spec, what is the measured count "
                "and the deficit?"
            ),
            "disjuncts": [["at least n", "measured count", "deficit"]],
            "domain_tokens": ["floor", "count", "deficit", "padding"],
            "bound_unit_id": "BLD-0015",
            "role": "live",
        },
        {
            "requirement_id": "REQ-OWNER-EXTRACT-BIND-UNBOUND",
            "demanded_mechanism": (
                "Extract every imperative AND bind each to a satisfying unit AND "
                "surface unbound requirements individually."
            ),
            "spec_anchor": _anchor(cat, 25202),
            "spec_quote": (
                "extract every imperative and every numeric floor ... bind each "
                "to the work unit or units that satisfy it, so an unbound "
                "requirement surfaces as a measured gap"
            ),
            "disjuncts": [
                [
                    "at least n",
                    "bind each to the work unit",
                    "unbound requirement",
                ]
            ],
            "domain_tokens": ["extract", "bind", "floor", "requirement"],
            "bound_unit_id": "BLD-0015",
            "role": "live-subset",
        },
        {
            "requirement_id": "REQ-DISJUNCT-BUILDER",
            "demanded_mechanism": "a visual OR structured builder",
            "spec_anchor": _anchor(cat, 21481),
            "spec_quote": (
                "a requirement demanding 'a visual OR structured builder' "
                "satisfied by a structured builder must classify SATISFIES, "
                "not SUBSTITUTES"
            ),
            "disjuncts": [["visual builder"], ["structured builder"]],
            "domain_tokens": ["builder", "visual", "structured", "council spec"],
            "bound_unit_id": "IMP-0327",
            "role": "control-disjunction",
        },
        {
            "requirement_id": "REQ-DISJUNCT-BUILDER",
            "demanded_mechanism": "a visual OR structured builder",
            "spec_anchor": _anchor(cat, 21481),
            "spec_quote": (
                "a requirement demanding 'a visual OR structured builder' "
                "satisfied by a structured builder must classify SATISFIES, "
                "not SUBSTITUTES"
            ),
            "disjuncts": [["visual builder"], ["structured builder"]],
            "domain_tokens": ["builder", "visual", "structured", "council spec"],
            "bound_unit_id": "BLD-0014",
            "role": "control-planted-misbind",
        },
        {
            "requirement_id": "REQ-DISJUNCT-BUILDER",
            "demanded_mechanism": "a visual OR structured builder",
            "spec_anchor": _anchor(cat, 21481),
            "spec_quote": (
                "a requirement demanding 'a visual OR structured builder' "
                "satisfied by a structured builder must classify SATISFIES, "
                "not SUBSTITUTES"
            ),
            "disjuncts": [["visual builder"], ["structured builder"]],
            "domain_tokens": ["builder", "visual", "structured", "council spec"],
            "bound_unit_id": "CNL-0128",
            "role": "live-title-not-target",
        },
        {
            "requirement_id": "REQ-CONTRADICTION",
            "demanded_mechanism": (
                "Detect a shipped artifact that contradicts a binding owner "
                "decision, distinct from a missing implementation."
            ),
            "spec_anchor": _anchor(cat, 21524),
            "spec_quote": (
                "which binding owner decision is CONTRADICTED by a shipped "
                "artifact? This is distinct from a missing implementation."
            ),
            "disjuncts": [["contradicted by a shipped artifact"]],
            "domain_tokens": ["contradict", "owner decision", "shipped artifact"],
            "bound_unit_id": "BLD-0014",
            "role": "live",
        },
        {
            "requirement_id": "REQ-TEST-JOIN",
            "demanded_mechanism": (
                "Join CC-0024 requirement records to TEST-REGISTRY.json in both "
                "directions and emit the two orphan sets."
            ),
            "spec_anchor": _anchor(cat, 22912),
            "spec_quote": (
                "Join the CC-0024 requirement records to TEST-REGISTRY.json in "
                "both directions, emit the two orphan sets"
            ),
            "disjuncts": [
                ["join the cc-0024 requirement records to test-registry.json"]
            ],
            "domain_tokens": ["requirement", "test", "orphan", "join"],
            "bound_unit_id": "BLD-0043",
            "role": "live",
        },
        {
            "requirement_id": "REQ-HOST-DRIFT",
            "demanded_mechanism": (
                "For each host-owned integration surface, record the tested "
                "version plus the concrete breakage one release back and one "
                "release forward."
            ),
            "spec_anchor": _anchor(cat, 21428),
            "spec_quote": (
                "for each record the tested version plus the concrete breakage "
                "one release back and one release forward"
            ),
            "disjuncts": [["one-release drift prediction"]],
            "domain_tokens": ["host", "version", "drift", "hook"],
            "bound_unit_id": "BLD-0012",
            "role": "live",
        },
        {
            "requirement_id": "REQ-FLOOR-INDEPENDENT-COUNT",
            "demanded_mechanism": (
                "Recount every numeric floor with a mechanically different "
                "extractor and escalate disagreement."
            ),
            "spec_anchor": _anchor(cat, 34108),
            "spec_quote": (
                "do the program's numeric floors hold under an INDEPENDENT "
                "counter"
            ),
            "disjuncts": [["independent counter", "different extraction path"]],
            "domain_tokens": ["floor", "count", "extract", "numeric"],
            "bound_unit_id": "CNF-0188",
            "role": "live",
        },
        {
            "requirement_id": "REQ-FLOOR-INDEPENDENT-COUNT",
            "demanded_mechanism": (
                "Recount every numeric floor with a mechanically different "
                "extractor and escalate disagreement."
            ),
            "spec_anchor": _anchor(cat, 34108),
            "spec_quote": (
                "do the program's numeric floors hold under an INDEPENDENT "
                "counter"
            ),
            "disjuncts": [["independent counter", "different extraction path"]],
            "domain_tokens": ["floor", "count", "extract", "numeric"],
            "bound_unit_id": "BLD-0015",
            "role": "live-substitute",
        },
        {
            "requirement_id": "REQ-DELIVERABLE-EXISTENCE",
            "demanded_mechanism": (
                "Probe each Final Deliverables list item for on-disk existence, "
                "byte size and sha256."
            ),
            "spec_anchor": _anchor(cat, 21621),
            "spec_quote": (
                "which item on the spec's Final Deliverables list "
                "(_USER-PROMPTS.md:11402-11435) has no artifact on disk?"
            ),
            "disjuncts": [["final deliverables", "byte size", "sha256"]],
            "domain_tokens": ["deliverable", "artifact", "sha256", "disk"],
            "bound_unit_id": "BLD-0016",
            "role": "live",
        },
        {
            "requirement_id": "REQ-UNBOUND-ORPHAN",
            "demanded_mechanism": (
                "A planted unbound owner requirement with no unit binding, "
                "used only to prove BLD-0013 does not treat unbound rows as "
                "MIS-BOUND."
            ),
            "spec_anchor": _anchor(cat, 25202),
            "spec_quote": (
                "an unbound requirement surfaces as a measured gap rather than "
                "an omission nobody notices"
            ),
            "disjuncts": [["unbound requirement surfaces as a measured gap"]],
            "domain_tokens": ["unbound", "requirement", "gap"],
            "bound_unit_id": None,
            "role": "control-unbound",
        },
    ]
    # Prefer live CC-0024 bindings if that receipt exists; keep controls either way.
    live = _try_cc0024(repo)
    if live:
        keep_roles = {
            "control-true-bind",
            "control-disjunction",
            "control-planted-misbind",
            "control-unbound",
        }
        controls = [r for r in rows if r["role"] in keep_roles]
        return controls + live
    return rows


def _try_cc0024(repo: Path) -> list[dict] | None:
    path = repo / CC0024_RECEIPT
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    bindings = doc.get("bindings") or doc.get("requirement_records") or []
    if not isinstance(bindings, list) or not bindings:
        return None
    out = []
    for i, b in enumerate(bindings):
        if not isinstance(b, dict):
            continue
        rid = str(b.get("id") or b.get("requirement_id") or f"CC0024-{i:04d}")
        mech = str(b.get("demanded_mechanism") or b.get("text") or "").strip()
        units = b.get("bound_unit_ids") or b.get("bound_units") or []
        if isinstance(units, str):
            units = [units]
        if not mech:
            continue
        phrases = [w for w in mech.split() if len(w) > 4][:4] or [mech[:40]]
        for uid in units or [None]:
            out.append(
                {
                    "requirement_id": rid,
                    "demanded_mechanism": mech,
                    "spec_anchor": str(b.get("spec_anchor") or CC0024_RECEIPT),
                    "spec_quote": mech[:400],
                    "disjuncts": [phrases],
                    "domain_tokens": phrases[:4],
                    "bound_unit_id": uid,
                    "role": "cc0024-live",
                }
            )
    return out or None


def confirm_spec_quotes(repo: Path, rows: list[dict]) -> None:
    """Each spec_quote must appear in the catalog file (transcribed source)."""
    text = catalog_path(repo).read_text(encoding="utf-8")
    for row in rows:
        q = row["spec_quote"]
        # quotes may wrap JSON escaping of apostrophes; check a distinctive slice
        needle = q.replace("'", "'")[:40]
        if needle not in text and needle.replace("'", "") not in text.replace("\\", ""):
            # allow reconstructed paraphrase only for control-unbound
            if row["role"] == "control-unbound":
                continue
            raise AssertionError(
                f"spec_quote not found in catalog for {row['requirement_id']}: {needle!r}"
            )

def load_register(repo: Path) -> dict:
    rows = reconstructed_register(repo)
    return {
        "cc0024_receipt_present": cc0024_receipt_present(repo),
        "spec_file_present": spec_file_present(repo),
        "source": (
            "CC-0024 receipt" if cc0024_receipt_present(repo)
            else "catalog-transcribed reconstruction (CC-0024 receipt absent)"
        ),
        "bindings": rows,
    }
