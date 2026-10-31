"""``workflow-forge`` - the executable fuse-benchmark-certify half of the Foundry.

Spec :11025 (forge must "benchmark them, synthesize the strongest result, and return both the
executable workflow and an evidence-backed design rationale") and :11282 (the acceptance bar).

What makes this a GATE rather than a fusion machine
---------------------------------------------------
``forge fuse`` can return **REJECTED**. A forge that always emits a fused workflow is a no-op
gate: it would certify "bigger" as "better", which is the exact failure the spec names. The
``union`` strategy exists partly to demonstrate this - it appends every donor stage whether or
not the donor contributes a mechanism, so a union of two similar sources grows the stage count,
improves no axis, and is REJECTED with ``reason="no-axis-improved"``.

Lineage and decomposition are structural, not prose
---------------------------------------------------
Every grafted stage, role, gate, param and artifact path is recorded in
``x_extensions.foundry.decomposition`` with the source it came from and its ORIGINAL id. That
makes ``forge decompose`` an exact inverse: it reconstructs each source's donated sub-topology
and, when the original source files are supplied, checks the reconstruction against them with
``workflows.mechanisms.topology`` - the same round-trip primitive the vendor-neutral emission
blueprint uses. A decomposition claim that cannot be checked against the real sources is
reported as NOT-CHECKED, never as passing.

CLI
---
    python platform/lib/foundry/forge.py strategies
    python platform/lib/foundry/forge.py fuse --source A.json --source B.json \
        --strategy best-of-breed --out platform/workflows/fused.json
    python platform/lib/foundry/forge.py decompose --workflow fused.json \
        --source A.json --source B.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in (None, ""):  # allow `python platform/lib/foundry/forge.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry import bench, mechanisms  # noqa: E402
from foundry.model import (  # noqa: E402
    FUSION_STRATEGIES,
    Goal,
    SPEC_ANCHOR_ACCEPTANCE,
    SPEC_ANCHOR_FOUNDRY_PIPELINE,
)
from workflows.mechanisms import topology  # noqa: E402

_SLUG = re.compile(r"^[a-z0-9]+(?:[-._][a-z0-9]+)*$")
_DONOR_PREFIX = re.compile(r"^d(\d+)\.")

#: top-level policy blocks that can be taken best-of-breed, each with the predicate keys that
#: decide which source's version is stronger. Scoring a block by its OWN fields (rather than by
#: the whole-workflow axes) is what makes the choice attributable.
_POLICY_BLOCKS: dict[str, tuple[str, ...]] = {
    "retry_policy": ("strategy", "max_attempts", "retry_on", "pivot"),
    "failure_policy": (
        "on_failure",
        "terminal_state_required",
        "never_silent",
        "preserve_partial_artifact",
        "classify_as",
        "quarantine_path",
    ),
    "resume": (
        "enabled",
        "checkpoint_store",
        "idempotency_key_from",
        "granularity",
        "stale_checkpoint_seconds",
        "on_stale",
    ),
    "replay": (
        "deterministic",
        "seed",
        "journal_path",
        "record",
        "forbid_nondeterministic_sources",
    ),
    "cache": ("enabled", "key_from", "store", "verify_integrity", "invalidate_on"),
    "dry_run": ("supported", "emits", "plan_artifact", "side_effect_free"),
    "estimate": (
        "basis",
        "confidence",
        "cost",
        "wallclock_seconds",
        "tokens",
        "impact",
    ),
    "portability": ("export", "import"),
    "model_routing": ("default", "overrides", "diversity", "fallback"),
    "tool_policy": (
        "default",
        "allow",
        "deny",
        "network",
        "source_policy",
        "require_owner_approval",
        "forbid_write_paths",
    ),
}


def _block_strength(block: Any, keys: Sequence[str]) -> int:
    if not isinstance(block, Mapping):
        return -1
    return sum(1 for k in keys if block.get(k) not in (None, "", [], {}, False))


#: `id` is capped at 80 chars by $defs/slug in platform/schema/workflow-dsl.schema.json.
_SLUG_MAX = 80
#: how many hex chars of the payload digest ride in the id.
_ID_DIGEST_CHARS = 12
#: id prefix for a fusion the certifier REJECTED. A rejected document keeps its evidentiary
#: value (forge must be able to refuse) but must never be loadable under a certified id.
_REJECTED_ID_PREFIX = "rejected"


def _slugify(text: str) -> str:
    out = re.sub(r"[^a-z0-9._-]+", "-", text.lower())
    return re.sub(r"[-._]{2,}", ".", out).strip("-._")


def fusion_payload_digest(doc: Mapping[str, Any]) -> str:
    """sha256 over the behaviour-bearing content of a fused document.

    Excluded, and only these two:

    * ``id`` - it is the value being derived, so including it would be circular.
    * ``x_extensions.foundry.certification`` - written by :func:`fuse_and_certify`
      *after* the id is assigned.

    Excluding exactly those two is what makes the id **recomputable from a finished
    document on disk**, so :func:`expected_fused_id` can verify any forged artifact
    rather than taking its stamped id on trust.
    """
    payload = copy.deepcopy(dict(doc))
    payload.pop("id", None)
    ext = payload.get("x_extensions")
    if isinstance(ext, Mapping):
        foundry = ext.get("foundry")
        if isinstance(foundry, Mapping) and "certification" in foundry:
            payload["x_extensions"] = {
                **ext,
                "foundry": {k: v for k, v in foundry.items() if k != "certification"},
            }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fused_id(
    a: str, b: str, strategy: str, payload_digest: str, *, rejected: bool = False
) -> str:
    """Derive a fused workflow id that cannot collide across strategy or verdict.

    Three inputs beyond the source pair, each closing a measured D4 collision:

    * ``strategy`` - a ``union`` fusion and a ``best-of-breed`` fusion of the SAME pair
      are different documents and must not share an id.
    * ``payload_digest`` - a re-run whose content differs gets a different id; a re-run
      whose content is identical deliberately keeps the same id (``fuse`` is pure, so
      same-content/same-id is the correct content-addressed outcome).
    * ``rejected`` - a REJECTED document is namespaced under ``rejected.``, so a loader
      keyed on id can never resolve a rejected fusion where a certified one is meant.
    """
    head = _REJECTED_ID_PREFIX + ".fused" if rejected else "fused"
    short = payload_digest[:_ID_DIGEST_CHARS]
    body = _slugify(f"{a}.{b}.{strategy}")
    candidate = _slugify(f"{head}.{body}.{short}")
    if len(candidate) <= _SLUG_MAX and _SLUG.match(candidate):
        return candidate
    # Too long for the slug cap: keep the head and the digest (the parts that carry the
    # uniqueness guarantee) and trim the readable middle. `strategy` is folded into the
    # digest by the caller, so trimming it out of the readable text cannot reintroduce a
    # cross-strategy collision.
    room = _SLUG_MAX - len(head) - len(short) - 2
    trimmed = _slugify(body[:room]) if room > 1 else ""
    candidate = _slugify(f"{head}.{trimmed}.{short}" if trimmed else f"{head}.{short}")
    if len(candidate) <= _SLUG_MAX and _SLUG.match(candidate):
        return candidate
    return f"{head}.{short}"


def expected_fused_id(doc: Mapping[str, Any]) -> str | None:
    """Recompute the id a forged document SHOULD carry, straight from the document.

    Returns ``None`` for a document that forge did not produce (no foundry decomposition),
    which the caller must treat as "not checkable here", never as a pass.
    """
    foundry = (doc.get("x_extensions") or {}).get("foundry")
    if not isinstance(foundry, Mapping):
        return None
    decomposition = foundry.get("decomposition")
    if not isinstance(decomposition, Mapping):
        return None
    base = decomposition.get("base") or {}
    donor = decomposition.get("donor") or {}
    if not isinstance(base, Mapping) or not isinstance(donor, Mapping):
        return None
    verdict = (foundry.get("certification") or {}).get("verdict")
    return _fused_id(
        str(base.get("id")),
        str(donor.get("id")),
        str(decomposition.get("strategy")),
        fusion_payload_digest(doc),
        rejected=verdict == "REJECTED",
    )


# --------------------------------------------------------------------- id rewriting

#: every place a DSL stage names another stage id. Missing one of these produces a fused
#: document that passes JSON Schema and then fails DSL-SEM-002/003/009 - so the list is
#: exhaustive against the schema's stage definitions rather than "the ones we happened to hit".
_STAGE_ID_REFS: tuple[tuple[str, ...], ...] = (
    ("depends_on",),
    ("joins",),
    ("barrier", "require_stages"),
    ("target",),
)


def _rewrite_stage(
    stage: Mapping[str, Any],
    prefix: str,
    donated_ids: set[str],
    graft_point: str,
    role_map: Mapping[str, str],
    gate_map: Mapping[str, str],
    subwf_map: Mapping[str, str],
    path_map: Mapping[str, str],
    rewires: list[dict[str, str]],
) -> dict[str, Any]:
    """Deep-copy one donated stage with every namespace reference rewired.

    A reference to a source stage that was NOT donated is rewired to ``graft_point`` and the
    rewire is RECORDED. Silently dropping such an edge would turn a real ordering constraint
    into a race; silently keeping it would dangle and fail DSL-SEM-002.
    """
    st = copy.deepcopy(dict(stage))
    original_id = str(st.get("id"))
    st["id"] = f"{prefix}{original_id}"

    def remap_ids(values: Any) -> list[str]:
        out: list[str] = []
        for v in values or []:
            sv = str(v)
            if sv in donated_ids:
                out.append(f"{prefix}{sv}")
            else:
                out.append(graft_point)
                rewires.append(
                    {
                        "stage": st["id"],
                        "dropped_reference": sv,
                        "rewired_to": graft_point,
                        "reason": "referenced a source stage that was not donated",
                    }
                )
        seen: set[str] = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    for ref in _STAGE_ID_REFS:
        if len(ref) == 1:
            if ref[0] in st:
                st[ref[0]] = remap_ids(st[ref[0]])
        else:
            outer, inner = ref
            if isinstance(st.get(outer), Mapping) and inner in st[outer]:
                st[outer] = dict(st[outer])
                st[outer][inner] = remap_ids(st[outer][inner])

    if "role" in st:
        st["role"] = role_map.get(str(st["role"]), str(st["role"]))
    if "gate_ref" in st:
        st["gate_ref"] = gate_map.get(str(st["gate_ref"]), str(st["gate_ref"]))
    wf = st.get("workflow")
    if isinstance(wf, Mapping) and "workflow_id" in wf:
        st["workflow"] = dict(wf)
        st["workflow"]["workflow_id"] = subwf_map.get(
            str(wf["workflow_id"]), str(wf["workflow_id"])
        )
    for art in st.get("produces") or []:
        if isinstance(art, dict) and art.get("path") in path_map:
            art["path"] = path_map[art["path"]]

    # nested bodies (loop / repair_loop) carry their own stage lists and sub-stages
    if isinstance(st.get("body"), list):
        st["body"] = [
            _rewrite_stage(
                s,
                prefix,
                donated_ids | {str(x.get("id")) for x in st["body"]},
                graft_point,
                role_map,
                gate_map,
                subwf_map,
                path_map,
                rewires,
            )
            for s in st["body"]
            if isinstance(s, Mapping)
        ]
    for key in ("diagnose", "repair", "verify"):
        if isinstance(st.get(key), Mapping):
            st[key] = _rewrite_stage(
                st[key],
                prefix,
                donated_ids,
                graft_point,
                role_map,
                gate_map,
                subwf_map,
                path_map,
                rewires,
            )
    return st


# ------------------------------------------------------------------------- selection


def donated_stage_ids(
    donor: Mapping[str, Any], base: Mapping[str, Any], strategy: str
) -> list[str]:
    """Which donor stages the strategy grafts. THIS is where the strategies differ."""
    top_level = [
        str(s.get("id")) for s in donor.get("stages", []) if isinstance(s, Mapping)
    ]
    base_caps = mechanisms.structural_capabilities(base)
    base_haz = mechanisms.hazard_coverage(base)
    smap = mechanisms.stage_mechanism_map(donor)

    if strategy == "union":
        # every donor stage, contribution or not. Deliberately naive - this is the strategy
        # whose fusions the certifier is expected to REJECT.
        return top_level
    if strategy == "common-core":
        # only stages whose mechanism set the base ALREADY has: the shared spine.
        return [
            sid for sid in top_level if all(base_caps.get(c) for c in smap.get(sid, []))
        ]
    # HONEST SCOPE: these five share ONE selection rule in this implementation, so they are
    # aliases here, not five distinct fusions. Measured on
    # bp-cnc-07 x bp-arc-05: all five produced 9 stages, 0 gratuitous, identical +0.1048/+0.0833.
    # Only `union` and `common-core` are genuinely different selectors today. Differentiating
    # them (conditional-hybrid needs `when` guards on the grafted stages; ensemble needs the
    # donated stages run in PARALLEL under a quorum barrier; progressive needs them behind
    # escalation gates) is real work that is NOT done - do not read this list as seven strategies.
    if strategy in (
        "best-of-breed",
        "stage-splice",
        "conditional-hybrid",
        "progressive",
        "ensemble",
    ):
        wanted: list[str] = []
        for sid in top_level:
            caps = smap.get(sid, [])
            if any(not base_caps.get(c) for c in caps):
                wanted.append(sid)
                continue
            # a stage can also earn its place by covering a hazard the base misses, which is
            # only decidable by removing it - approximated here by the donor covering a hazard
            # the base does not AND this stage being of the kind that carries the mitigation.
            if sid in _hazard_bearing_stage_ids(donor, base_haz):
                wanted.append(sid)
        return wanted
    raise ValueError(
        f"unknown fusion strategy {strategy!r}; known: {FUSION_STRATEGIES}"
    )


def _hazard_bearing_stage_ids(
    donor: Mapping[str, Any], base_haz: Mapping[str, bool]
) -> set[str]:
    """Donor stages that carry a mitigation for a hazard the base leaves uncovered.

    Measured per hazard by ABLATION: drop the candidate stage from the donor and re-run the
    detector. If the detector flips to False, that stage is load-bearing for the hazard. This
    is a real measurement, not an assumption about stage kinds.
    """
    donor_haz = mechanisms.hazard_coverage(donor)
    missing = [h for h, ok in donor_haz.items() if ok and not base_haz.get(h)]
    if not missing:
        return set()
    out: set[str] = set()
    stages = list(donor.get("stages") or [])
    for i, st in enumerate(stages):
        if not isinstance(st, Mapping):
            continue
        ablated = dict(donor)
        ablated["stages"] = stages[:i] + stages[i + 1 :]
        after = mechanisms.hazard_coverage(ablated)
        if any(not after.get(h) for h in missing):
            out.add(str(st.get("id")))
    return out


# ---------------------------------------------------------------------------- fusion


@dataclass
class Fusion:
    doc: dict[str, Any]
    strategy: str
    base_id: str
    donor_id: str
    decomposition: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    #: sha256 over the fused content, excluding `id` and the later-written certification.
    #: Carried so `fuse_and_certify` can re-stamp a REJECTED id without recomputing it.
    payload_digest: str = ""


def fuse(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    strategy: str = "best-of-breed",
    cases: Sequence[bench.Case] | None = None,
) -> Fusion:
    """Fuse two DSL documents. Pure: same inputs -> byte-identical output."""
    if strategy not in FUSION_STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; known: {FUSION_STRATEGIES}")
    cases = list(cases or bench.DEFAULT_CASES)

    # base = the stronger source on the axes a base contributes (its own spine), decided by
    # measurement rather than argument order.
    ra, rb = bench.benchmark(a, cases), bench.benchmark(b, cases)
    key = lambda r: (  # noqa: E731
        r.axes_mean["correctness"] + r.axes_mean["recovery"] + r.axes_mean["usability"],
        r.workflow_id,
    )
    base, donor = (a, b) if key(ra) >= key(rb) else (b, a)
    base_id, donor_id = str(base.get("id")), str(donor.get("id"))
    prefix = "d1."

    fused = copy.deepcopy(dict(base))
    notes: list[str] = []
    conflicts: list[dict[str, str]] = []

    # ---- namespaces: roles / gates / subworkflows / params, union with recorded collisions
    role_map: dict[str, str] = {}
    fused.setdefault("roles", {})
    for name, spec in (donor.get("roles") or {}).items():
        target = name if name not in fused["roles"] else f"{prefix}{name}"
        if name in fused["roles"] and fused["roles"][name] != spec:
            conflicts.append(
                {
                    "namespace": "roles",
                    "id": name,
                    "resolution": f"donor kept as {target}",
                }
            )
        role_map[name] = target
        fused["roles"].setdefault(target, copy.deepcopy(spec))

    gate_map: dict[str, str] = {}
    fused.setdefault("gates", {})
    for name, spec in (donor.get("gates") or {}).items():
        target = name if name not in fused["gates"] else f"{prefix}{name}"
        if name in fused["gates"] and fused["gates"][name] != spec:
            conflicts.append(
                {
                    "namespace": "gates",
                    "id": name,
                    "resolution": f"donor kept as {target}",
                }
            )
        gate_map[name] = target
        fused["gates"].setdefault(target, copy.deepcopy(spec))

    subwf_map: dict[str, str] = {}
    if donor.get("subworkflows"):
        fused.setdefault("subworkflows", {})
        for name, spec in donor["subworkflows"].items():
            target = name if name not in fused["subworkflows"] else f"{prefix}{name}"
            subwf_map[name] = target
            fused["subworkflows"].setdefault(target, copy.deepcopy(spec))

    param_origin: dict[str, str] = {k: base_id for k in (fused.get("params") or {})}
    fused.setdefault("params", {})
    for name, spec in (donor.get("params") or {}).items():
        if name in fused["params"]:
            if fused["params"][name] != spec:
                conflicts.append(
                    {
                        "namespace": "params",
                        "id": name,
                        "resolution": "base definition kept; donor definition discarded",
                    }
                )
            continue
        fused["params"][name] = copy.deepcopy(spec)
        param_origin[name] = donor_id

    # ---- best-of-breed on the top-level policy blocks
    block_origin: dict[str, str] = {}
    for block, keys in _POLICY_BLOCKS.items():
        sb, sd = (
            _block_strength(base.get(block), keys),
            _block_strength(donor.get(block), keys),
        )
        if sd > sb:
            fused[block] = copy.deepcopy(donor[block])
            block_origin[block] = donor_id
            notes.append(
                f"policy block {block!r} taken from {donor_id} "
                f"(strength {sd} > {sb} on {list(keys)})"
            )
        else:
            block_origin[block] = base_id if base.get(block) is not None else "absent"

    # ---- tool_policy is NOT a plain best-of-breed pick.
    # Measured defect (probe: _probe_forge_selfdefects.py, 22 of 120 pairs): when the donor's
    # tool_policy scored higher it REPLACED the base's, discarding the base's allowlist, so the
    # BASE's own roles then violated DSL-SEM-011 ("tool 'Glob' is not in tool_policy.allow and
    # the policy default is deny"). A merged policy must be permissive enough for BOTH sources'
    # declared tools while never being laxer than either on the restrictive fields.
    tool_conflicts: list[dict[str, str]] = []
    bp, dp = (base.get("tool_policy") or {}), (donor.get("tool_policy") or {})
    if bp or dp:
        merged: dict[str, Any] = dict(fused.get("tool_policy") or {})
        for key in ("allow", "require_owner_approval", "write_paths"):
            union = sorted(set(bp.get(key) or []) | set(dp.get(key) or []))
            if union:
                merged[key] = union
        for key in ("deny", "forbid_write_paths"):
            union = sorted(set(bp.get(key) or []) | set(dp.get(key) or []))
            if union:
                merged[key] = union
        # strictest wins on the scalars - a fusion may never relax a source's posture
        merged["default"] = (
            "deny"
            if "deny"
            in {str(bp.get("default", "deny")), str(dp.get("default", "deny"))}
            else "allow"
        )
        net_rank = {"none": 0, "read-only": 1, "full": 2}
        nets = [str(p.get("network", "none")) for p in (bp, dp) if p]
        merged["network"] = (
            min(nets, key=lambda n: net_rank.get(n, 2)) if nets else "none"
        )
        # source_policy carries the untrusted-content and licence posture; the block-level pick
        # could otherwise drop it when the winner happens not to declare one.
        sps = [
            p.get("source_policy")
            for p in (bp, dp)
            if isinstance(p.get("source_policy"), Mapping)
        ]
        if sps:
            merged["source_policy"] = copy.deepcopy(max(sps, key=len))
        # deny beats allow in DSL-SEM-011, so a token one source denies and the other USES is a
        # genuine policy conflict. It is recorded and left in place: silently deleting it from
        # deny would weaken a security posture to make a fusion look acceptable.
        denied = set(merged.get("deny") or [])
        for token in sorted(denied & set(merged.get("allow") or [])):
            tool_conflicts.append(
                {
                    "namespace": "tool_policy",
                    "id": token,
                    "resolution": (
                        "one source denies this tool and the other allows it; deny is KEPT and "
                        "the conflict is reported - the fused document will fail DSL-SEM-011 "
                        "if a stage actually requests it, which is the correct outcome"
                    ),
                }
            )
        fused["tool_policy"] = merged
        block_origin["tool_policy"] = f"merged({base_id}+{donor_id})"
        notes.append(
            "tool_policy merged rather than picked: allow/deny/write-path lists unioned, "
            "default and network taken at the STRICTER of the two"
        )
    conflicts.extend(tool_conflicts)

    # ---- artifact path collisions
    base_paths = {
        str(p.get("path"))
        for _, st in mechanisms.iter_stages(base)
        for p in (st.get("produces") or [])
    }
    donated = donated_stage_ids(donor, base, strategy)
    donated_set = set(donated)
    path_map: dict[str, str] = {}
    for _, st in mechanisms.iter_stages(donor):
        if str(st.get("id")) not in donated_set:
            continue
        for art in st.get("produces") or []:
            p = str(art.get("path"))
            if p in base_paths:
                parts = p.rsplit("/", 1)
                newp = (
                    f"{parts[0]}/{prefix.rstrip('.')}-{parts[1]}"
                    if len(parts) == 2
                    else f"{prefix.rstrip('.')}-{p}"
                )
                path_map[p] = newp
                conflicts.append(
                    {
                        "namespace": "artifact_path",
                        "id": p,
                        "resolution": f"donated artifact rewritten to {newp}",
                    }
                )

    # ---- graft the donated stages after the base's terminal stage
    base_top = [s for s in fused.get("stages") or [] if isinstance(s, Mapping)]
    graft_point = str(base_top[-1]["id"]) if base_top else ""
    rewires: list[dict[str, str]] = []
    donor_top = {
        str(s.get("id")): s for s in donor.get("stages") or [] if isinstance(s, Mapping)
    }
    grafted: list[dict[str, Any]] = []
    synthesized_edges: list[dict[str, str]] = []
    donated_fused_ids = {f"{prefix}{sid}" for sid in donated}
    for sid in donated:
        st = donor_top.get(sid)
        if st is None:
            continue
        new_st = _rewrite_stage(
            st,
            prefix,
            donated_set,
            graft_point,
            role_map,
            gate_map,
            subwf_map,
            path_map,
            rewires,
        )
        deps = list(new_st.get("depends_on") or [])
        # Only a donated stage with NO surviving intra-donation dependency gets an edge to the
        # base's terminal stage. The first version chained every donated stage to its
        # predecessor, which INVENTED ordering edges the donor never had - caught by the
        # decomposition round-trip (_probe_forge_selfdefects.py: 4 of 4 sampled pairs REFUTED
        # with recovered_edges_are_a_subset_of_the_source=false). Serialising for safety is not
        # free: it changes the graph, so it is no longer done blindly.
        if not any(d in donated_fused_ids for d in deps):
            if graft_point and graft_point not in deps:
                deps.append(graft_point)
                synthesized_edges.append(
                    {
                        "from": str(new_st["id"]),
                        "to": graft_point,
                        "reason": "graft point: donated root sequenced after the base spine",
                    }
                )
        if deps:
            new_st["depends_on"] = deps
        grafted.append(new_st)
    fused["stages"] = base_top + grafted

    # ---- stopping rules: union, donor ids prefixed on collision
    existing_rules = {
        str(r.get("id"))
        for r in (fused.get("stopping_rules") or [])
        if isinstance(r, Mapping)
    }
    for r in donor.get("stopping_rules") or []:
        if not isinstance(r, Mapping):
            continue
        rr = copy.deepcopy(dict(r))
        if str(rr.get("id")) in existing_rules:
            rr["id"] = f"{prefix}{rr['id']}"
        fused.setdefault("stopping_rules", []).append(rr)

    # ---- outputs: union, donor keys prefixed on collision
    for name, spec in (donor.get("outputs") or {}).items():
        fused.setdefault("outputs", {})
        target = name if name not in fused["outputs"] else f"{prefix}{name}"
        fused["outputs"].setdefault(target, copy.deepcopy(spec))

    # ---- identity, lineage, decomposition
    # `id` is assigned at the END of this function, once every content-bearing block exists:
    # it is a digest OVER that content, so it cannot be computed here. Re-assigning the key
    # later preserves its position (`fused` is a deepcopy of `base`, which already has `id`),
    # so the emitted JSON keeps `id` as its second key.
    fused["version"] = "1.0.0"
    fused["name"] = (
        f"Fused ({strategy}): {base.get('name', base_id)} + {donor.get('name', donor_id)}"
    )
    fused["description"] = (
        f"Forged by workflow-forge with strategy {strategy!r} from {base_id} (base) and "
        f"{donor_id} (donor). Grafted {len(grafted)} of "
        f"{len(donor_top)} donor top-level stages. This document is NOT accepted for being "
        f"larger: see x_extensions.foundry.certification for the measured axis deltas that "
        f"justify it, per spec {SPEC_ANCHOR_ACCEPTANCE}."
    )
    fused["flagship"] = False
    base_lineage = base.get("lineage") or {}
    donor_lineage = donor.get("lineage") or {}
    fused["lineage"] = {
        "derived_from": [
            {
                "source": base_id,
                "relation": "MERGE",
                "license": _lineage_license(base_lineage),
                "credit": _lineage_credit(base_lineage, base_id),
            },
            {
                "source": donor_id,
                "relation": "MERGE",
                "license": _lineage_license(donor_lineage),
                "credit": _lineage_credit(donor_lineage, donor_id),
            },
        ],
        "decomposable_back_to_sources": True,
        "rollback_to": [
            f"{base_id}@{base.get('version', '0.0.0')}",
            f"{donor_id}@{donor.get('version', '0.0.0')}",
        ],
    }

    decomposition = {
        "strategy": strategy,
        "base": {"id": base_id, "version": str(base.get("version", ""))},
        "donor": {"id": donor_id, "version": str(donor.get("version", ""))},
        "donor_prefix": prefix,
        "stage_origin": {
            **{str(s["id"]): base_id for s in base_top},
            **{str(s["id"]): donor_id for s in grafted},
        },
        "donated_stage_ids": donated,
        "donated_original_to_fused": {sid: f"{prefix}{sid}" for sid in donated},
        "not_donated_stage_ids": sorted(set(donor_top) - donated_set),
        "role_map": role_map,
        "gate_map": gate_map,
        "subworkflow_map": subwf_map,
        "param_origin": param_origin,
        "policy_block_origin": block_origin,
        "artifact_path_rewrites": path_map,
        "dependency_rewires": rewires,
        "synthesized_edges": synthesized_edges,
        "conflicts": conflicts,
    }
    fused["x_extensions"] = {
        **(dict(base.get("x_extensions") or {})),
        "foundry": {
            "tool": "workflow-forge",
            "version": "1.0.0",
            "spec_anchor": SPEC_ANCHOR_FOUNDRY_PIPELINE,
            "decomposition": decomposition,
        },
    }
    payload_digest = fusion_payload_digest(fused)
    fused["id"] = _fused_id(base_id, donor_id, strategy, payload_digest)
    return Fusion(
        doc=fused,
        strategy=strategy,
        base_id=base_id,
        donor_id=donor_id,
        decomposition=decomposition,
        notes=notes,
        conflicts=conflicts,
        payload_digest=payload_digest,
    )


def _lineage_license(lineage: Mapping[str, Any]) -> str:
    for d in lineage.get("derived_from") or []:
        if isinstance(d, Mapping) and d.get("license"):
            return str(d["license"])
    return "owner-proprietary"


def _lineage_credit(lineage: Mapping[str, Any], fallback: str) -> str:
    credits = [
        str(d["credit"])
        for d in lineage.get("derived_from") or []
        if isinstance(d, Mapping) and d.get("credit")
    ]
    return ", ".join(dict.fromkeys(credits)) if credits else fallback


# --------------------------------------------------------------------- decomposition


def decompose(
    fused_doc: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Invert a fusion: recover which mechanisms each source contributed.

    ``sources`` maps source id -> the ORIGINAL document. When supplied, the reconstruction is
    checked against those documents with an exact topology comparison and the result is
    CONFIRMED or REFUTED. When omitted, the structural reconstruction still runs but the
    round-trip verdict is NOT-CHECKED - a decomposition nobody compared to the real sources is
    a claim, not a receipt.
    """
    ext = ((fused_doc.get("x_extensions") or {}).get("foundry") or {}).get(
        "decomposition"
    )
    if not ext:
        return {
            "ok": False,
            "verdict": "REFUTED",
            "reason": (
                "no x_extensions.foundry.decomposition record: this document does not carry "
                "the lineage needed to decompose it back into source mechanisms"
            ),
        }
    base_id = str(ext["base"]["id"])
    donor_id = str(ext["donor"]["id"])
    stage_origin: dict[str, str] = dict(ext.get("stage_origin") or {})

    fused_stages = {
        str(st.get("id")): st for _, st in mechanisms.iter_stages(fused_doc)
    }
    top_level = [
        str(s.get("id"))
        for s in fused_doc.get("stages") or []
        if isinstance(s, Mapping)
    ]

    unattributed = [sid for sid in top_level if sid not in stage_origin]
    per_source: dict[str, dict[str, Any]] = {}
    for src in (base_id, donor_id):
        sids = [sid for sid in top_level if stage_origin.get(sid) == src]
        originals = [
            _DONOR_PREFIX.sub("", sid) if src == donor_id else sid for sid in sids
        ]
        smap = mechanisms.stage_mechanism_map(
            {"stages": [fused_stages[s] for s in sids if s in fused_stages]}
        )
        caps: set[str] = set()
        for v in smap.values():
            caps |= set(v)
        per_source[src] = {
            "fused_stage_ids": sids,
            "original_stage_ids": originals,
            "contributed_capabilities": sorted(caps),
        }

    result: dict[str, Any] = {
        "ok": not unattributed,
        "strategy": ext.get("strategy"),
        "base": base_id,
        "donor": donor_id,
        "unattributed_stages": unattributed,
        "per_source": per_source,
        "artifact_path_rewrites": ext.get("artifact_path_rewrites") or {},
        "dependency_rewires": ext.get("dependency_rewires") or [],
        "conflicts": ext.get("conflicts") or [],
        "roundtrip": {
            "verdict": "NOT-CHECKED",
            "detail": "original source documents not supplied",
        },
    }
    if unattributed:
        result["verdict"] = "REFUTED"
        result["reason"] = (
            f"{len(unattributed)} fused stages have no source attribution"
        )
        return result

    if sources:
        checks: dict[str, Any] = {}
        all_ok = True
        for src in (base_id, donor_id):
            original = sources.get(src)
            if original is None:
                checks[src] = {
                    "verdict": "NOT-CHECKED",
                    "detail": "source document not supplied",
                }
                all_ok = False
                continue
            want_ids = set(per_source[src]["original_stage_ids"])
            src_topo = [t for t in topology(original) if t[0] in want_ids]
            rebuilt = []
            for sid in per_source[src]["fused_stage_ids"]:
                st = fused_stages[sid]
                oid = _DONOR_PREFIX.sub("", sid) if src == donor_id else sid
                deps = tuple(
                    _DONOR_PREFIX.sub("", str(d))
                    for d in (st.get("depends_on") or [])
                    if _DONOR_PREFIX.sub("", str(d)) in want_ids
                )
                rebuilt.append((oid, str(st.get("kind")), deps))
            ids_match = [t[0] for t in src_topo] == [t[0] for t in rebuilt]
            kinds_match = [t[1] for t in src_topo] == [t[1] for t in rebuilt]
            # edges: every rebuilt edge must exist in the source. The reverse does NOT hold for
            # a donor whose stages were partially donated - a dropped edge is recorded in
            # dependency_rewires, so it is disclosed rather than asserted away.
            src_edges = {(t[0], d) for t in src_topo for d in t[2]}
            rebuilt_edges = {(t[0], d) for t in rebuilt for d in t[2]}
            # DISCLOSED additions are subtracted before the subset test. An edge the forge
            # synthesized is recorded in the lineage, so it is an audited addition rather than a
            # silent graph change; an edge that is neither in the source NOR disclosed is a real
            # refutation.
            disclosed = {
                (
                    _DONOR_PREFIX.sub("", str(e.get("from"))),
                    _DONOR_PREFIX.sub("", str(e.get("to"))),
                )
                for e in (ext.get("synthesized_edges") or [])
            }
            undisclosed = rebuilt_edges - src_edges - disclosed
            edges_subset = not undisclosed
            ok = ids_match and kinds_match and edges_subset
            all_ok = all_ok and ok
            checks[src] = {
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "stage_ids_recovered": ids_match,
                "stage_kinds_recovered": kinds_match,
                "recovered_edges_are_a_subset_of_the_source": edges_subset,
                "undisclosed_edges": sorted(undisclosed),
                "source_stage_count_donated": len(src_topo),
                "edges_dropped_by_partial_donation": sorted(src_edges - rebuilt_edges),
            }
        result["roundtrip"] = {
            "verdict": "CONFIRMED" if all_ok else "REFUTED",
            "method": (
                "workflows.mechanisms.topology over the donated sub-topology, id-prefix "
                "stripped; exact tuple comparison of (id, kind) sequence plus an edge-subset "
                "check"
            ),
            "per_source": checks,
        }
        result["ok"] = bool(result["ok"] and all_ok)
    result["verdict"] = (
        "CONFIRMED"
        if result["ok"] and sources
        else ("PARTIAL" if result["ok"] else "REFUTED")
    )
    return result


