"""Test support for blueprint range bp-4 (document-order 37-48 of the 96 built-ins).

Scope of this module: it LOADS and MEASURES the twelve bp-4 blueprint documents. It does not
template any of them - every stage graph, gate, role and stopping rule is written out by hand in
``platform/workflows/<id>.json``, because a shared authoring template is exactly how a catalog of
near-duplicates gets manufactured.

The distinctness measurement here is an EXACT ALGORITHM over the documents (token sets +
Jaccard), not a judgement: an LLM asked to classify mechanical similarity measured 86% accurate
with 100% of its errors pointing the unsafe way, so the comparison is code.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from wfdsl import expr as _expr
from wfdsl import schemas as _schemas
from wfdsl import semantics as _semantics

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"
CATALOG_PATH = REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"

#: (document-order position over the 108 cards, source card id, workflow id, flagship)
BP4_RANGE: tuple[tuple[int, str, str, bool], ...] = (
    (37, "BP-PLN-05", "stale-mega-pr-reconcile", False),
    (38, "BP-IMP-01", "per-unit-four-phase-pipeline", True),
    (39, "BP-IMP-02", "worktree-isolated-parallel-build", True),
    (40, "BP-IMP-03", "execution-consensus-patch-select", False),
    (41, "BP-IMP-04", "tdd-red-proof-batches", True),
    (42, "BP-IMP-05", "remote-fleet-propose-only", False),
    (43, "BP-IMP-06", "shared-prod-shard-fanout-build", False),
    (44, "BP-DBG-01", "systematic-debugging-ladder", False),
    (45, "BP-DBG-02", "both-states-detector-control", True),
    (46, "BP-DBG-03", "two-signal-corroboration-gate", True),
    (47, "BP-DBG-04", "fresh-context-rederivation-tiebreak", False),
    (48, "BP-DBG-05", "silent-disarm-hunt", True),
)

BP4_IDS: tuple[str, ...] = tuple(row[2] for row in BP4_RANGE)
BP4_FLAGSHIP: tuple[str, ...] = tuple(row[2] for row in BP4_RANGE if row[3])

#: The six domains the spec requires the 96 to span, slugified as the DSL's `categories` tokens.
SPEC_CATEGORIES = frozenset(
    {
        "research-and-evidence",
        "engineering-and-reliability",
        "security-governance-and-risk",
        "product-design-and-strategy",
        "data-science-knowledge-and-creative",
        "collective-intelligence-and-meta",
    }
)

#: Every stage kind the DSL defines; the SET is expected to span all nine.
ALL_STAGE_KINDS = frozenset(
    {
        "task",
        "subworkflow",
        "fanout",
        "barrier",
        "loop",
        "gate",
        "human_checkpoint",
        "repair_loop",
        "council",
    }
)


# ------------------------------------------------------------------------------- loading


def path_for(workflow_id: str) -> Path:
    return WORKFLOW_DIR / f"{workflow_id}.json"


def load(workflow_id: str) -> dict[str, Any]:
    return json.loads(path_for(workflow_id).read_text(encoding="utf-8"))


def load_all() -> dict[str, dict[str, Any]]:
    return {wid: load(wid) for wid in BP4_IDS}


def catalog_ids() -> frozenset[str]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return frozenset(str(u.get("id")) for u in catalog.get("work_units", []))


# ---------------------------------------------------------------------------- validation


def schema_errors(doc: Mapping[str, Any]) -> list[str]:
    return _schemas.error_summary(
        _schemas.workflow_validator().iter_errors(doc), limit=8
    )


def semantic_violations(doc: Mapping[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rule in _semantics.check_workflow(doc):
        if rule.severity == "violation":
            out.extend((f"{rule.rule}:{s}", d) for s, d in rule.violations)
    return out


def semantic_advisories(doc: Mapping[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rule in _semantics.check_workflow(doc):
        if rule.severity == "advisory":
            out.extend((f"{rule.rule}:{s}", d) for s, d in rule.violations)
    return out


# ------------------------------------------------------------------------------ walking


def stages(doc: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """Every stage depth-first, including fan-out/loop bodies and repair sub-stages."""
    return _semantics.iter_stages(doc)


def stage(doc: Mapping[str, Any], stage_id: str) -> Mapping[str, Any]:
    for _, st in stages(doc):
        if st.get("id") == stage_id:
            return st
    raise AssertionError(f"stage {stage_id!r} not found in {doc.get('id')!r}")


def stage_ids(doc: Mapping[str, Any]) -> list[str]:
    return [str(st.get("id")) for _, st in stages(doc)]


def top_level_stage_ids(doc: Mapping[str, Any]) -> list[str]:
    return [str(st.get("id")) for st in doc.get("stages", [])]


def assert_precedes(order: list[str], earlier: str, later: str) -> None:
    """Assert both stages are present AND ordered.

    A bare ``order.index(x) < order.index(y)`` raises ValueError when a stage is deleted, and
    ``raises_assertion`` only catches AssertionError - so a deletion mutation would escape the
    both-states control as an error rather than a detected defect. Presence is asserted first.
    """
    assert earlier in order, f"stage {earlier!r} is absent from {order}"
    assert later in order, f"stage {later!r} is absent from {order}"
    assert order.index(earlier) < order.index(later), (
        f"{earlier!r} must precede {later!r}"
    )


def gate(doc: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    gates = doc.get("gates") or {}
    if name not in gates:
        raise AssertionError(
            f"gate {name!r} not declared in {doc.get('id')!r}; have {sorted(gates)}"
        )
    return gates[name]


def work_unit_refs(doc: Mapping[str, Any]) -> list[str]:
    return [str(st["work_unit_ref"]) for _, st in stages(doc) if "work_unit_ref" in st]


def inline_work_units(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        st["work_unit"]
        for _, st in stages(doc)
        if isinstance(st.get("work_unit"), Mapping)
    ]


def schema_references(doc: Any) -> list[str]:
    """Every `schema_ref` / `output_schema` / `predicate_ref` string anywhere in the document."""
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if key in {
                    "schema_ref",
                    "output_schema",
                    "predicate_ref",
                } and isinstance(value, str):
                    found.append(value)
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(doc)
    return found


def resolve_schema_reference(ref: str) -> Path | None:
    """Map a repo-relative schema reference (with an optional #pointer) to a real file."""
    if ref.startswith(("http://", "https://")):
        return None
    relative = ref.split("#", 1)[0]
    candidate = REPO_ROOT / relative
    return candidate if candidate.is_file() else None


# ------------------------------------------------------------------- mechanism fingerprint


def _expression_identifiers(value: Any) -> set[str]:
    if isinstance(value, str):
        try:
            return set(_expr.identifiers(value))
        except (
            _expr.ExpressionError
        ):  # pragma: no cover - DSL-SEM-007 already gates this
            return set()
    if isinstance(value, Mapping):
        out: set[str] = set()
        for key, inner in value.items():
            if key == "weighted" and isinstance(inner, Mapping):
                for term in inner.get("terms", []) or []:
                    if isinstance(term, Mapping):
                        out |= _expression_identifiers(term.get("expr"))
            else:
                out |= _expression_identifiers(inner)
        return out
    if isinstance(value, list):
        out = set()
        for item in value:
            out |= _expression_identifiers(item)
        return out
    return set()


def mechanism_tokens(doc: Mapping[str, Any]) -> frozenset[str]:
    """A token set describing WHAT THE DOCUMENT DOES, ignoring its prose.

    Deliberately excludes name/description/title/tags: two blueprints that differ only in
    wording must land on the same token set so the distinctness check can catch them.
    """
    tokens: set[str] = set()

    for _, st in stages(doc):
        tokens.add(f"kind:{st.get('kind')}")
        barrier = st.get("barrier")
        if isinstance(barrier, Mapping):
            tokens.add(f"barrier:{barrier.get('mode')}/{barrier.get('on_partial')}")
        over = st.get("over")
        if isinstance(over, Mapping):
            tokens.add(f"over:{over.get('source')}")
        conv = st.get("convergence")
        if isinstance(conv, Mapping):
            for metric in conv.get("metrics", []) or []:
                if isinstance(metric, Mapping):
                    tokens.add(f"metric:{metric.get('name')}")
            tokens |= {
                f"expr:{i}" for i in _expression_identifiers(conv.get("converged_when"))
            }
        if isinstance(st.get("workflow"), Mapping):
            wid = st["workflow"].get("workflow_id")
            tokens.add(f"child:{wid}" if wid else "child:inline")

    for name, spec in (doc.get("gates") or {}).items():
        tokens.add(f"gatepred:{spec.get('predicate')}/{spec.get('on_fail')}")
        tokens.add(f"gate:{name}")
        tokens |= {f"expr:{i}" for i in _expression_identifiers(spec.get("expression"))}

    for rule in doc.get("stopping_rules") or []:
        if isinstance(rule, Mapping):
            tokens |= {
                f"expr:{i}" for i in _expression_identifiers(rule.get("expression"))
            }
            tokens |= {
                f"expr:{i}"
                for i in _expression_identifiers(rule.get("minimum_conditions"))
            }
            tokens.add(f"stop:{rule.get('on_stop')}")

    for pname in doc.get("params") or {}:
        tokens.add(f"param:{pname}")
    for rname in doc.get("roles") or {}:
        tokens.add(f"role:{rname}")
    for sname in doc.get("subworkflows") or {}:
        tokens.add(f"sub:{sname}")

    retry = doc.get("retry_policy") or {}
    tokens.add(f"retry:{retry.get('strategy')}")
    failure = doc.get("failure_policy") or {}
    tokens.add(f"failure:{failure.get('on_failure')}")
    for cls in failure.get("classify_as", []) or []:
        tokens.add(f"class:{cls}")
    tokens.add(f"replay:{(doc.get('replay') or {}).get('deterministic')}")
    tokens.add(f"resume:{(doc.get('resume') or {}).get('granularity')}")
    tokens.add(f"cache:{(doc.get('cache') or {}).get('enabled')}")

    return frozenset(tokens)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def pairwise_similarity(
    docs: Mapping[str, Mapping[str, Any]],
) -> list[tuple[float, str, str]]:
    """Every unordered pair, most similar first."""
    tokens = {wid: mechanism_tokens(doc) for wid, doc in docs.items()}
    keys = sorted(tokens)
    rows: list[tuple[float, str, str]] = []
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            rows.append((jaccard(tokens[a], tokens[b]), a, b))
    rows.sort(reverse=True)
    return rows


# -------------------------------------------------------------------------- mutation kit


def mutant(
    doc: Mapping[str, Any], apply: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    """A deep copy with ``apply`` applied - the both-states control's broken state.

    Every assertion helper in the bp-4 suite is run against the real document (must pass) AND
    against a mutant (must raise). A check that is silent on both measures nothing.
    """
    clone = copy.deepcopy(dict(doc))
    apply(clone)
    return clone


def find_stage_mut(doc: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Locate a stage in a MUTABLE copy so a mutation can be applied in place."""

    def walk(nodes: Any) -> Iterator[dict[str, Any]]:
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict):
                    yield node
                    yield from walk(node.get("body"))
                    for key in ("diagnose", "repair", "verify"):
                        sub = node.get(key)
                        if isinstance(sub, dict):
                            yield sub
                            yield from walk(sub.get("body"))

    for candidate in walk(doc.get("stages")):
        if candidate.get("id") == stage_id:
            return candidate
    raise AssertionError(f"stage {stage_id!r} not present in the mutant")


def raises_assertion(
    check: Callable[[Mapping[str, Any]], None], doc: Mapping[str, Any]
) -> bool:
    """True when ``check`` rejects ``doc``. Used to prove a check can actually fail."""
    try:
        check(doc)
    except AssertionError:
        return True
    return False
