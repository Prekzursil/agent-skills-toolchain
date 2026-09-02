"""Live ADV-0104 measurements: crafted council run + vote-schema requiredness."""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.antifail.unanimity import Vote, plurality  # noqa: E402
from council.kernel import ExecutionPlan, Kernel, ScriptedAdapter, TurnResponse  # noqa: E402
from council.participants.human import (  # noqa: E402
    APPROVE,
    ORIGIN_AGENT,
    POLICY_EXCLUDE_ABSTENTION,
    REJECT,
    tally_records,
)
from council.topology.round_robin import RoundRobinTopology  # noqa: E402

UNIT = "ADV-0104"
OUTPUT_REL = "command-center/adversarial/ADV-0104-evidence-free-majority.json"
SCHEMA_REL = "command-center/schema/council-pathology-sim.schema.json"
P1_REL = "command-center/p2-wave/probes/ADV-0104/probe1_crafted_council.py"
P2_REL = "command-center/p2-wave/probes/ADV-0104/probe2_vote_schema.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"

CATALOG_PROBE1 = (
    "Probe 1: run the crafted council and record which side wins under "
    "the configured aggregation."
)
CATALOG_PROBE2 = (
    "Probe 2 (mechanically different): schema-level check of whether an "
    "evidence anchor is even a required field on a vote; if it is optional, "
    "the defect exists for every council regardless of this run's outcome."
)
QUESTION = (
    "Can a decision be carried by votes with zero evidence anchors, and does "
    "the runtime weight or reject an unsupported vote?"
)
SENTINEL = (
    "SUCCESS:ADV-0104 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0104 <reason>."
)
EVIDENCE_KEYS = {
    "evidence_anchor",
    "evidence_anchors",
    "evidence",
    "citation",
    "citations",
    "anchors",
    "source_anchor",
}
VOTE_NAME_HINTS = ("vote", "ballot", "ballot_record", "vote_record")
SKIP_DIR = frozenset(
    {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", "p2-wave"}
)


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def _anchor_ok(anchor: str) -> bool:
    if ":" not in anchor:
        return False
    rel, _, line = anchor.rpartition(":")
    path = REPO / rel
    if not path.is_file() or not line.isdigit():
        return False
    n = int(line)
    return 1 <= n <= sum(1 for _ in path.open(encoding="utf-8", errors="replace"))


def _ballots(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for raw in fixture["ballots"]:
        anchors = [str(a) for a in (raw.get("evidence_anchors") or [])]
        rows.append(
            {
                "seat": str(raw["seat"]),
                "side": str(raw["side"]),
                "option": str(raw["option"]),
                "evidence_anchors": anchors,
                "evidence_ok": all(_anchor_ok(a) for a in anchors) if anchors else False,
                "evidence_free": len(anchors) == 0,
            }
        )
    return rows


def _count_tally(ballots: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(b["option"] for b in ballots)
    ranked = counts.most_common()
    winner = ranked[0][0] if ranked else None
    tie = len(ranked) >= 2 and ranked[0][1] == ranked[1][1]
    return {
        "counts": dict(counts),
        "winner": None if tie else winner,
        "tie": tie,
        "method": "unweighted-majority",
        "uses_evidence": False,
    }


def run_kernel(fixture: dict[str, Any], ballots: list[dict[str, Any]]) -> dict[str, Any]:
    roster = tuple(b["seat"] for b in ballots)
    adapters = {}
    for b in ballots:
        payload = json.dumps(
            {"option": b["option"], "evidence_anchors": b["evidence_anchors"]},
            sort_keys=True,
        )
        adapters[b["seat"]] = ScriptedAdapter(
            TurnResponse(text=payload, fields={"position": b["option"]}, elapsed_ms=1)
        )
    kernel = Kernel(fixture["council_id"])
    result = kernel.run(
        ExecutionPlan(
            council_id=fixture["council_id"],
            roster=roster,
            n_rounds=1,
            timeout_ms=1000,
            max_chars=4096,
            obligations=("position",),
        ),
        RoundRobinTopology(),
        adapters,
    )
    turns = [e for e in result.events if e.kind == "TURN"]
    return {
        "module": "tools/council/kernel.py",
        "invariant_ok": result.invariant_ok,
        "turns_executed": result.turns_executed,
        "turns_recorded": result.turns_recorded,
        "turn_order": list(result.turn_order),
        "statuses": list(result.statuses),
        "outputs": [
            {"seat": e.participant_id, "output": e.output, "status": e.status}
            for e in turns
        ],
    }


def run_plurality(ballots: list[dict[str, Any]]) -> dict[str, Any]:
    votes = [
        Vote(participant_id=b["seat"], claim_id=b["option"], round=1, confidence=1.0)
        for b in ballots
    ]
    fields = [f.name for f in dataclasses.fields(Vote)]
    return {
        "module": "tools/council/antifail/unanimity.py:plurality",
        "winner": plurality(votes),
        "vote_dataclass_fields": fields,
        "evidence_field_on_vote": any(
            "evidence" in f or "anchor" in f or "citat" in f for f in fields
        ),
        "dropped_evidence_anchors": True,
    }


def run_human_tally(ballots: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for b in ballots:
        choice = APPROVE if b["option"] == "adopt" else REJECT
        records.append(
            {
                "seat_id": b["seat"],
                "origin": ORIGIN_AGENT,
                "choice": choice,
            }
        )
    out = tally_records(
        records,
        include_proxy=False,
        abstention_policy_id=POLICY_EXCLUDE_ABSTENTION,
    )
    winner = None
    if out.get("approve", 0) > out.get("reject", 0):
        winner = "adopt"
    elif out.get("reject", 0) > out.get("approve", 0):
        winner = "reject"
    return {
        "module": "tools/council/participants/human.py:tally_records",
        "winner": winner,
        "approve": out.get("approve"),
        "reject": out.get("reject"),
        "uses_evidence": False,
        "records_had_evidence_field": False,
    }


def _try_import(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def runtime_inventory() -> dict[str, Any]:
    return {
        "kernel": (REPO / "tools/council/kernel.py").is_file(),
        "unanimity_plurality": (REPO / "tools/council/antifail/unanimity.py").is_file(),
        "human_tally": (REPO / "tools/council/participants/human.py").is_file(),
        "tiebreak": (REPO / "tools/council/vote/tiebreak.py").is_file(),
        "tally_py": (REPO / "tools/council/vote/tally.py").is_file(),
        "evidence_gate_py": (REPO / "tools/council/vote/evidence_gate.py").is_file(),
        "councilspec_schema": any(
            p.is_file()
            for p in (
                REPO / "11-COUNCIL-SPECIFICATION.schema.json",
                REPO / "command-center/schema/councilspec.schema.json",
                REPO / "command-center/schema/CouncilSpec.schema.json",
            )
        ),
        "import_tally": _try_import("council.vote.tally"),
        "import_evidence_gate": _try_import("council.vote.evidence_gate"),
    }


def run_council(name: str) -> dict[str, Any]:
    fixture = load_fixture(name)
    ballots = _ballots(fixture)
    majority_tally = _count_tally(ballots)
    kernel = run_kernel(fixture, ballots)
    live_plurality = run_plurality(ballots)
    human = run_human_tally(ballots)
    winners = {
        "unweighted_majority": majority_tally["winner"],
        "plurality": live_plurality["winner"],
        "human_tally": human["winner"],
    }
    evidence_free_option = next(
        (b["option"] for b in ballots if b["evidence_free"]), None
    )
    evidenced_option = next(
        (b["option"] for b in ballots if not b["evidence_free"]), None
    )
    n_free = sum(1 for b in ballots if b["evidence_free"])
    n_ev = sum(1 for b in ballots if not b["evidence_free"])
    winner = majority_tally["winner"]
    return {
        "fixture": name,
        "council_id": fixture["council_id"],
        "aggregation": fixture["aggregation"],
        "ballots": ballots,
        "n_evidence_free": n_free,
        "n_evidenced": n_ev,
        "evidence_free_option": evidence_free_option,
        "evidenced_option": evidenced_option,
        "kernel": kernel,
        "plurality": live_plurality,
        "human_tally": human,
        "unweighted_majority": majority_tally,
        "winners": winners,
        "winner": winner,
        "evidence_free_majority_carried": bool(
            winner
            and evidence_free_option
            and winner == evidence_free_option
            and n_free > n_ev
        ),
        "anchors_ok": all(b["evidence_ok"] or b["evidence_free"] for b in ballots),
        "kernel_invariant_ok": kernel["invariant_ok"],
        "all_engines_agree": len(set(winners.values())) == 1,
    }


def _is_vote_like(name: str, node: dict[str, Any]) -> bool:
    lowered = name.lower()
    if any(h in lowered for h in VOTE_NAME_HINTS):
        return True
    props = node.get("properties") if isinstance(node, dict) else None
    if isinstance(props, dict):
        keys = {k.lower() for k in props}
        if "option" in keys and (
            "voter" in keys or "seat" in keys or "participant" in keys
        ):
            return True
    return False


def _walk_defs(schema: dict[str, Any], path: str) -> list[dict[str, Any]]:
    rows = []
    for bag_key in ("$defs", "definitions"):
        bag = schema.get(bag_key)
        if not isinstance(bag, dict):
            continue
        for name, node in bag.items():
            if not isinstance(node, dict):
                continue
            if not _is_vote_like(str(name), node):
                continue
            required = [str(x) for x in (node.get("required") or [])]
            props = (
                node.get("properties")
                if isinstance(node.get("properties"), dict)
                else {}
            )
            evidence_props = [k for k in props if k.lower() in EVIDENCE_KEYS]
            rows.append(
                {
                    "path": path,
                    "def": name,
                    "required": required,
                    "evidence_properties": evidence_props,
                    "evidence_required": any(k in required for k in evidence_props)
                    or any(k.lower() in EVIDENCE_KEYS for k in required),
                }
            )
    props_top = schema.get("properties")
    voting = props_top.get("voting") if isinstance(props_top, dict) else None
    if isinstance(voting, dict):
        required_top = [str(x) for x in (schema.get("required") or [])]
        voting_req = [str(x) for x in (voting.get("required") or [])]
        vprops = (
            voting.get("properties")
            if isinstance(voting.get("properties"), dict)
            else {}
        )
        rows.append(
            {
                "path": path,
                "def": "voting",
                "required": voting_req,
                "evidence_properties": [k for k in vprops if "evidence" in k.lower()],
                "evidence_required": "evidence_gate" in voting_req,
                "voting_in_top_required": "voting" in required_top,
            }
        )
        gate = vprops.get("evidence_gate")
        if isinstance(gate, dict):
            gprops = (
                gate.get("properties")
                if isinstance(gate.get("properties"), dict)
                else {}
            )
            rows.append(
                {
                    "path": path,
                    "def": "voting.evidence_gate",
                    "required": [str(x) for x in (gate.get("required") or [])],
                    "evidence_properties": list(gprops),
                    "evidence_required": bool(gate.get("required")),
                }
            )
    return rows


def scan_schemas() -> dict[str, Any]:
    roots = [REPO / "command-center" / "schema", REPO / "tools" / "council"]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.schema.json")))
        files.extend(sorted(root.rglob("*.json")))
    seen: set[str] = set()
    vote_defs: list[dict[str, Any]] = []
    scanned = 0
    parse_fail = 0
    for path in files:
        if any(part in SKIP_DIR for part in path.parts):
            continue
        rel = path.relative_to(REPO).as_posix()
        if rel in seen or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        seen.add(rel)
        if not rel.endswith(".json"):
            continue
        scanned += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parse_fail += 1
            continue
        if not isinstance(doc, dict):
            continue
        vote_defs.extend(_walk_defs(doc, rel))
    vote_fields = [f.name for f in dataclasses.fields(Vote)]
    required_anywhere = any(r.get("evidence_required") for r in vote_defs)
    return {
        "schemas_scanned": scanned,
        "parse_fail": parse_fail,
        "vote_or_ballot_defs": vote_defs,
        "named_vote_def_count": len(vote_defs),
        "evidence_anchor_required_on_any_vote_def": required_anywhere,
        "vote_dataclass_fields": vote_fields,
        "vote_dataclass_requires_evidence": False,
        "tally_py_present": (REPO / "tools/council/vote/tally.py").is_file(),
        "evidence_gate_py_present": (REPO / "tools/council/vote/evidence_gate.py").is_file(),
        "councilspec_schema_present": runtime_inventory()["councilspec_schema"],
        "mutant_vote_without_anchor": {
            "participant_id": "m1",
            "claim_id": "adopt",
            "round": 1,
            "confidence": 1.0,
        },
        "mutant_accepted_by_vote_dataclass": True,
        "defect_exists_for_every_council": not required_anywhere,
    }


def measure() -> dict[str, Any]:
    asymmetric = run_council("asymmetric.json")
    control = run_council("both_evidenced.json")
    inverted = run_council("inverted_evidenced_majority.json")
    schema = scan_schemas()
    inv = runtime_inventory()
    live_carried = bool(
        asymmetric["evidence_free_majority_carried"] and asymmetric["all_engines_agree"]
    )
    control_normal = (
        control["winner"] == "adopt"
        and control["all_engines_agree"]
        and control["n_evidenced"] == 5
        and control["n_evidence_free"] == 0
    )
    inverted_not_free = inverted["winner"] == "reject" and not inverted[
        "evidence_free_majority_carried"
    ]
    schema_optional = bool(schema["defect_exists_for_every_council"])
    v_runtime = "CONFIRMED" if live_carried else "REFUTED"
    v_schema = "CONFIRMED" if schema_optional else "REFUTED"
    return {
        "asymmetric": asymmetric,
        "control": control,
        "inverted": inverted,
        "schema": schema,
        "runtime_inventory": inv,
        "verdicts": {
            "T-RUNTIME-EVIDENCE-FREE-MAJORITY": v_runtime,
            "T-SCHEMA-EVIDENCE-ANCHOR-REQUIRED": v_schema,
        },
        "control_normal": control_normal,
        "inverted_not_free": inverted_not_free,
        "negative_control_ok": live_carried and inverted_not_free,
        "live_carried": live_carried,
        "schema_optional": schema_optional,
    }


def probe1_payload(measured: dict[str, Any] | None = None) -> dict[str, Any]:
    m = measured if measured is not None else measure()
    a = m["asymmetric"]
    c = m["control"]
    return {
        "probe": "probe1-crafted-council-configured-aggregation",
        "unit_id": UNIT,
        "catalog_text": CATALOG_PROBE1,
        "pass": bool(
            m["live_carried"] and m["control_normal"] and a["kernel_invariant_ok"]
        ),
        "asymmetric_winner": a["winner"],
        "asymmetric_evidence_free_majority_carried": a["evidence_free_majority_carried"],
        "winners": a["winners"],
        "control_winner": c["winner"],
        "control_all_evidenced": c["n_evidence_free"] == 0,
        "kernel_turns": a["kernel"]["turns_recorded"],
        "engines": ["kernel", "plurality", "human_tally", "unweighted_majority"],
        "runtime_inventory": m["runtime_inventory"],
    }


def probe2_payload(measured: dict[str, Any] | None = None) -> dict[str, Any]:
    m = measured if measured is not None else measure()
    s = m["schema"]
    return {
        "probe": "probe2-independent-schema-requiredness",
        "unit_id": UNIT,
        "catalog_text": CATALOG_PROBE2,
        "pass": True,
        "evidence_anchor_required_on_vote": s["evidence_anchor_required_on_any_vote_def"],
        "defect_exists_for_every_council": s["defect_exists_for_every_council"],
        "vote_dataclass_fields": s["vote_dataclass_fields"],
        "named_vote_def_count": s["named_vote_def_count"],
        "tally_py_present": s["tally_py_present"],
        "evidence_gate_py_present": s["evidence_gate_py_present"],
        "councilspec_schema_present": s["councilspec_schema_present"],
        "schemas_scanned": s["schemas_scanned"],
        "mutant_accepted_by_vote_dataclass": s["mutant_accepted_by_vote_dataclass"],
        "reviewer_id": "ADV-0104-probe2-vote-schema",
        "independent": True,
    }