# ------------------------------------------------------------------- fuse + certify


def fuse_and_certify(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    strategy: str = "best-of-breed",
    cases: Sequence[bench.Case] | None = None,
    goal: Goal | None = None,
) -> dict[str, Any]:
    """The full forge pipeline for one pair: fuse, benchmark all three, certify or REJECT."""
    cases = list(cases or bench.DEFAULT_CASES)
    fusion = fuse(a, b, strategy=strategy, cases=cases)
    r_fused = bench.benchmark(fusion.doc, cases)
    r_a = bench.benchmark(a, cases)
    r_b = bench.benchmark(b, cases)
    dec = decompose(fusion.doc, {str(a.get("id")): a, str(b.get("id")): b})
    grafted_ids = list(fusion.decomposition["donated_original_to_fused"].values())
    gratuitous = bench.gratuitous_stages(fusion.doc, cases, grafted_ids)
    cert = bench.certify(
        r_fused,
        [r_a, r_b],
        decomposes_back=(dec.get("roundtrip", {}).get("verdict") == "CONFIRMED"),
        gratuitous=gratuitous,
    )
    # A tool-policy conflict makes the fused document fail DSL-SEM-011, which the certifier sees
    # only as "fails the DSL gate". Name the real cause: one source DENIES a tool the other USES,
    # and the merge kept the deny rather than weakening a security posture to make the fusion
    # look acceptable. That is a legitimate reason not to fuse these two, not a forge bug.
    tool_conflicts = [
        c for c in fusion.conflicts if c.get("namespace") == "tool_policy"
    ]
    if tool_conflicts and not cert.accepted:
        cert.reasons.insert(
            0,
            "tool-policy conflict: "
            + "; ".join(
                f"{c['id']} denied by one source and allowed by the other"
                for c in tool_conflicts
            )
            + " - the stricter posture was kept, so the fused document is intentionally invalid",
        )
    # D4: the verdict is only known HERE, so re-stamp the id under the `rejected.` namespace
    # when the certifier refused. Without this a loader keyed on id could resolve the rejected
    # union in place of the certified fusion of the same pair - the measured D4 hazard.
    if not cert.accepted:
        fusion.doc["id"] = _fused_id(
            fusion.base_id,
            fusion.donor_id,
            fusion.strategy,
            fusion.payload_digest,
            rejected=True,
        )
    fusion.doc["x_extensions"]["foundry"]["certification"] = {
        "verdict": cert.verdict,
        "reasons": cert.reasons,
        "axis_improvements_over_best_source": {
            k: round(v, 4) for k, v in cert.improvements.items()
        },
        "axis_regressions_against_best_source": {
            k: round(v, 4) for k, v in cert.regressions.items()
        },
        "cost_delta_vs_largest_source": cert.cost_delta,
        "cases": [c.id for c in cases],
        "acceptance_bar": SPEC_ANCHOR_ACCEPTANCE,
        "stage_count_is_not_an_axis": True,
        "grafted_stages": grafted_ids,
        "gratuitous_stages_measured_by_ablation": gratuitous,
    }
    return {
        "tool": "workflow-forge",
        "strategy": strategy,
        "gratuitous_stages": gratuitous,
        "goal": goal.to_json() if goal else None,
        "base": fusion.base_id,
        "donor": fusion.donor_id,
        "fused_id": fusion.doc["id"],
        "certification": cert.to_json(),
        "decomposition": dec,
        "fusion_notes": fusion.notes,
        "fusion_conflicts": fusion.conflicts,
        "doc": fusion.doc,
    }


