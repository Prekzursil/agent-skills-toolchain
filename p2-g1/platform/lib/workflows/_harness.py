"""Shared helpers for the bp-6 blueprint tests.

Three jobs:

1. **Conformance** - re-use the SAME validator the CLI uses (``wfdsl.schemas.workflow_validator``
   plus ``wfdsl.semantics.check_workflow``) so a test cannot pass against a laxer checker than
   the one the unit reports. Works on an in-memory document, which is what makes the mutation
   controls possible.
2. **Worked-example conformance** - the DSL schema cannot express "the worked example's params
   actually satisfy the declared params" or "its expected artifacts are ones this workflow
   produces", because those are cross-field rules over a vendor extension. They are checked here,
   and every blueprint test exercises the checker in BOTH states: clean, and against a mutant
   where one binding has been removed.
3. **Inline work-unit rules the workflow validator does not reach.** ``DSL-SEM-002`` (a completion
   sentinel must name its own unit id) is applied by ``semantics.check_work_units`` to a CATALOG,
   not to work units embedded in a DSL stage. A unit inlined in a blueprint therefore gets no
   sentinel check from either side, so :func:`sentinel_violations` closes that gap here.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
LIB_ROOT = REPO_ROOT / "platform" / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from wfdsl import schemas, semantics  # noqa: E402

WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"
UNIT_ID_RE = re.compile(r"^[A-Z]{2,4}-[0-9]{4}$")
TERMINAL_RE = re.compile(r"^SUCCESS:[A-Z]{2,4}-[0-9]{4}$")


# ------------------------------------------------------------------ loading / traversal


def load(name: str) -> dict[str, Any]:
    """Load one blueprint by file name (with or without the .json suffix)."""
    fname = name if name.endswith(".json") else f"{name}.json"
    path = WORKFLOW_DIR / fname
    if not path.is_file():
        raise FileNotFoundError(f"blueprint not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def stages(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Every stage depth-first, including fan-out/loop bodies and repair-loop arms."""
    out: list[dict[str, Any]] = []

    def walk(items: Any) -> None:
        if not isinstance(items, list):
            return
        for st in items:
            if not isinstance(st, dict):
                continue
            out.append(st)
            walk(st.get("body"))
            for key in ("diagnose", "repair", "verify"):
                sub = st.get(key)
                if isinstance(sub, dict):
                    out.append(sub)
                    walk(sub.get("body"))

    walk(doc.get("stages"))
    return out


def top_level_stage_ids(doc: dict[str, Any]) -> list[str]:
    return [str(s.get("id")) for s in (doc.get("stages") or []) if isinstance(s, dict)]


def stage_ids(doc: dict[str, Any]) -> set[str]:
    return {str(s.get("id")) for s in stages(doc)}


def stage(doc: dict[str, Any], sid: str) -> dict[str, Any]:
    for st in stages(doc):
        if str(st.get("id")) == sid:
            return st
    raise KeyError(
        f"no stage {sid!r} in {doc.get('id')!r}; have {sorted(stage_ids(doc))}"
    )


def inline_units(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        st["work_unit"] for st in stages(doc) if isinstance(st.get("work_unit"), dict)
    ]


def declared_paths(doc: dict[str, Any]) -> set[str]:
    """Every artifact path this workflow claims to write."""
    paths: set[str] = set()
    for spec in (doc.get("outputs") or {}).values():
        if isinstance(spec, dict) and spec.get("path"):
            paths.add(str(spec["path"]))
    for st in stages(doc):
        for spec in st.get("produces") or []:
            if isinstance(spec, dict) and spec.get("path"):
                paths.add(str(spec["path"]))
        dec = st.get("decision_artifact")
        if isinstance(dec, dict) and dec.get("path"):
            paths.add(str(dec["path"]))
    return paths


def gate_expressions(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        name: g.get("expression")
        for name, g in (doc.get("gates") or {}).items()
        if isinstance(g, dict)
    }


