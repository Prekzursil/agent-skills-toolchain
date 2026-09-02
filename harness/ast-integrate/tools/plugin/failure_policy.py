"""Fail-open versus fail-closed policy table per plugin component (IMP-0053).

The table (``failure_policy.json``) declares, per component, whether a failure
is *fail-open* (hooks and advisories must never block the user) or
*fail-closed* (validators, secret gates, signature checks deny on error),
records the rationale and the published rule each row encodes, and pins the
default to fail-closed.  ``fp_components.py`` is the enforcement half: one class
per row.  This module joins the two and enforces the declaration:

* :func:`inject_all` raises one fault *inside* every component and records what
  it did (``proceed``/``denied``/``degraded``);
* :func:`assert_injections_match_declarations` is the predicate: fail-open must
  proceed degraded, fail-closed must deny -- a mismatch raises
  :class:`PolicyViolation` naming the rows;
* :func:`audit_fail_closed_components` is the independent static signal: an AST
  walk over the fail-closed ``apply`` paths refusing any ``except`` that
  swallows the failure into a pass; :func:`both_states_auditor` proves the
  auditor fires on a planted swallow and stays silent on the real file;
* :func:`negative_control_flip_goes_red` flips one declaration in memory and
  shows the predicate goes red -- the test is not vacuous;
* :func:`independent_classification` re-derives each posture from ``kind``
  alone (never reading ``posture``) and reports disagreements instead of
  adopting the table;
* :func:`hooks_config_syntax_error` shows the hook component fail-open on an
  unparseable hooks config (the AGENTS.md#6 case).

Flipping a row is owner-gated (``owner_lock``); nothing here changes a posture,
it only checks that the code does what the table says.
"""
from __future__ import annotations

import ast
import copy
import json
import re
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TABLE_PATH = HERE / "failure_policy.json"
SCHEMA_PATH = HERE / "schema" / "failure-policy.schema.json"
COMPONENTS_PATH = HERE / "fp_components.py"

FAIL_OPEN = "fail-open"
FAIL_CLOSED = "fail-closed"
PROCEED = "proceed"
DENY = "deny"
INJECTED_FAULT = "IMP-0053-injected-fault"

# kind -> posture, the published rule restated without reading the table.
KIND_POSTURE: dict[str, str] = {
    "hook": FAIL_OPEN,
    "advisory": FAIL_OPEN,
    "warning-channel": FAIL_OPEN,
    "heartbeat": FAIL_OPEN,
    "validator": FAIL_CLOSED,
    "secret-gate": FAIL_CLOSED,
    "signature": FAIL_CLOSED,
    "allowlist": FAIL_CLOSED,
    "content-gate": FAIL_CLOSED,
    "permission": FAIL_CLOSED,
    "rollback": FAIL_CLOSED,
}


def _components():
    """Import the enforcement module whether or not tools/plugin is on sys.path."""
    try:
        import fp_components  # type: ignore

        return fp_components
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location("fp_components", COMPONENTS_PATH)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class PolicyViolation(AssertionError):
    """Injection outcomes disagree with the declared postures."""

    def __init__(self, mismatches: list[dict[str, Any]]) -> None:
        self.mismatches = mismatches
        super().__init__(f"{len(mismatches)} component(s) violate the declared posture: {mismatches}")


class TableInvalid(ValueError):
    """The policy table does not satisfy failure-policy.schema.json."""


@dataclass(frozen=True)
class Spec:
    id: str
    kind: str
    posture: str
    on_failure: str
    rationale: str
    source_rule: str


# --- table -------------------------------------------------------------------


