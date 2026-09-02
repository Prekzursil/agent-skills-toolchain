#!/usr/bin/env python3
"""Gated review-board family: typed deltas, instantiation, split, sibling distance.

The family is parameterised by three dials the catalog question names:
  * rubric_source
  * evidence_contract
  * fail_override.who
plus fail_kind (finding vs gate). A go-no-go board is a different mechanism
from a design/plan critique board only when all four differ. A rename is a
mechanism-duplicate and must be merged.

Family members validate against the unit-local
command-center/p2-wave/probes/CNL-0104/preset.record.schema.json ($defs.preset).
The catalog output_schema path is a generated $ref shim into the receipt
envelope (report.kind=council-preset) and does not define $defs.preset.
This unit does not rewrite that shared file.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/council-preset.schema.json"
PRESET_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0104/preset.record.schema.json"
)
CATALOG_FIXTURE = HERE / "catalog_fixture.json"
TASK_FIXTURE = HERE / "fixture_task.json"
PRESET_SCHEMA_PATH = HERE / "preset.record.schema.json"
OUT_REL = (
    "command-center/design/council/"
    "CNL-0104-gated-review-board-family-design-plan-critique-and-release.md"
)
SENTINEL = "SUCCESS:CNL-0104"
FAMILY = "gated-review-board"
BASE_SPEC_REF = "councilspec.v2.gated-review-base@2.0.0-cnl0104"

# The 20 keys required by the unit-local $defs.preset on this tree.
PRESET_KEYS_20 = [
    ("id", "metadata"),
    ("name", "metadata"),
    ("family", "metadata"),
    ("catalog_c_ids", "metadata"),
    ("base_spec_ref", "base"),
    ("delta", "delta"),
    ("roles", "delta"),
    ("protocol_schedule", "delta"),
    ("voting", "delta"),
    ("stopping", "delta"),
    ("editable_dials", "metadata"),
    ("default_binding", "delta"),
    ("anti_failure", "delta"),
    ("audit", "delta"),
    ("evidence_contract", "delta"),
    ("outcome_types", "delta"),
    ("oracles", "delta"),
    ("recusal", "delta"),
    ("version_policy", "metadata"),
    ("metadata", "metadata"),
]

CRITIQUE_VEC = (
    "task-authored",
    "argument-admissible",
    "none-without-new-evidence",
    "finding",
)
GONOGO_VEC = (
    "frozen-predicate",
    "command-reproducible",
    "owner-two-key",
    "gate",
)
VEC_KEYS = (
    "rubric_source",
    "evidence_kind",
    "fail_override_who",
    "fail_kind",
)

SUPERSEDES = {
    "council.preset.gated-review.design-plan-critique": [
        {
            "id": "C-architecture-review-board",
            "relation": "extends",
            "confirmed_from_library_file": False,
            "basis": (
                "Catalog-cited protocol P46 architecture-review-board "
                "(CNL-0045 ENGINEERING-REVIEW member list). C-id string is "
                "reconstructed; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent."
            ),
        }
    ],
    "council.preset.gated-review.release-go-no-go": [
        {
            "id": "C-architecture-review-board",
            "relation": "extends",
            "confirmed_from_library_file": False,
            "basis": (
                "Same P46 sibling as the critique member, plus a command oracle "
                "P46 does not have. That oracle is what makes this a different "
                "mechanism rather than a renamed critique board."
            ),
        }
    ],
}


def _role(rid: str, votes: bool, obligation: str, count: int = 1) -> dict[str, Any]:
    return {"id": rid, "count": count, "votes": votes, "obligation": obligation}


def _step(order: int, protocol_id: str, purpose: str) -> dict[str, Any]:
    return {"order": order, "protocol_id": protocol_id, "purpose": purpose}


def _version_policy() -> dict[str, Any]:
    return {
        "on_base_bump": "migrate-or-list-unmigratable",
        "reject_locked_override": True,
    }


def _anti() -> dict[str, Any]:
    return {"on_split": "surface-split-not-average", "no_silent_average": True}


CRITIQUE: dict[str, Any] = {
    "id": "council.preset.gated-review.design-plan-critique",
    "name": "design-plan-critique",
    "family": FAMILY,
    "catalog_c_ids": ["C-architecture-review-board"],
    "base_spec_ref": BASE_SPEC_REF,
    "delta": {
        "overlays": [
            "roles",
            "protocol_schedule",
            "voting",
            "stopping",
            "evidence_contract",
            "outcome_types",
            "default_binding.rubric_source",
            "default_binding.fail_kind",
        ],
        "must_not_override": [
            "family_vector",
            "voting.rule",
            "fail_kind",
            "author_nonvoting",
        ],
    },
    "roles": [
        _role("GateChair", True, "Seat the board and bind the task-authored rubric."),
        _role("Architect", True, "Argue the design against the rubric cells."),
        _role("Skeptic", True, "Falsify findings; drop unfalsifiable concerns."),
        _role("EvidenceClerk", True, "Admit or reject each finding's evidence packet."),
        _role("Author", False, "Consume one revision round; does not vote the verdict."),
    ],
    "protocol_schedule": [
        _step(1, "P46", "Seat the board and bind the task-authored rubric."),
        _step(2, "P50", "Admit or reject each finding's evidence packet."),
        _step(3, "P49", "Drop unfalsifiable findings via interrogation."),
    ],
    "voting": {
        "rule": "fail-sticky-majority",
        "quorum": 3,
        "who_votes": "seated-voting-roles",
        "oracle_veto": False,
    },
    "stopping": {
        "expression": (
            "ALL(cells_adjudicated) AND "
            "(fail_count==0 OR revision_budget==0 OR round>=max_rounds)"
        ),
        "max_rounds": 4,
        "on_timeout": "emit-findings-FAIL-open",
        "forbid": ["unfalsifiable-concern", "chair-feelings-as-evidence"],
    },
    "editable_dials": ["stopping.max_rounds", "default_binding.revision_rounds"],
    "default_binding": {
        "rubric_source": CRITIQUE_VEC[0],
        "evidence_kind": CRITIQUE_VEC[1],
        "fail_override_who": CRITIQUE_VEC[2],
        "fail_kind": CRITIQUE_VEC[3],
        "revision_rounds": 1,
        "max_rounds": 4,
    },
    "anti_failure": _anti(),
    "audit": {"persist_transcript": True, "hash_inputs": True, "seal_protocol": False},
    "evidence_contract": (
        "Findings rest on argument-admissible evidence: counterexample, fixture, "
        "or reasoned dissent with a locus. Unfalsifiable concern is inadmissible. "
        "FAIL is a finding, not a ship gate; nobody seated may convert FAIL to "
        "PASS without new admissible evidence."
    ),
    "outcome_types": ["FINDINGS-PASS", "FINDINGS-FAIL", "FINDINGS-CONDITIONAL"],
    "oracles": [],
    "recusal": ["author-from-verdict-tally"],
    "version_policy": _version_policy(),
    "metadata": {
        "unit_id": "CNL-0104",
        "extends_protocols": ["P46", "P50", "P49"],
        "extends_units": ["CNL-0101", "CNL-0045", "CNL-0060"],
    },
}


GONOGO: dict[str, Any] = {
    "id": "council.preset.gated-review.release-go-no-go",
    "name": "release-go-no-go",
    "family": FAMILY,
    "catalog_c_ids": ["C-architecture-review-board"],
    "base_spec_ref": BASE_SPEC_REF,
    "delta": {
        "overlays": [
            "roles",
            "protocol_schedule",
            "voting",
            "stopping",
            "oracles",
            "evidence_contract",
            "outcome_types",
            "audit.seal_protocol",
            "default_binding.rubric_source",
            "default_binding.fail_kind",
        ],
        "must_not_override": [
            "family_vector",
            "voting.rule",
            "oracle_veto",
            "fail_kind",
            "owner_two_key",
        ],
    },
    "roles": [
        _role("GateChair", True, "Seat the board against the frozen completion predicate."),
        _role("ProbeOperator", True, "Re-run named probes; vote on command-reproducible cells."),
        _role("EvidenceClerk", True, "Admit only named-probe exits, hashes, and verbatim output."),
        _role("OwnerKeyA", False, "Silent until two-key override; may not vote as operator."),
        _role("OwnerKeyB", False, "Silent until two-key override; may not vote as operator."),
    ],
    "protocol_schedule": [
        _step(1, "P46", "Seat the board against the frozen named predicate."),
        _step(2, "P16", "Every cell must meet the command-reproducible evidence bar."),
        _step(3, "P18", "Fires only if FAIL and an owner two-key override is requested."),
    ],
    "voting": {
        "rule": "fail-closed-unanimity-of-operators",
        "quorum": 2,
        "who_votes": "operator-and-clerk",
        "oracle_veto": "named-probe-nonzero-exit",
    },
    "stopping": {
        "expression": (
            "ALL(named_probes_rerun) AND "
            "(fail_count==0 OR override_two_key_complete OR round>=max_rounds)"
        ),
        "max_rounds": 2,
        "on_timeout": "NO-GO",
        "forbid": ["argument-without-command", "panel-majority-opinion"],
    },
    "editable_dials": ["stopping.max_rounds"],
    "default_binding": {
        "rubric_source": GONOGO_VEC[0],
        "evidence_kind": GONOGO_VEC[1],
        "fail_override_who": GONOGO_VEC[2],
        "fail_kind": GONOGO_VEC[3],
        "revision_rounds": 0,
        "max_rounds": 2,
        "predicate_name": "G-1-contract-green",
    },
    "anti_failure": _anti(),
    "audit": {"persist_transcript": True, "hash_inputs": True, "seal_protocol": True},
    "evidence_contract": (
        "GO/NO-GO rests on command-reproducible evidence: named-probe exit code, "
        "artifact sha256, and verbatim command output. Opinion without a command "
        "is inadmissible. FAIL is a gate. Only owner two-key dual control (P18) "
        "with recorded dissent may convert the outcome to CONDITIONAL-GO."
    ),
    "outcome_types": ["SHIP-GO", "SHIP-NOGO", "CONDITIONAL-GO"],
    "oracles": [
        {
            "id": "named-probe",
            "vetoes": "SHIP-GO",
            "obligation": "Nonzero named-probe exit forbids SHIP-GO; FAIL stays a gate.",
        }
    ],
    "recusal": ["owner-keys-from-operator-vote"],
    "version_policy": _version_policy(),
    "metadata": {
        "unit_id": "CNL-0104",
        "extends_protocols": ["P46", "P16", "P18"],
        "extends_units": ["CNL-0101", "CNL-0045", "CNL-0060"],
    },
}


SPLIT_RULE = (
    "A go-no-go board stops being the same mechanism as a design/plan critique "
    "board when and only when all four of these differ: (1) rubric_source "
    "frozen-predicate vs task-authored, (2) evidence_contract command-reproducible "
    "vs argument-admissible, (3) fail_override.who owner-two-key vs "
    "none-without-new-evidence, (4) fail_kind gate vs finding. If any of the "
    "four still matches, the records are mechanism-duplicates and must be merged."
)


def family_presets() -> list[dict[str, Any]]:
    return [copy.deepcopy(CRITIQUE), copy.deepcopy(GONOGO)]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema() -> dict:
    return load_json(REPO / SCHEMA_REL)


def load_catalog() -> list[dict[str, Any]]:
    doc = load_json(CATALOG_FIXTURE)
    rows = doc.get("presets") or []
    return [r for r in rows if isinstance(r, dict)]


def load_task() -> dict[str, Any]:
    return load_json(TASK_FIXTURE)


def _delta(preset: dict) -> dict:
    d = preset.get("delta")
    return d if isinstance(d, dict) else {}


def _binding(preset: dict) -> dict:
    b = preset.get("default_binding")
    return b if isinstance(b, dict) else {}


def _roles_block(preset: dict) -> list:
    roles = preset.get("roles")
    if isinstance(roles, list) and roles:
        return roles
    return _delta(preset).get("roles") or []


def _sched_block(preset: dict) -> list:
    sched = preset.get("protocol_schedule")
    if isinstance(sched, list) and sched:
        return sched
    return _delta(preset).get("protocol_schedule") or []


def _voting_block(preset: dict) -> dict:
    v = preset.get("voting")
    if isinstance(v, dict) and v:
        return v
    v = _delta(preset).get("voting")
    return v if isinstance(v, dict) else {}


def _stopping_block(preset: dict) -> dict:
    s = preset.get("stopping")
    if isinstance(s, dict) and s:
        return s
    s = _delta(preset).get("stopping")
    return s if isinstance(s, dict) else {}


def family_vector(preset: dict) -> tuple:
    d = _delta(preset)
    bind = _binding(preset)
    rub = d.get("rubric") if isinstance(d.get("rubric"), dict) else {}
    ev = d.get("evidence") if isinstance(d.get("evidence"), dict) else {}
    ov = d.get("fail_override") if isinstance(d.get("fail_override"), dict) else {}
    return (
        bind.get("rubric_source") or rub.get("source"),
        bind.get("evidence_kind") or ev.get("contract"),
        bind.get("fail_override_who") or ov.get("who"),
        bind.get("fail_kind") or ov.get("fail_kind"),
    )


def mechanism_tuple(preset: dict) -> tuple:
    roles = tuple(sorted(str(r.get("id")) for r in _roles_block(preset) if isinstance(r, dict)))
    protocols = tuple(
        str(s.get("protocol_id") or s.get("protocol_id"))
        for s in sorted(
            _sched_block(preset),
            key=lambda x: int(x.get("order") or 0) if isinstance(x, dict) else 0,
        )
        if isinstance(s, dict)
    )
    vot = _voting_block(preset)
    stp = _stopping_block(preset)
    voting = (vot.get("rule"), vot.get("quorum"))
    stopping = (stp.get("expression"), stp.get("max_rounds"))
    return (roles, protocols, voting, stopping, family_vector(preset))


def axis_distance(a: tuple, b: tuple) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def classify_mechanism(preset: dict) -> str:
    vec = family_vector(preset)
    if vec == CRITIQUE_VEC:
        return "design-plan-critique"
    if vec == GONOGO_VEC:
        return "release-go-no-go"
    if any(v is None for v in vec):
        return "pre-family-review-board"
    return "ILLEGAL-MIXED"


def split_holds(critique: dict, gng: dict) -> bool:
    """True iff the four family-vector axes all differ (the split criterion)."""
    return axis_distance(family_vector(critique), family_vector(gng)) == 4


def _set_path(root: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cur: Any = root
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            raise KeyError(dotted)
        cur = cur[p]
    if not isinstance(cur, dict):
        raise KeyError(dotted)
    cur[parts[-1]] = value


def apply_dials(preset: dict, dials: dict[str, Any] | None) -> dict[str, Any]:
    """Return {ok, preset, rejected, reason}."""
    out = copy.deepcopy(preset)
    rejected: list[str] = []
    allowed = set(out.get("editable_dials") or [])
    for key, val in (dials or {}).items():
        if key not in allowed:
            rejected.append(key)
            continue
        _set_path(out, key, val)
    if rejected:
        return {
            "ok": False,
            "preset": out,
            "rejected": rejected,
            "reason": (
                "silent override of non-editable dial(s) "
                + ",".join(rejected)
                + " — instantiator REJECTS"
            ),
        }
    return {"ok": True, "preset": out, "rejected": [], "reason": ""}


def instantiate(preset: dict, task: dict, dials: dict[str, Any] | None = None) -> dict[str, Any]:
    applied = apply_dials(preset, dials if dials is not None else task.get("requested_dials"))
    if not applied["ok"]:
        return {
            "ok": False,
            "preset_id": preset.get("id"),
            "task_id": task.get("id"),
            "rejected": applied["rejected"],
            "reason": applied["reason"],
            "roster": [],
            "protocol_schedule": [],
            "voting": {},
            "stopping": {},
        }
    live = applied["preset"]
    cls = classify_mechanism(live)
    if live.get("family") == FAMILY and cls == "ILLEGAL-MIXED":
        return {
            "ok": False,
            "preset_id": live.get("id"),
            "task_id": task.get("id"),
            "reason": "ILLEGAL-MIXED family vector — mechanism-duplicate or underspecified",
            "roster": [],
            "protocol_schedule": [],
            "voting": {},
            "stopping": {},
        }
    roster = []
    override_roles = {"OwnerKeyA", "OwnerKeyB"}
    for r in _roles_block(live):
        if not isinstance(r, dict):
            continue
        if "vote_weight" in r:
            weight = r.get("vote_weight")
        else:
            weight = 1.0 if r.get("votes") else 0.0
        rid = r.get("id")
        roster.append(
            {
                "role": rid,
                "vote_weight": weight,
                "seated": r.get("seated", True),
                "may_override_fail": bool(r.get("may_override_fail")) or rid in override_roles,
                "weight_provenance": r.get("weight_provenance")
                or (None if weight == 1.0 else f"non-unit-weight:{rid}"),
            }
        )
    schedule = []
    for s in _sched_block(live):
        if not isinstance(s, dict):
            continue
        pid = s.get("protocol_id") or s.get("protocol_id")
        schedule.append(
            {
                "order": s.get("order"),
                "protocol_id": pid,
                "purpose": s.get("purpose"),
                "name": s.get("name"),
            }
        )
    voting = copy.deepcopy(_voting_block(live))
    stopping = copy.deepcopy(_stopping_block(live))
    vec = family_vector(live)
    return {
        "ok": True,
        "preset_id": live.get("id"),
        "task_id": task.get("id"),
        "mechanism_class": cls,
        "roster": roster,
        "protocol_schedule": schedule,
        "voting": voting,
        "stopping": stopping,
        "family_vector": {
            "rubric_source": vec[0],
            "evidence_contract": vec[1],
            "fail_override_who": vec[2],
            "fail_kind": vec[3],
        },
        "default_binding": copy.deepcopy(_binding(live)),
        "mechanism_tuple": _tuple_to_json(mechanism_tuple(live)),
    }


def _tuple_to_json(t: tuple) -> list:
    out: list[Any] = []
    for item in t:
        if isinstance(item, tuple):
            out.append(_tuple_to_json(item))
        else:
            out.append(item)
    return out


def nearest_sibling(preset: dict, catalog: list[dict]) -> dict[str, Any]:
    mine = mechanism_tuple(preset)
    best: dict[str, Any] | None = None
    ranked: list[dict[str, Any]] = []
    for sib in catalog:
        if sib.get("id") == preset.get("id"):
            continue
        dist = axis_distance(mine, mechanism_tuple(sib))
        rec = {
            "id": sib.get("id"),
            "name": sib.get("name"),
            "distance": dist,
            "mechanism_class": classify_mechanism(sib),
        }
        ranked.append(rec)
        if best is None or dist < int(best["distance"]) or (
            dist == int(best["distance"]) and str(rec["id"]) < str(best["id"])
        ):
            best = rec
    ranked.sort(key=lambda r: (int(r["distance"]), str(r["id"])))
    differ = _axes_that_differ(mine, mechanism_tuple(_by_id(catalog, best["id"]) if best else {}))
    return {
        "named": None if best is None else best["id"],
        "distance": None if best is None else best["distance"],
        "axes_that_differ": differ,
        "ranked": ranked,
        "same_mechanism": bool(best and best["distance"] == 0),
    }


def _by_id(rows: list[dict], pid: str | None) -> dict:
    for r in rows:
        if r.get("id") == pid:
            return r
    return {}


def _axes_that_differ(a: tuple, b: tuple) -> list[str]:
    names = ["roles", "protocols", "voting", "stopping", "family_vector"]
    out: list[str] = []
    for i, name in enumerate(names):
        if i >= len(a) or i >= len(b) or a[i] != b[i]:
            out.append(name)
    return out


def name_only_clone(preset: dict, new_id: str, new_name: str) -> dict:
    clone = copy.deepcopy(preset)
    clone["id"] = new_id
    clone["name"] = new_name
    return clone


def mixed_gonogo_wearing_critique_evidence(gng: dict) -> dict:
    """Negative control: go-no-go name, critique family vector."""
    bad = copy.deepcopy(gng)
    bad["id"] = "NEG.gated-review.go-no-go-name-only"
    bad["name"] = "release-go-no-go-in-name-only"
    src = _binding(CRITIQUE)
    dst = bad.setdefault("default_binding", {})
    if not isinstance(dst, dict):
        bad["default_binding"] = {}
        dst = bad["default_binding"]
    for k in VEC_KEYS:
        dst[k] = src.get(k)
    bad["evidence_contract"] = CRITIQUE["evidence_contract"]
    # Keep old nested copies if a caller still has them.
    if isinstance(bad.get("delta"), dict) and isinstance(CRITIQUE.get("delta"), dict):
        for nested in ("evidence", "rubric", "fail_override"):
            if nested in CRITIQUE["delta"]:
                bad["delta"][nested] = copy.deepcopy(CRITIQUE["delta"][nested])
    return bad


def artifact_body(doc: dict) -> dict:
    """Family payload lives in report when the catalog file is a receipt envelope."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("presets") or report.get("kind") == "council-preset"
    ):
        return report
    return doc