def tournament(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    cases: Sequence[bench.Case] | None = None,
    strategies: Sequence[str] = FUSION_STRATEGIES,
) -> dict[str, Any]:
    """Run every fusion strategy on one pair and pick the CHEAPEST certified result.

    Spec :11276 ("A/B and tournament benchmarking") and :11019 ("workflow tournament"). The
    tie-break is cost, ASCENDING - among fusions that clear the bar, the smallest wins. This is
    the positive form of the acceptance rule: size is never a reason to accept, and among equals
    it is a reason to prefer the other one.
    """
    cases = list(cases or bench.DEFAULT_CASES)
    rows: list[dict[str, Any]] = []
    for strat in strategies:
        out = fuse_and_certify(a, b, strategy=strat, cases=cases)
        cert = out["certification"]
        rows.append(
            {
                "strategy": strat,
                "verdict": cert["verdict"],
                "improvements": cert["axis_improvements_over_best_source"],
                "regressions": cert["axis_regressions_against_best_source"],
                "stage_count": cert["fused"]["cost"]["stage_count"],
                "stage_delta": cert["cost_delta_vs_largest_source"]["stage_count"],
                "gratuitous_stages": out["gratuitous_stages"],
                "roundtrip": out["decomposition"]["roundtrip"]["verdict"],
                "reasons": cert["reasons"],
                "_doc": out["doc"],
            }
        )
    winners = [r for r in rows if r["verdict"] == "CERTIFIED"]
    winners.sort(
        key=lambda r: (
            r["stage_count"],
            -sum(r["improvements"].values()),
            r["strategy"],
        )
    )
    return {
        "tool": "workflow-forge",
        "mode": "tournament",
        "pair": [str(a.get("id")), str(b.get("id"))],
        "cases": [c.id for c in cases],
        "entrants": [{k: v for k, v in r.items() if k != "_doc"} for r in rows],
        "certified_count": len(winners),
        "winner": (
            {k: v for k, v in winners[0].items() if k != "_doc"} if winners else None
        ),
        "winner_doc": winners[0]["_doc"] if winners else None,
        "tie_break": (
            "cost ASCENDING among certified entrants - size never accepts a fusion and among "
            "equals it argues against one"
        ),
    }