def _validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Stdlib validator for the schema subset failure-policy.schema.json uses."""
    errs: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum")
    typ = schema.get("type")
    if typ is not None:
        ok = {
            "object": isinstance(instance, dict),
            "array": isinstance(instance, list),
            "string": isinstance(instance, str),
            "integer": isinstance(instance, int) and not isinstance(instance, bool),
            "boolean": isinstance(instance, bool),
        }.get(typ, True)
        if not ok:
            return errs + [f"{path}: expected {typ}"]
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: does not match {schema['pattern']!r}")
    if isinstance(instance, int) and not isinstance(instance, bool) and "minimum" in schema:
        if instance < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errs.append(f"{path}: missing required {key!r}")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                errs.extend(_validate(instance[key], sub, f"{path}.{key}"))
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errs.append(f"{path}: additional property {key!r}")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if schema.get("uniqueItems"):
            seen = [json.dumps(x, sort_keys=True) for x in instance]
            if len(set(seen)) != len(seen):
                errs.append(f"{path}: items are not unique")
        if "items" in schema:
            for i, item in enumerate(instance):
                errs.extend(_validate(item, schema["items"], f"{path}[{i}]"))
    if "oneOf" in schema:
        hits = [alt for alt in schema["oneOf"] if not _validate(instance, alt, path)]
        if len(hits) != 1:
            errs.append(f"{path}: matched {len(hits)} of oneOf, need exactly 1")
    return errs


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_table(table: dict[str, Any]) -> list[str]:
    """Schema errors plus the cross-row checks the schema cannot express."""
    errs = _validate(table, load_schema())
    rows = table.get("components") if isinstance(table, dict) else None
    if isinstance(rows, list):
        ids = [r.get("id") for r in rows if isinstance(r, dict)]
        if len(set(ids)) != len(ids):
            errs.append("$.components: duplicate component ids")
        for r in rows:
            if isinstance(r, dict) and r.get("kind") in KIND_POSTURE:
                if KIND_POSTURE[r["kind"]] != r.get("posture"):
                    errs.append(
                        f"$.components[{r.get('id')}]: kind {r['kind']!r} is published as "
                        f"{KIND_POSTURE[r['kind']]}, row says {r.get('posture')!r}"
                    )
    return errs


def load_table(path: Path | None = None) -> dict[str, Any]:
    """Read and validate the policy table; an invalid table is refused (fail-closed)."""
    table = json.loads(Path(path or TABLE_PATH).read_text(encoding="utf-8"))
    errs = validate_table(table)
    if errs:
        raise TableInvalid("; ".join(errs))
    return table


def specs_from_table(table: dict[str, Any]) -> dict[str, Spec]:
    return {
        row["id"]: Spec(
            id=row["id"],
            kind=row["kind"],
            posture=row["posture"],
            on_failure=row["on_failure"],
            rationale=row["rationale"],
            source_rule=row["source_rule"],
        )
        for row in table["components"]
    }


# --- injection ---------------------------------------------------------------


def component_for(cid: str):
    fp = _components()
    try:
        cls = fp.REGISTRY[cid]
    except KeyError as exc:
        raise LookupError(f"no enforcement component registered for row {cid!r}") from exc
    return cls()


def inject_one(cid: str, ctx: Any = None, fault: BaseException | None = None):
    """Raise ``fault`` inside component ``cid`` and return its Outcome."""
    fp = _components()
    ctx = ctx if ctx is not None else fp.Context()
    fault = fault if fault is not None else RuntimeError(INJECTED_FAULT)
    return component_for(cid).apply(ctx, fault=fault)


def inject_all(table: dict[str, Any], ctx: Any = None) -> dict[str, Any]:
    """Exactly one injection per declared component."""
    fp = _components()
    ctx = ctx if ctx is not None else fp.Context()
    outcomes: dict[str, Any] = {}
    for row in table["components"]:
        outcomes[row["id"]] = inject_one(row["id"], ctx, RuntimeError(INJECTED_FAULT))
    return outcomes


def mismatches(outcomes: dict[str, Any], table: dict[str, Any]) -> list[dict[str, Any]]:
    specs = specs_from_table(table)
    out: list[dict[str, Any]] = []
    for cid in sorted(set(specs) | set(outcomes)):
        spec = specs.get(cid)
        got = outcomes.get(cid)
        if spec is None or got is None:
            out.append({"id": cid, "reason": "declared without injection" if got is None else "injected without declaration"})
            continue
        if not got.failure:
            out.append({"id": cid, "reason": "fault was not observed", "outcome": asdict(got)})
        elif spec.posture == FAIL_OPEN and not (got.proceed and not got.denied and got.degraded):
            out.append({"id": cid, "declared": FAIL_OPEN, "outcome": asdict(got)})
        elif spec.posture == FAIL_CLOSED and not (got.denied and not got.proceed):
            out.append({"id": cid, "declared": FAIL_CLOSED, "outcome": asdict(got)})
    return out


def assert_injections_match_declarations(outcomes: dict[str, Any], table: dict[str, Any]) -> None:
    bad = mismatches(outcomes, table)
    if bad:
        raise PolicyViolation(bad)


# --- static audit ------------------------------------------------------------


def _class_map(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}


def _resolve_apply(name: str, classes: dict[str, ast.ClassDef], seen: set[str] | None = None) -> ast.FunctionDef | None:
    seen = seen or set()
    if name in seen or name not in classes:
        return None
    seen.add(name)
    cls = classes[name]
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == "apply":
            return node
    for base in cls.bases:
        base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        found = _resolve_apply(base_name, classes, seen)
        if found is not None:
            return found
    return None


def _handler_swallows(handler: ast.ExceptHandler) -> str:
    """Return a finding string when the handler turns a failure into a pass."""
    body = handler.body
    if not body:
        return "empty handler"
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            return "except ...: pass"
        if isinstance(stmt, ast.Continue):
            return "except ...: continue"
        if isinstance(stmt, ast.Return):
            value = stmt.value
            if value is None or (isinstance(value, ast.Constant) and value.value in (None, True)):
                return "returns None/True from except"
            if isinstance(value, ast.Call):
                fn = value.func
                attr = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if attr in {"ok", "degrade"}:
                    return f"returns self.{attr}() from except"
                if attr == "Outcome":
                    kw = {k.arg: k.value for k in value.keywords}
                    proceed = kw.get("proceed")
                    denied = kw.get("denied")
                    if (isinstance(proceed, ast.Constant) and proceed.value is True) or (
                        isinstance(denied, ast.Constant) and denied.value is False
                    ):
                        return "returns a proceeding Outcome from except"
    last = body[-1]
    if isinstance(last, (ast.Raise, ast.Return)):
        return ""
    return "handler falls through to the success path"


def audit_source(source: str, fail_closed_classes: dict[str, str]) -> dict[str, Any]:
    """AST audit of ``source``: every fail-closed class must have an apply whose
    except handlers all deny or re-raise.  ``fail_closed_classes`` maps row id ->
    class name."""
    tree = ast.parse(source)
    classes = _class_map(tree)
    findings: list[dict[str, Any]] = []
    missing_apply: list[str] = []
    for cid, cls_name in sorted(fail_closed_classes.items()):
        apply = _resolve_apply(cls_name, classes)
        if apply is None:
            missing_apply.append(cid)
            continue
        for node in ast.walk(apply):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    why = _handler_swallows(handler)
                    if why:
                        findings.append({"id": cid, "class": cls_name, "line": handler.lineno, "finding": why})
    return {
        "clean": not findings and not missing_apply,
        "fail_closed_ids": sorted(fail_closed_classes),
        "findings": findings,
        "missing_apply": missing_apply,
    }


def _fail_closed_classes(table: dict[str, Any]) -> dict[str, str]:
    fp = _components()
    return {
        row["id"]: fp.REGISTRY[row["id"]].__name__
        for row in table["components"]
        if row["posture"] == FAIL_CLOSED and row["id"] in fp.REGISTRY
    }


def audit_fail_closed_components(table: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = Path(path or COMPONENTS_PATH)
    report = audit_source(path.read_text(encoding="utf-8"), _fail_closed_classes(table))
    declared = [r["id"] for r in table["components"] if r["posture"] == FAIL_CLOSED]
    unregistered = [cid for cid in declared if cid not in report["fail_closed_ids"]]
    if unregistered:
        report["missing_apply"] = sorted(set(report["missing_apply"]) | set(unregistered))
        report["clean"] = False
    report["path"] = path.name
    return report


PLANTED_SWALLOW = '''
class Outcome: pass
class PlantedGate:
    def apply(self, ctx, fault=None):
        try:
            self.check(ctx, fault)
        except Exception:
            pass
        return Outcome()
'''


def both_states_auditor(table: dict[str, Any] | None = None) -> dict[str, Any]:
    """The auditor must fire on a planted swallow and stay silent on the real file."""
    table = table or load_table()
    real = audit_fail_closed_components(table)
    planted = audit_source(PLANTED_SWALLOW, {"planted_gate": "PlantedGate"})
    return {
        "both_states": bool(real["clean"]) and not planted["clean"] and bool(planted["findings"]),
        "silent_on_real": real["clean"],
        "fired_on_planted": bool(planted["findings"]),
        "planted_findings": planted["findings"],
        "real_findings": real["findings"],
    }


# --- controls and reviewer ---------------------------------------------------


def negative_control_flip_goes_red(cid: str, table: dict[str, Any]) -> dict[str, Any]:
    """Flip one row in memory; the unchanged code must now violate the table."""
    outcomes = inject_all(table)
    green_before = not mismatches(outcomes, table)
    flipped = copy.deepcopy(table)
    row = next(r for r in flipped["components"] if r["id"] == cid)
    original = row["posture"]
    row["posture"] = FAIL_CLOSED if original == FAIL_OPEN else FAIL_OPEN
    row["on_failure"] = DENY if row["posture"] == FAIL_CLOSED else PROCEED
    went_red = False
    detail: list[dict[str, Any]] = []
    try:
        assert_injections_match_declarations(outcomes, flipped)
    except PolicyViolation as exc:
        went_red = any(m.get("id") == cid for m in exc.mismatches)
        detail = exc.mismatches
    return {
        "component": cid,
        "flipped_from": original,
        "flipped_to": row["posture"],
        "green_before_flip": green_before,
        "went_red": went_red and green_before,
        "mismatches": detail,
    }


def classify_by_kind(rows: list[tuple[str, str]]) -> dict[str, str]:
    """Posture from kind only.  Unknown kinds default to fail-closed."""
    return {cid: KIND_POSTURE.get(kind, FAIL_CLOSED) for cid, kind in rows}


def independent_classification(table: dict[str, Any]) -> dict[str, Any]:
    rows = [(r["id"], r["kind"]) for r in table["components"]]
    derived = classify_by_kind(rows)
    declared = {r["id"]: r["posture"] for r in table["components"]}
    disagreements = [
        {"id": cid, "from_kind": derived[cid], "declared": declared[cid]}
        for cid in derived
        if derived[cid] != declared[cid]
    ]
    return {
        "reviewer_id": "imp-0053-kind-classifier",
        "independent": True,
        "reads_posture_field": False,
        "classified": derived,
        "disagreements": disagreements,
        "verdict": "PASS" if not disagreements else "FAIL",
    }


def hooks_config_syntax_error(bad_text: str = "{bad json}"):
    """A hooks config that does not parse must be fail-open: proceed, degraded."""
    fp = _components()
    with tempfile.TemporaryDirectory(prefix="imp0053-hooks-") as td:
        cfg = Path(td) / "hooks.json"
        cfg.write_text(bad_text, encoding="utf-8")
        ctx = fp.Context(hooks_config=cfg)
        return component_for("hooks").apply(ctx)


# --- suite -------------------------------------------------------------------


def run_suite(table: dict[str, Any] | None = None) -> dict[str, Any]:
    table = table or load_table()
    outcomes = inject_all(table)
    bad = mismatches(outcomes, table)
    control = negative_control_flip_goes_red("hooks", table)
    both = both_states_auditor(table)
    review = independent_classification(table)
    syntax = hooks_config_syntax_error()
    audit = audit_fail_closed_components(table)
    ok = (
        not bad
        and control["went_red"]
        and both["both_states"]
        and review["verdict"] == "PASS"
        and audit["clean"]
        and syntax.proceed
        and syntax.failure
        and syntax.degraded
        and not syntax.denied
    )
    return {
        "ok": ok,
        "injections": {cid: asdict(o) for cid, o in outcomes.items()},
        "mismatches": bad,
        "negative_control": control,
        "auditor_both_states": both,
        "reviewer": review,
        "hooks_syntax_error": asdict(syntax),
        "static_audit": audit,
    }


def main(argv: list[str] | None = None) -> int:
    suite = run_suite()
    print(json.dumps({k: v for k, v in suite.items() if k != "injections"}, indent=2, sort_keys=True))
    print("SUCCESS:failure-policy suite" if suite["ok"] else "FAILED:failure-policy suite")
    return 0 if suite["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