def preset_schema(schema: dict | None = None) -> dict:
    """Validate affected family members against the unit-local $defs.preset.

    The catalog-declared council-preset.schema.json is a generated shim with no
    $defs.preset (receipt envelope, report.kind=council-preset). Passing that
    shim here is a mechanism-duplicate of the strike-1 failure (17 envelope
    errors on a preset record). Local file only.
    """
    sch = schema if schema is not None else load_json(PRESET_SCHEMA_PATH)
    if not (isinstance(sch, dict) and "preset" in (sch.get("$defs") or {})):
        sch = load_json(PRESET_SCHEMA_PATH)
    defs = sch["$defs"]
    return {
        "$schema": sch.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "$defs": defs,
        **defs["preset"],
    }


def schema_error_count(record: dict, schema: dict | None = None) -> int:
    import jsonschema

    sch = preset_schema(schema)
    validator = jsonschema.Draft202012Validator(sch)
    return sum(1 for _ in validator.iter_errors(record))


def schema_error_messages(record: dict, schema: dict | None = None) -> list[str]:
    import jsonschema

    sch = preset_schema(schema)
    validator = jsonschema.Draft202012Validator(sch)
    out: list[str] = []
    for err in validator.iter_errors(record):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def envelope_schema() -> dict:
    """Physical council-preset class: generic_report plus report.kind pin.

    Compiled without schema_resolver.validator_for (jsonschema 4.10.3 has no
    registry= kwarg; that API is 4.18+). $defs are copied from the on-disk
    receipt schema so #/$defs/receipt_core resolves locally.
    """
    receipt = load_json(REPO / "platform" / "schema" / "receipt.schema.json")
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise RuntimeError("receipt.schema.json missing $defs.generic_report")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.local/cnl-0104/council-preset-envelope.schema.json",
        "$defs": defs,
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {
                            "kind": {"const": "council-preset"},
                        },
                    },
                },
            },
        ],
    }


def envelope_errors(record: dict) -> list[str]:
    """Validate a catalog output document against the council-preset envelope."""
    import jsonschema

    validator = jsonschema.Draft202012Validator(envelope_schema())
    out: list[str] = []
    for err in validator.iter_errors(record):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def envelope_error_count(record: dict) -> int:
    return len(envelope_errors(record))


def invalid_record() -> dict:
    return {"id": 0, "name": "", "delta": {}}


def intra_family_distance() -> int:
    return axis_distance(mechanism_tuple(CRITIQUE), mechanism_tuple(GONOGO))