# ------------------------------------------------------------------------------- CLI


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="workflow-forge",
        description="fuse two workflows, benchmark against their sources, certify or REJECT",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fuse", help="fuse two DSL documents and certify the result")
    f.add_argument(
        "--source", action="append", required=True, help="path to a DSL workflow (x2)"
    )
    f.add_argument(
        "--strategy", default="best-of-breed", choices=list(FUSION_STRATEGIES)
    )
    f.add_argument(
        "--cases", help="path to a case library JSON (defaults to the built-in 6)"
    )
    f.add_argument("--out", help="write the fused workflow here (only if CERTIFIED)")
    f.add_argument(
        "--emit-rejected",
        action="store_true",
        help="also write the document when the verdict is REJECTED, for evidence",
    )
    f.add_argument("--report", help="write the full forge report here")

    d = sub.add_parser(
        "decompose", help="decompose a fused workflow back to its sources"
    )
    d.add_argument("--workflow", required=True)
    d.add_argument(
        "--source", action="append", help="an original source document (repeatable)"
    )
    d.add_argument("--json", help="write the decomposition report here")

    t = sub.add_parser(
        "tournament",
        help="run every strategy on one pair and pick the cheapest certified result",
    )
    t.add_argument("--source", action="append", required=True)
    t.add_argument("--cases")
    t.add_argument("--out", help="write the winning workflow here")
    t.add_argument("--report")

    sub.add_parser("strategies", help="list the fusion strategies")

    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "tournament":
        if len(args.source) != 2:
            print(
                "FAILED:forge-tournament exactly two --source arguments",
                file=sys.stderr,
            )
            return 2
        a, b = _load(args.source[0]), _load(args.source[1])
        cases = bench.load_cases(Path(args.cases) if args.cases else None)
        res = tournament(a, b, cases)
        print(f"# workflow-forge tournament  {res['pair'][0]}  x  {res['pair'][1]}")
        print(
            f"{'strategy':<20} {'verdict':<10} {'stages':>7} {'delta':>6} {'gratis':>7}  improvements"
        )
        for r in res["entrants"]:
            print(
                f"{r['strategy']:<20} {r['verdict']:<10} {r['stage_count']:>7} "
                f"{r['stage_delta']:>+6} {len(r['gratuitous_stages']):>7}  "
                + ", ".join(f"{k} +{v}" for k, v in sorted(r["improvements"].items()))
            )
        print()
        if res["winner"]:
            print(
                f"WINNER: {res['winner']['strategy']} "
                f"({res['winner']['stage_count']} stages, tie-break = {res['tie_break']})"
            )
            if args.out:
                Path(args.out).write_text(
                    json.dumps(res["winner_doc"], indent=2) + "\n", encoding="utf-8"
                )
                print(f"wrote: {args.out}")
        else:
            print("WINNER: none - every strategy was REJECTED for this pair")
        if args.report:
            rep = {k: v for k, v in res.items() if k != "winner_doc"}
            Path(args.report).write_text(
                json.dumps(rep, indent=2) + "\n", encoding="utf-8"
            )
            print(f"report: {args.report}")
        print("SUCCESS:forge-tournament")
        return 0

    if args.cmd == "strategies":
        for s in FUSION_STRATEGIES:
            print(s)
        print("SUCCESS:forge-strategies")
        return 0

    if args.cmd == "decompose":
        doc = _load(args.workflow)
        srcs = {}
        for p in args.source or []:
            s = _load(p)
            srcs[str(s.get("id"))] = s
        rep = decompose(doc, srcs or None)
        if args.json:
            Path(args.json).write_text(
                json.dumps(rep, indent=2) + "\n", encoding="utf-8"
            )
        print(json.dumps(rep, indent=2))
        marker = (
            "SUCCESS" if rep.get("verdict") in ("CONFIRMED", "PARTIAL") else "FAILED"
        )
        print(f"{marker}:forge-decompose {rep.get('verdict')}")
        return 0 if marker == "SUCCESS" else 1

    if len(args.source) != 2:
        print(
            "FAILED:forge-fuse exactly two --source arguments are required",
            file=sys.stderr,
        )
        return 2
    a, b = _load(args.source[0]), _load(args.source[1])
    cases = bench.load_cases(Path(args.cases) if args.cases else None)
    out = fuse_and_certify(a, b, strategy=args.strategy, cases=cases)
    cert = out["certification"]

    print(f"# workflow-forge  strategy={args.strategy}")
    print(f"base : {out['base']}")
    print(f"donor: {out['donor']}")
    print(f"fused: {out['fused_id']}")
    print()
    print(f"{'axis':<14} {'base':>8} {'donor':>8} {'fused':>8}   delta vs best source")
    src_axes = {s["workflow_id"]: s["axes_mean"] for s in cert["sources"]}
    fa = cert["fused"]["axes_mean"]
    for axis in ("correctness", "coverage", "recovery", "usability"):
        va = src_axes.get(out["base"], {}).get(axis, 0.0)
        vb = src_axes.get(out["donor"], {}).get(axis, 0.0)
        vf = fa.get(axis, 0.0)
        print(f"{axis:<14} {va:>8.4f} {vb:>8.4f} {vf:>8.4f}   {vf - max(va, vb):+.4f}")
    print()
    print(f"cost (NOT an axis): {cert['cost_delta_vs_largest_source']}")
    print(
        f"DSL gate: schema_valid={cert['fused']['schema_valid']} "
        f"semantic_violations={cert['fused']['semantic_violations']}"
    )
    print(f"decomposition roundtrip: {out['decomposition']['roundtrip']['verdict']}")
    print()
    print(f"VERDICT: {cert['verdict']}")
    for r in cert["reasons"]:
        print(f"  - {r}")

    wrote = None
    if args.out and (cert["accepted"] or args.emit_rejected):
        Path(args.out).write_text(
            json.dumps(out["doc"], indent=2) + "\n", encoding="utf-8"
        )
        wrote = args.out
        print(f"\nwrote: {args.out}")
    elif args.out:
        print(
            f"\nNOT written to {args.out}: verdict is REJECTED "
            "(pass --emit-rejected to keep it as evidence)"
        )
    if args.report:
        report = {k: v for k, v in out.items() if k != "doc"}
        report["emitted_to"] = wrote
        Path(args.report).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(f"report: {args.report}")

    if cert["accepted"]:
        print("SUCCESS:forge-fuse CERTIFIED")
        return 0
    print(
        "SUCCESS:forge-fuse REJECTED (the gate fired; this is a working gate, not an error)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