def all_tool_tokens(doc: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for rspec in (doc.get("roles") or {}).values():
        if isinstance(rspec, dict):
            tokens |= {str(t) for t in rspec.get("tool_permissions") or []}
    for st in stages(doc):
        tokens |= {str(t) for t in st.get("tool_permissions") or []}
        wu = st.get("work_unit")
        if isinstance(wu, dict):
            tokens |= {str(t) for t in wu.get("tool_permissions") or []}
    return tokens


# ------------------------------------------------------------------------ conformance


def schema_errors(doc: dict[str, Any]) -> list[str]:
    errs = sorted(
        schemas.workflow_validator().iter_errors(doc),
        key=lambda e: list(e.absolute_path),
    )
    return schemas.error_summary(errs, limit=8)


def semantic_violations(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for rule in semantics.check_workflow(doc):
        if rule.severity != "violation":
            continue
        for subject, detail in rule.violations:
            out.append(f"{rule.rule} {subject}: {detail}")
    return out


def conformance_failures(doc: dict[str, Any]) -> list[str]:
    return [f"schema: {e}" for e in schema_errors(doc)] + [
        f"semantic: {v}" for v in semantic_violations(doc)
    ]


def unit_profile_failures(doc: dict[str, Any], profile: str) -> list[str]:
    """Validate every INLINE work unit against a work-unit profile."""
    validator = schemas.work_unit_validator(profile)
    out: list[str] = []
    for unit in inline_units(doc):
        errs = sorted(validator.iter_errors(unit), key=lambda e: list(e.absolute_path))
        for line in schemas.error_summary(errs, limit=3):
            out.append(f"{unit.get('id')}: {line}")
    return out


def sentinel_violations(doc: dict[str, Any]) -> list[str]:
    """Every inline unit's completion_sentinel must name that unit's own id.

    Closes the gap described in this module's docstring: ``SEM-002`` only runs over a catalog.
    """
    out: list[str] = []
    for unit in inline_units(doc):
        uid = str(unit.get("id"))
        sentinel = str(unit.get("completion_sentinel", ""))
        if f"SUCCESS:{uid}" not in sentinel:
            found = re.findall(r"SUCCESS:([A-Z]{2,4}-[0-9]{4})", sentinel)
            out.append(
                f"{uid}: sentinel names {found or 'no unit'} instead of its own id"
            )
    return out


# ------------------------------------------------------------- worked-example checking


def _type_ok(spec: dict[str, Any], value: Any) -> bool:
    kind = spec.get("type")
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind in {"string", "path", "unit_id", "workflow_ref", "secret_ref"}:
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, list)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "enum":
        return True  # membership is checked separately
    return True


def worked_example_failures(doc: dict[str, Any]) -> list[str]:
    """Cross-field rules over ``x_extensions.worked_example`` that no schema can express."""
    fails: list[str] = []
    ext = doc.get("x_extensions") or {}
    ex = ext.get("worked_example")
    if not isinstance(ex, dict):
        return ["worked_example is missing or not an object"]

    declared = doc.get("params") or {}
    bound = ex.get("params")
    if not isinstance(bound, dict):
        fails.append("worked_example.params is missing or not an object")
        bound = {}

    for name, spec in declared.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("required") is True and name not in bound:
            fails.append(f"required param {name!r} has no value in the worked example")

    for name, value in bound.items():
        spec = declared.get(name)
        if not isinstance(spec, dict):
            fails.append(f"worked example binds undeclared param {name!r}")
            continue
        if not _type_ok(spec, value):
            fails.append(
                f"param {name!r} declared {spec.get('type')!r} but example value is "
                f"{type(value).__name__}"
            )
            continue
        if spec.get("type") == "enum" and value not in (spec.get("enum") or []):
            fails.append(f"param {name!r} value {value!r} is outside its declared enum")
        if spec.get("type") == "array":
            item_spec = spec.get("items") or {}
            if item_spec.get("type") == "enum":
                for item in value:
                    if item not in (item_spec.get("enum") or []):
                        fails.append(
                            f"param {name!r} item {item!r} is outside the item enum"
                        )
            if spec.get("min_items") is not None and len(value) < spec["min_items"]:
                fails.append(f"param {name!r} has fewer items than min_items")
            if spec.get("max_items") is not None and len(value) > spec["max_items"]:
                fails.append(f"param {name!r} has more items than max_items")
        if isinstance(value, str):
            if spec.get("min_length") is not None and len(value) < spec["min_length"]:
                fails.append(f"param {name!r} is shorter than min_length")
            if spec.get("pattern") and not re.search(spec["pattern"], value):
                fails.append(f"param {name!r} does not match its declared pattern")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if spec.get("minimum") is not None and value < spec["minimum"]:
                fails.append(f"param {name!r} is below its declared minimum")
            if spec.get("maximum") is not None and value > spec["maximum"]:
                fails.append(f"param {name!r} is above its declared maximum")

    known = stage_ids(doc)
    path = ex.get("expected_stage_path")
    if not isinstance(path, list) or not path:
        fails.append("expected_stage_path is missing or empty")
        path = []
    for sid in path:
        if str(sid) not in known:
            fails.append(f"expected_stage_path names unknown stage {sid!r}")

    skipped = ex.get("skipped_stages") or []
    if not isinstance(skipped, list):
        fails.append("skipped_stages is not a list")
        skipped = []
    for sid in skipped:
        if str(sid) not in known:
            fails.append(f"skipped_stages names unknown stage {sid!r}")
        if str(sid) in {str(p) for p in path}:
            fails.append(f"stage {sid!r} is both walked and skipped")
    if skipped and not ex.get("skipped_because"):
        fails.append("skipped_stages declared without skipped_because")

    accounted = {str(p) for p in path} | {str(s) for s in skipped}
    for sid in top_level_stage_ids(doc):
        if sid not in accounted:
            fails.append(
                f"top-level stage {sid!r} is neither walked nor skipped in the worked example"
            )

    arts = ex.get("expected_artifacts")
    if not isinstance(arts, list) or not arts:
        fails.append("expected_artifacts is missing or empty")
        arts = []
    produced = declared_paths(doc)
    for art in arts:
        if str(art) not in produced:
            fails.append(
                f"expected artifact {art!r} is not declared by any stage or output"
            )

    terminal = str(ex.get("expected_terminal", ""))
    if not TERMINAL_RE.match(terminal):
        fails.append(f"expected_terminal {terminal!r} is not SUCCESS:<UNIT-ID>")
    else:
        want = terminal.split(":", 1)[1]
        if want not in {str(u.get("id")) for u in inline_units(doc)}:
            fails.append(
                f"expected_terminal names {want!r}, which is not an inline work unit here"
            )

    if not str(ex.get("narrative", "")).strip():
        fails.append("worked example has no narrative")
    return fails


# --------------------------------------------------------------------------- mutation


def mutated(
    doc: dict[str, Any], mutate: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    """Deep-copy ``doc``, apply ``mutate`` in place, return the mutant.

    Every both-states control in these tests goes through here, so a control can never
    accidentally assert against the pristine document.
    """
    clone = copy.deepcopy(doc)
    mutate(clone)
    if clone == doc:
        raise AssertionError("mutation was a no-op - the control would prove nothing")
    return clone


def drop_a_required_binding(doc: dict[str, Any]) -> None:
    """Mutator: remove the first required param binding from the worked example."""
    ex = doc["x_extensions"]["worked_example"]
    for name, spec in (doc.get("params") or {}).items():
        if (
            isinstance(spec, dict)
            and spec.get("required") is True
            and name in ex["params"]
        ):
            del ex["params"][name]
            return
    raise AssertionError("no required param binding to drop - control not applicable")


def contains_all(haystack: Iterable[str], needles: Iterable[str]) -> list[str]:
    """Return the needles that are absent - a helper that names what is missing, not just False."""
    have = set(haystack)
    return [n for n in needles if n not in have]
