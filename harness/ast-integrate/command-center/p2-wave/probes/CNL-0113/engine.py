#!/usr/bin/env python3
"""Jury-family preset engine: typed delta, instantiate, 4-axis distance, fixture resolve.

A preset is a typed delta over a base CouncilSpec (CNL-0101). Distinctness is the
CNL-0102 4-tuple (roles, protocol_schedule, voting, stopping). A renamed clone is
distance 0 and must be merged. Benchmark results need oracles, producer recusal,
and seal-before-admit that evidence adjudication does not have.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WORKING_SCHEMA_PATH = HERE / "council-preset.schema.json"
CATALOG_SCHEMA_PATH = REPO / "command-center" / "schema" / "council-preset.schema.json"
SCHEMA_PATH = WORKING_SCHEMA_PATH

PRESET_KEYS = [
    "id",
    "name",
    "family",
    "catalog_c_ids",
    "base_spec_ref",
    "delta",
    "roles",
    "protocol_schedule",
    "voting",
    "stopping",
    "editable_dials",
    "default_binding",
    "anti_failure",
    "audit",
    "evidence_contract",
    "outcome_types",
    "oracles",
    "recusal",
    "version_policy",
    "metadata",
]
PROFILE_AXES = ("roles", "protocol_schedule", "voting", "stopping")
BASE_SPEC_REF = "councilspec.v2.base@unversioned-on-this-tree"
P14, P15, P17, P18, P50 = "P14", "P15", "P17", "P18", "P50"
SEAL, REMEASURE, CANARY = "seal-protocol-before-result", "independent-remeasure", "gameability-canary"


def _role(rid: str, count: int, votes: bool, obligation: str) -> dict[str, Any]:
    return {"id": rid, "count": count, "votes": votes, "obligation": obligation}


def _step(order: int, protocol_id: str, purpose: str) -> dict[str, Any]:
    return {"order": order, "protocol_id": protocol_id, "purpose": purpose}


def evidence_adjudication_preset() -> dict[str, Any]:
    return {
        "id": "C-J01",
        "name": "evidence-adjudication-jury",
        "family": "jury",
        "catalog_c_ids": ["C-J01"],
        "base_spec_ref": BASE_SPEC_REF,
        "delta": {
            "overlays": [
                "roles",
                "protocol_schedule",
                "voting",
                "stopping",
                "evidence_contract",
                "outcome_types",
            ],
            "must_not_override": ["presenter_cannot_vote", "clerk_cannot_vote"],
        },
        "roles": [
            _role("clerk", 1, False, "Admit or exclude exhibits; never vote on the merits."),
            _role("presenter", 1, False, "Offer exhibits; does not decide."),
            _role("judge", 1, False, "Rule procedure and hung; does not vote on merits."),
            _role("juror", 5, True, "Decide admitted claims; must not have argued the case."),
        ],
        "protocol_schedule": [
            _step(1, P50, "Clerk-led intake and admission of exhibits."),
            _step(2, P15, "Claim-by-claim adjudication against the admitted packet."),
            _step(3, P17, "Jury deliberation with hung permitted."),
        ],
        "voting": {
            "rule": "supermajority-jurors-hung-ok",
            "quorum": 4,
            "who_votes": "juror",
            "oracle_veto": False,
        },
        "stopping": {
            "expression": "hung-or-verdict OR max_rounds",
            "max_rounds": 3,
            "on_timeout": "HUNG",
            "forbid": ["presenter-vote", "clerk-vote"],
        },
        "editable_dials": ["juror.count", "voting.quorum", "stopping.max_rounds"],
        "default_binding": {
            "juror.count": 5,
            "voting.quorum": 4,
            "stopping.max_rounds": 3,
            "standard_of_proof": "preponderance",
        },
        "anti_failure": {"on_split": "surface-hung-not-average", "no_silent_average": True},
        "audit": {"persist_transcript": True, "hash_inputs": True, "seal_protocol": False},
        "evidence_contract": (
            "Admitted documents and testimony are the facts under the stated standard of proof. "
            "A self-reported number may be admitted as an exhibit; this jury has no replication "
            "oracle, so a number from an interested party can move the verdict."
        ),
        "outcome_types": ["CLAIM-UPHELD", "CLAIM-REJECTED", "INSUFFICIENT", "HUNG"],
        "oracles": [],
        "recusal": ["presenter-from-jury", "clerk-from-jury"],
        "version_policy": {
            "on_base_bump": "migrate-or-list-unmigratable",
            "reject_locked_override": True,
        },
        "metadata": {
            "unit_id": "CNL-0113",
            "extends_protocols": [P14, P15, P17, P50],
            "extends_units": ["CNL-0034", "CNL-0040", "CNL-0101"],
        },
    }


def benchmark_results_preset() -> dict[str, Any]:
    return {
        "id": "C-J02",
        "name": "benchmark-results-jury",
        "family": "jury",
        "catalog_c_ids": ["C-J02"],
        "base_spec_ref": BASE_SPEC_REF,
        "delta": {
            "overlays": [
                "roles",
                "protocol_schedule",
                "voting",
                "stopping",
                "oracles",
                "recusal",
                "evidence_contract",
                "outcome_types",
                "audit.seal_protocol",
            ],
            "must_not_override": [
                "producer_recusal",
                "oracle_veto",
                "seal_before_admit",
                "replicator_role",
                "metric_adversary_role",
            ],
        },
        "roles": [
            _role("clerk", 1, False, "Classify the number as CLAIM not FACT; never vote."),
            _role(
                "claim-presenter",
                1,
                False,
                "Present the claimed score; recused from the jury tally.",
            ),
            _role(
                "protocol-registrar",
                1,
                False,
                "Seal metric, splits, hardware class, and seeds BEFORE any result is admitted.",
            ),
            _role(
                "replicator",
                1,
                False,
                "Independent remeasurement under the sealed protocol; oracle, not juror.",
            ),
            _role(
                "metric-adversary",
                1,
                False,
                "Exhibit a cheaper policy that beats the metric without the claimed capability.",
            ),
            _role("judge", 1, False, "Rule procedure; cannot override an oracle veto."),
            _role(
                "juror",
                5,
                True,
                "Decide among remaining outcomes after oracles; must not have produced the number.",
            ),
        ],
        "protocol_schedule": [
            _step(1, SEAL, "Registrar seals metric/splits/hardware/seeds before any score is in evidence."),
            _step(2, P18, "Two-key dual control on the seal so the producer cannot reseal alone."),
            _step(3, P50, "Clerk-led intake: the vendor number is a claim, not a fact."),
            _step(4, REMEASURE, "Replicator re-runs the sealed protocol on a sealed fixture."),
            _step(5, CANARY, "Metric-adversary runs a known-cheap policy / leakage canary."),
            _step(6, P15, "Claim-by-claim on (sealed protocol, replication delta, canary)."),
            _step(7, P17, "Deliberation with hung permitted; CONFIRMED forbidden under veto."),
        ],
        "voting": {
            "rule": "supermajority-jurors-with-oracle-veto",
            "quorum": 4,
            "who_votes": "juror",
            "oracle_veto": "replicator-or-canary",
        },
        "stopping": {
            "expression": "(oracles-resolved AND (hung-or-verdict)) OR max_rounds",
            "max_rounds": 4,
            "on_timeout": "INCONCLUSIVE",
            "forbid": [
                "CONFIRMED-while-replication-pending",
                "CONFIRMED-if-canary-gameable",
                "CONFIRMED-if-protocol-unsealed",
                "producer-as-juror",
            ],
        },
        "editable_dials": [
            "juror.count",
            "voting.quorum",
            "stopping.max_rounds",
            "replication.tolerance",
        ],
        "default_binding": {
            "juror.count": 5,
            "voting.quorum": 4,
            "stopping.max_rounds": 4,
            "replication.tolerance": 1.5,
        },
        "anti_failure": {"on_split": "surface-hung-not-average", "no_silent_average": True},
        "audit": {"persist_transcript": True, "hash_inputs": True, "seal_protocol": True},
        "evidence_contract": (
            "A benchmark result is a number an interested party produced. It is admitted only as "
            "a CLAIM, and only after the protocol is sealed. Independent remeasurement and a "
            "gameability canary are required before CONFIRMED-UNDER-PROTOCOL. Majority opinion "
            "cannot override a failed replication or a passing canary. Producer recusal is structural."
        ),
        "outcome_types": [
            "CONFIRMED-UNDER-PROTOCOL",
            "GAMEABLE",
            "UNREPLICATED",
            "PROTOCOL-VIOLATION",
            "CLAIM-REJECTED",
            "INCONCLUSIVE",
            "HUNG",
        ],
        "oracles": [
            {
                "id": "replicator",
                "vetoes": "CONFIRMED-UNDER-PROTOCOL",
                "obligation": "Must re-run the sealed protocol; pending or mismatch blocks CONFIRMED.",
            },
            {
                "id": "metric-adversary",
                "vetoes": "CONFIRMED-UNDER-PROTOCOL",
                "obligation": "A cheaper policy that beats the metric without the claimed capability yields GAMEABLE.",
            },
        ],
        "recusal": [
            "producer-from-jury",
            "claim-presenter-from-jury",
            "clerk-from-jury",
            "replicator-from-jury",
            "registrar-from-jury",
            "metric-adversary-from-jury",
        ],
        "version_policy": {
            "on_base_bump": "migrate-or-list-unmigratable",
            "reject_locked_override": True,
        },
        "metadata": {
            "unit_id": "CNL-0113",
            "extends_protocols": [P15, P17, P18, P50, SEAL, REMEASURE, CANARY],
            "extends_units": ["CNL-0034", "CNL-0040", "CNL-0101", "CNL-0106"],
        },
    }


def name_only_clone(src: dict[str, Any], new_id: str, new_name: str) -> dict[str, Any]:
    out = copy.deepcopy(src)
    out["id"] = new_id
    out["name"] = new_name
    out["catalog_c_ids"] = [new_id]
    return out


def _thin(
    pid: str,
    name: str,
    family: str,
    roles: list[dict[str, Any]],
    schedule: list[dict[str, Any]],
    voting: dict[str, Any],
    stopping: dict[str, Any],
) -> dict[str, Any]:
    """Sibling stub: enough of the 4-tuple to compute nearest-neighbour, not a full 20-key preset."""
    return {
        "id": pid,
        "name": name,
        "family": family,
        "roles": roles,
        "protocol_schedule": schedule,
        "voting": voting,
        "stopping": stopping,
    }


def sibling_catalog() -> list[dict[str, Any]]:
    """Working sibling set. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this tree.

    P14–P19 are named in catalog CNL-0040. Other family presets are reconstructed from
    CNL-0103–CNL-0116 titles so nearest-neighbour is executable rather than asserted.
    """
    return [
        evidence_adjudication_preset(),
        benchmark_results_preset(),
        _thin(
            "C-R04",
            "code-review-tribunal-executable-oracle",
            "gated-review",
            [
                _role("author", 1, False, "Present the change; does not vote."),
                _role("reviewer", 3, True, "Review against the rubric."),
                _role("test-oracle", 1, False, "Failing executable test overrides reviewer majority."),
                _role("chair", 1, False, "Procedure only."),
            ],
            [
                _step(1, "P45", "Peer review of the patch."),
                _step(2, "executable-oracle", "Run the disputed test suite."),
            ],
            {
                "rule": "majority-reviewers-unless-oracle-fail",
                "quorum": 2,
                "who_votes": "reviewer",
                "oracle_veto": "test-oracle",
            },
            {
                "expression": "oracle-fail OR majority OR max_rounds",
                "max_rounds": 2,
                "on_timeout": "NO-GO",
                "forbid": ["override-failing-test-by-majority"],
            },
        ),
        _thin(
            "C-R02",
            "release-go-no-go-board",
            "gated-review",
            [
                _role("release-manager", 1, True, "Cast go/no-go."),
                _role("qa", 1, True, "Quality vote."),
                _role("sre", 1, True, "Operational vote."),
                _role("product", 1, True, "Scope vote."),
            ],
            [_step(1, "P46", "Architecture/release review board.")],
            {
                "rule": "unanimous-go",
                "quorum": 4,
                "who_votes": "all-seated",
                "oracle_veto": False,
            },
            {
                "expression": "first-no-go OR unanimous-go",
                "max_rounds": 1,
                "on_timeout": "NO-GO",
                "forbid": ["silent-average"],
            },
        ),
        _thin(
            "C-F01",
            "forecasting-proper-scoring",
            "forecasting",
            [
                _role("forecaster", 5, False, "Issue a scored forecast."),
                _role("aggregator", 1, False, "Combine forecasts by the scoring rule."),
                _role("resolution-officer", 1, False, "Resolve against the named source and date."),
            ],
            [
                _step(1, "P33", "Prediction tournament."),
                _step(2, "P36", "Calibration tournament."),
            ],
            {
                "rule": "proper-score-aggregation",
                "quorum": 1,
                "who_votes": "none-scored-not-voted",
                "oracle_veto": False,
            },
            {
                "expression": "resolution-date",
                "max_rounds": 1,
                "on_timeout": "UNRESOLVED",
                "forbid": ["never-resolvable-forecast-as-resolved"],
            },
        ),
        _thin(
            "C-R01",
            "design-critique-board",
            "gated-review",
            [
                _role("author", 1, False, "Present the design."),
                _role("critic", 3, True, "Critique against the rubric."),
                _role("chair", 1, False, "Procedure."),
            ],
            [_step(1, "P46", "Design review board.")],
            {
                "rule": "majority-critics",
                "quorum": 2,
                "who_votes": "critic",
                "oracle_veto": False,
            },
            {
                "expression": "majority OR max_rounds",
                "max_rounds": 2,
                "on_timeout": "REVISE",
                "forbid": [],
            },
        ),
        _thin(
            "council.preset.catalog-class.editable",
            "catalog-class-editable-four-voice",
            "catalog-class",
            [
                _role("Architect", 1, True, "Propose."),
                _role("Skeptic", 1, True, "Attack."),
                _role("Pragmatist", 1, True, "Constrain."),
                _role("Critic", 1, True, "Evaluate."),
            ],
            [_step(1, "four-voice-static", "Static four-voice prompt; not a judicial protocol.")],
            {
                "rule": "unanimous-or-record-dissent",
                "quorum": 4,
                "who_votes": "all-four",
                "oracle_veto": False,
            },
            {
                "expression": "max_rounds",
                "max_rounds": 8,
                "on_timeout": "halt",
                "forbid": [],
            },
        ),
    ]


def locked_dials(preset: dict[str, Any]) -> set[str]:
    return set(preset.get("delta", {}).get("must_not_override") or [])


def apply_binding(preset: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(preset)
    editable = set(out.get("editable_dials") or [])
    locked = locked_dials(out)
    for key, value in binding.items():
        if key in locked or any(key == d or key.startswith(str(d) + ".") for d in locked):
            raise PermissionError(f"locked-dial-override:{key}")
        if key not in editable:
            raise PermissionError(f"non-editable-dial:{key}")
        if key == "juror.count":
            for role in out["roles"]:
                if role["id"] == "juror":
                    role["count"] = int(value)
        elif key == "voting.quorum":
            out["voting"]["quorum"] = int(value)
        elif key == "stopping.max_rounds":
            out["stopping"]["max_rounds"] = int(value)
        else:
            out.setdefault("default_binding", {})[key] = value
    return out


def instantiate(preset: dict[str, Any], task: dict[str, Any] | None = None) -> dict[str, Any]:
    task = task or {}
    extra = task.get("binding") if isinstance(task.get("binding"), dict) else {}
    bound = apply_binding(preset, extra) if extra else copy.deepcopy(preset)
    roster: list[str] = []
    for role in bound["roles"]:
        n = int(role["count"])
        if n == 1:
            roster.append(role["id"])
        else:
            roster.extend(f"{role['id']}-{i}" for i in range(1, n + 1))
    schedule = [s["protocol_id"] for s in sorted(bound["protocol_schedule"], key=lambda x: x["order"])]
    voting = bound["voting"]
    stopping = bound["stopping"]
    return {
        "preset_id": bound["id"],
        "roster": roster,
        "protocol_schedule": schedule,
        "voting_method": (
            f"{voting['rule']}|q={voting['quorum']}|who={voting['who_votes']}|veto={voting['oracle_veto']}"
        ),
        "stopping_expression": (
            f"{stopping['expression']}|max={stopping['max_rounds']}|timeout={stopping['on_timeout']}"
            f"|forbid={','.join(stopping.get('forbid') or [])}"
        ),
        "voting": copy.deepcopy(voting),
        "stopping": copy.deepcopy(stopping),
        "roles": copy.deepcopy(bound["roles"]),
        "oracles": copy.deepcopy(bound.get("oracles") or []),
        "recusal": list(bound.get("recusal") or []),
        "outcome_types": list(bound.get("outcome_types") or []),
        "task_id": task.get("id"),
    }


def profile_of(inst: dict[str, Any]) -> dict[str, Any]:
    return {
        "preset_id": inst["preset_id"],
        "roster": list(inst["roster"]),
        "protocol_schedule": list(inst["protocol_schedule"]),
        "voting_method": inst["voting_method"],
        "stopping_expression": inst["stopping_expression"],
    }


def _role_ids(preset: dict[str, Any]) -> set[str]:
    return {r["id"] for r in preset["roles"]}


def _protocol_ids(preset: dict[str, Any]) -> set[str]:
    return {s["protocol_id"] for s in preset["protocol_schedule"]}


def axis_tuple(preset: dict[str, Any]) -> tuple[Any, ...]:
    """Exact 4-tuple used for name-only clone detection (CNL-0102)."""
    roles = tuple(sorted(f"{r['id']}#{r['count']}#{int(r['votes'])}" for r in preset["roles"]))
    sched = tuple(s["protocol_id"] for s in sorted(preset["protocol_schedule"], key=lambda x: x["order"]))
    vote = json.dumps(preset["voting"], sort_keys=True)
    stop = json.dumps(preset["stopping"], sort_keys=True)
    return (roles, sched, vote, stop)


def differing_axes(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    ta, tb = axis_tuple(a), axis_tuple(b)
    return [name for i, name in enumerate(PROFILE_AXES) if ta[i] != tb[i]]


def distance(a: dict[str, Any], b: dict[str, Any]) -> int:
    """Integer set-symmetric-difference over roles and protocols, plus vote/stop mismatch.

    Hamming-on-exact-tuple scores every non-clone as 4 and cannot name a nearest sibling.
    Shared clerk/juror/P15/P17 between C-J01 and C-J02 must outrank a four-voice prompt.
    A name-only clone still scores 0.
    """
    ra, rb = _role_ids(a), _role_ids(b)
    pa, pb = _protocol_ids(a), _protocol_ids(b)
    role_sym = len(ra ^ rb)
    prot_sym = len(pa ^ pb)
    vote_diff = 0 if a["voting"] == b["voting"] else 1
    stop_diff = 0 if a["stopping"] == b["stopping"] else 1
    return role_sym + prot_sym + vote_diff + stop_diff


def nearest_sibling(subject: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, Any]:
    others = [p for p in catalog if p.get("id") != subject.get("id")]
    if not others:
        raise ValueError("empty-sibling-catalog")
    ranked = sorted(others, key=lambda p: (distance(subject, p), p["id"]))
    sib = ranked[0]
    axes = differing_axes(subject, sib)
    return {
        "subject_id": subject["id"],
        "sibling_id": sib["id"],
        "sibling_name": sib["name"],
        "distance": distance(subject, sib),
        "differing_axes": axes,
        "duplicate_if_name_only": True,
    }


def producer_seated_as_juror(inst: dict[str, Any]) -> bool:
    voting_roles = {r["id"] for r in inst["roles"] if r.get("votes")}
    return bool(voting_roles & {"producer", "claim-presenter", "presenter"})


def resolve(
    preset: dict[str, Any],
    task: dict[str, Any],
    *,
    presenter_packet: dict[str, Any],
    replicator: dict[str, Any] | None = None,
    canary: dict[str, Any] | None = None,
    protocol_sealed: bool = True,
) -> str:
    inst = instantiate(preset, task)
    threshold = float(task.get("claim_threshold", 80.0))
    claimed = presenter_packet.get("claimed_score")
    pid = preset["id"]
    if pid == "C-J01":
        if claimed is None:
            return "INSUFFICIENT"
        return "CLAIM-UPHELD" if float(claimed) >= threshold else "CLAIM-REJECTED"
    if pid == "C-J02":
        if producer_seated_as_juror(inst):
            return "PROTOCOL-VIOLATION"
        if not protocol_sealed or not (preset.get("audit") or {}).get("seal_protocol"):
            return "PROTOCOL-VIOLATION"
        if replicator is None or replicator.get("status") != "REPLICATED":
            return "UNREPLICATED"
        if canary and canary.get("gameable"):
            return "GAMEABLE"
        if claimed is None:
            return "INCONCLUSIVE"
        tol = float((preset.get("default_binding") or {}).get("replication.tolerance", 1.5))
        if abs(float(replicator.get("score", 0)) - float(claimed)) > tol:
            return "UNREPLICATED"
        return "CONFIRMED-UNDER-PROTOCOL"
    raise ValueError(f"no-resolver:{pid}")


def presenter_sensitivity(preset: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    packets = [
        {"claimed_score": 89.2, "label": "high"},
        {"claimed_score": 62.0, "label": "low"},
    ]
    outcomes = [
        {
            "packet": pkt["label"],
            "claimed_score": pkt["claimed_score"],
            "outcome": resolve(
                preset,
                task,
                presenter_packet=pkt,
                replicator=None,
                canary=None,
                protocol_sealed=True,
            ),
        }
        for pkt in packets
    ]
    return {
        "preset_id": preset["id"],
        "outcomes": outcomes,
        "verdict_moved": len({o["outcome"] for o in outcomes}) > 1,
    }


def catalog_schema_status() -> dict[str, Any]:
    """Declared output_schema is a generated shim; it does not own $defs.preset."""
    path = CATALOG_SCHEMA_PATH
    exists = path.is_file()
    doc: dict[str, Any] | None = None
    if exists:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            doc = loaded if isinstance(loaded, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = None
    defs = doc.get("$defs") if isinstance(doc, dict) else None
    has_preset = isinstance(defs, dict) and "preset" in defs
    return {
        "path": "command-center/schema/council-preset.schema.json",
        "exists": exists,
        "has_defs_preset": has_preset,
        "generated_by": (doc or {}).get("x-generated-by"),
        "physical_definition": (doc or {}).get("x-physical-definition"),
        "executable_schema": "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json",
        "rewrote_shared_schema": False,
    }


def load_schema() -> dict[str, Any]:
    catalog = None
    if CATALOG_SCHEMA_PATH.is_file():
        try:
            loaded = json.loads(CATALOG_SCHEMA_PATH.read_text(encoding="utf-8"))
            catalog = loaded if isinstance(loaded, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            catalog = None
    defs = catalog.get("$defs") if isinstance(catalog, dict) else None
    if isinstance(defs, dict) and "preset" in defs:
        return catalog
    return json.loads(WORKING_SCHEMA_PATH.read_text(encoding="utf-8"))


def preset_schema() -> dict[str, Any]:
    doc = load_schema()
    defs = doc.get("$defs")
    if not isinstance(defs, dict) or "preset" not in defs:
        raise ValueError("working-schema-missing-$defs.preset")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": defs,
        **defs["preset"],
    }


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(preset_schema())
    errors: list[str] = []
    for rec in records:
        for err in validator.iter_errors(rec):
            errors.append(f"{rec.get('id')}:{err.message}")
    return errors


def validate_envelope(doc: dict[str, Any]) -> list[str]:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(load_schema())
    return [e.message for e in validator.iter_errors(doc)]


def invalid_record() -> dict[str, Any]:
    return {"id": "C-J99", "name": "benchmark-results-jury"}


def fixture_task() -> dict[str, Any]:
    return {
        "id": "task.vendor-mmlu-claim",
        "title": "Vendor claims MMLU 89.2% on model X; admit or confirm?",
        "claim_threshold": 80.0,
        "claimant": "vendor",
        "metric": "MMLU",
        "interested_party": True,
        "binding": {},
    }


def assert_preset_keys(preset: dict[str, Any]) -> None:
    missing = [k for k in PRESET_KEYS if k not in preset]
    extra = [k for k in preset if k not in PRESET_KEYS]
    if missing or extra:
        raise ValueError(f"preset-keys missing={missing} extra={extra}")
