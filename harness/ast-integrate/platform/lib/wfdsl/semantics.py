"""Cross-field and referential rules that JSON Schema structurally cannot express.

JSON Schema validates one value against one schema. It cannot say "this sentinel must name
THIS unit's id", "this dependency token must match some OTHER unit's id", or "the stage graph
must be acyclic". Asserting those in a schema is impossible; asserting them nowhere is how a
catalog acquires 41 dependency references that point at nothing. They live here, each with a
stable rule id so a report can cite one.

Every rule returns a :class:`RuleResult`; ``violations`` is a list of ``(subject, detail)``
pairs so a caller can print a bounded sample without losing the count.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from . import expr as _expr

UNIT_ID_RE = re.compile(r"^[A-Z]{2,4}-[0-9]{4}$")
BUCKET_RE = re.compile(r"^B[0-9]{2}$")

#: ``Write(command-center/research/**)`` -> identity ``Write``, scope ``command-center/research/**``
_TOOL_TOKEN_RE = re.compile(
    r"^(?P<identity>[^(]*?)\s*(?:\((?P<scope>.*)\))?\s*$", re.DOTALL
)
#: the server segment forbids ``_`` so two comma-packed ids cannot match as one server
_MCP_TOKEN_RE = re.compile(r"^mcp__(?P<server>[a-z0-9][a-z0-9.\-]*)__(?P<method>.+)$")

#: harness tools that only exist inside an attached interactive session. A remote batch
#: runner has no session to spawn a subagent into, no owner to ask, and no local shell to
#: monitor, so a remote unit holding one of these declares a capability it cannot be given.
SESSION_LOCAL_TOOLS: frozenset[str] = frozenset({"Task", "AskUserQuestion", "Monitor"})

#: the four ``execution_substrate`` values that run away from the interactive session
REMOTE_SUBSTRATES: frozenset[str] = frozenset(
    {"cloud-batch", "databricks-job", "modal-sandbox", "container"}
)

#: approval floor that a ``tool_policy`` cannot loosen. ``Task`` spawns subagents that act
#: with the unit's own permissions and spend the owner's quota; an identity wildcard grants
#: every present and FUTURE tool of a server, which no reviewer can have inspected.
#: ``tool_policy.require_owner_approval`` may only ADD to this set (SEM-009).
APPROVAL_FLOOR_TOOLS: frozenset[str] = frozenset({"Task"})

#: phases sort as (number, letter) so 2 < 2A < 2B < 7 < 7A < 10
_PHASE_RE = re.compile(r"^(\d+)([A-Z]?)$")


@dataclass
class RuleResult:
    rule: str
    description: str
    severity: str  # "violation" | "advisory"
    violations: list[tuple[str, str]] = field(default_factory=list)
    checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.violations

    def to_json(self, sample: int = 12) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "description": self.description,
            "severity": self.severity,
            "checked": self.checked,
            "violations": len(self.violations),
            "sample": [
                {"subject": s, "detail": d} for s, d in self.violations[:sample]
            ],
        }


def phase_sort_key(phase: str) -> tuple[int, str]:
    m = _PHASE_RE.match(str(phase))
    if not m:
        return (10**6, str(phase))
    return (int(m.group(1)), m.group(2))


# ------------------------------------------------------------------ work units / catalog


def check_work_units(
    units: Sequence[Mapping[str, Any]],
    tool_policy: Mapping[str, Any] | None = None,
) -> list[RuleResult]:
    """Run SEM-001..SEM-011 over a work-unit collection.

    SEM-001..007 are referential/graph rules and need only the units. SEM-008..011 are the
    AUTHORIZATION plane and additionally consume the catalog-level ``tool_policy``; passing
    ``None`` makes SEM-008 fail closed (see :func:`check_work_unit_authorization`).
    """
    ids = {u.get("id") for u in units}

    r1 = RuleResult(
        "SEM-001",
        "every dependency token resolves to a known unit id or a bucket id (Bnn)",
        "violation",
        checked=len(units),
    )
    for u in units:
        bad = [
            t
            for t in _as_list(u.get("dependencies"))
            if t not in ids and not BUCKET_RE.match(str(t))
        ]
        if bad:
            r1.violations.append(
                (str(u.get("id")), "unresolvable: " + ", ".join(map(str, bad)))
            )

    r2 = RuleResult(
        "SEM-002",
        "completion_sentinel names the unit's own id (AGENTS.md 4 terminal state)",
        "violation",
        checked=len(units),
    )
    for u in units:
        sentinel = str(u.get("completion_sentinel", ""))
        if f"SUCCESS:{u.get('id')}" not in sentinel:
            found = re.findall(r"SUCCESS:([A-Z]{2,4}-[0-9]{4})", sentinel)
            detail = (
                f"sentinel names a DIFFERENT unit id {found}"
                if found
                else "sentinel carries no SUCCESS:<unit-id> marker"
            )
            r2.violations.append((str(u.get("id")), detail))

    r3 = RuleResult("SEM-003", "unit ids are unique", "violation", checked=len(units))
    seen: dict[str, int] = {}
    for u in units:
        uid = str(u.get("id"))
        seen[uid] = seen.get(uid, 0) + 1
    for uid, count in seen.items():
        if count > 1:
            r3.violations.append((uid, f"appears {count} times"))

    r4 = RuleResult(
        "SEM-004",
        "output_path is unique across units (two units writing one path race and lose work)",
        "violation",
        checked=len(units),
    )
    paths: dict[str, list[str]] = {}
    for u in units:
        paths.setdefault(str(u.get("output_path")), []).append(str(u.get("id")))
    for path, owners in paths.items():
        if len(owners) > 1:
            r4.violations.append((path, "claimed by " + ", ".join(sorted(owners))))

    r5 = RuleResult(
        "SEM-005", "no unit depends on itself", "violation", checked=len(units)
    )
    for u in units:
        if u.get("id") in _as_list(u.get("dependencies")):
            r5.violations.append((str(u.get("id")), "self-dependency"))

    r6 = RuleResult(
        "SEM-006",
        "the unit dependency graph is acyclic",
        "violation",
        checked=len(units),
    )
    for cycle in find_cycles(
        {
            str(u.get("id")): [t for t in _as_list(u.get("dependencies")) if t in ids]
            for u in units
        }
    ):
        r6.violations.append((" -> ".join(cycle), "cycle"))

    r7 = RuleResult(
        "SEM-007",
        "a dependency does not point at a LATER phase (advisory: a later-phase dependency cannot be satisfied in phase order)",
        "advisory",
        checked=len(units),
    )
    phase_of = {str(u.get("id")): str(u.get("phase")) for u in units}
    for u in units:
        mine = phase_sort_key(str(u.get("phase")))
        late = [
            t
            for t in _as_list(u.get("dependencies"))
            if t in phase_of and phase_sort_key(phase_of[t]) > mine
        ]
        if late:
            r7.violations.append(
                (
                    str(u.get("id")),
                    f"phase {u.get('phase')} depends on later "
                    + ", ".join(f"{t}@{phase_of[t]}" for t in late[:6]),
                )
            )

    return [r1, r2, r3, r4, r5, r6, r7] + check_work_unit_authorization(
        units, tool_policy
    )


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ------------------------------------------------ work-unit authorization (SEM-008..011)


@dataclass(frozen=True)
class ToolToken:
    """One parsed ``tool_permissions`` entry.

    The corpus carries four surface forms and they must not be conflated::

        Read                                  identity=Read          base=Read
        Bash:python                           identity=Bash:python   base=Bash
        Write(command-center/research/**)      identity=Write         base=Write   scope=...**
        mcp__search-hub__*                     identity=mcp__...__*   server=search-hub

    ``scope`` is a NARROWING (a path glob restricting where Write may write); an ``identity``
    wildcard is a BROADENING (every tool of a server, including ones not yet written). A rule
    that treats the two alike punishes least privilege - measured: 111 of the catalog's 120
    "wildcard" units carry only a scope glob.
    """

    raw: str
    identity: str
    scope: str
    base: str
    server: str
    method: str

    @property
    def is_mcp(self) -> bool:
        return self.identity.startswith("mcp__")

    @property
    def identity_wildcard(self) -> bool:
        return "*" in self.identity

    @property
    def scope_wildcard(self) -> bool:
        return "*" in self.scope


def parse_tool_token(raw: Any) -> ToolToken:
    """Split a tool token into identity / scope / base / mcp server+method."""
    text = str(raw)
    m = _TOOL_TOKEN_RE.match(text)
    identity = (m.group("identity") or "").strip() if m else text.strip()
    scope = (m.group("scope") or "") if m else ""
    base = identity.split(":", 1)[0]
    server = method = ""
    if identity.startswith("mcp__"):
        mm = _MCP_TOKEN_RE.match(identity)
        if mm:
            server, method = mm.group("server"), mm.group("method")
    return ToolToken(
        raw=text,
        identity=identity,
        scope=scope,
        base=base,
        server=server,
        method=method,
    )


def policy_entry_permits(entry: Any, tok: ToolToken) -> bool:
    """Does one ``tool_policy`` allow/deny/require entry cover this token?

    Family semantics, deliberately narrow:

    * exact identity equality (``Read`` covers ``Read``);
    * a bare native base covers its sub-shell and path-scoped narrowings (``Bash`` covers
      ``Bash:python`` and ``Bash(pytest)``, because both are LESS than the base grant);
    * ``mcp__<server>__*`` covers every tool of that server.

    It deliberately does NOT work the other way: a specific entry never covers a wildcard
    token, so an allowlist of specific tools cannot be satisfied by ``mcp__srv__*``.

    A POLICY entry that carries its own ``( )`` scope matches only by exact string. Without
    that guard, writing ``Write(reports/**)`` in the allowlist would still permit a bare
    ``Write`` (identical identity, no scope comparison) - an author would believe they had
    restricted writes while every unscoped grant sailed through. Path-scope enforcement
    belongs in ``tool_policy.write_paths``, which is a separate field with real semantics.
    """
    e = parse_tool_token(entry)
    if e.raw.strip() == tok.raw.strip():
        return True
    if e.scope:
        return False
    if e.identity == tok.identity:
        return True
    if e.is_mcp:
        return bool(
            e.method == "*" and tok.is_mcp and tok.server == e.server and e.server
        )
    if tok.is_mcp:
        return False
    return bool(e.identity and e.identity == e.base and e.identity == tok.base)


def _covered_by(entries: Iterable[Any], tok: ToolToken) -> bool:
    return any(policy_entry_permits(e, tok) for e in entries or [])


def _fmt(tokens: Sequence[ToolToken], limit: int = 4) -> str:
    shown = ", ".join(repr(t.raw) for t in tokens[:limit])
    extra = f" (+{len(tokens) - limit} more)" if len(tokens) > limit else ""
    return shown + extra


def check_work_unit_authorization(
    units: Sequence[Mapping[str, Any]],
    tool_policy: Mapping[str, Any] | None = None,
) -> list[RuleResult]:
    """Run SEM-008..SEM-011: the authorization plane of the work-unit contract.

    ``tool_policy`` is the SAME document shape as
    ``workflow-dsl.schema.json#/$defs/tool_policy`` (deny by default, ``allow`` /
    ``deny`` / ``require_owner_approval``). It is read from the catalog root - there is
    deliberately no second policy file, because two authorization planes disagree.

    With no policy at all SEM-008 fails CLOSED: every unit that requests a tool is a
    violation. "No policy found" must never read as "nothing to check".
    """
    policy: Mapping[str, Any] = tool_policy or {}
    has_policy = bool(policy)
    default_deny = str(policy.get("default", "deny")) == "deny"
    allow = _as_list(policy.get("allow"))
    deny = _as_list(policy.get("deny"))
    require_approval = _as_list(policy.get("require_owner_approval"))

    r8 = RuleResult(
        "SEM-008",
        "every tool a unit requests is permitted by the catalog tool_policy (deny by default)",
        "violation",
    )
    r9 = RuleResult(
        "SEM-009",
        "a unit holding an approval-gated tool declares owner_approval_required: true",
        "violation",
    )
    r10 = RuleResult(
        "SEM-010",
        "tool_permissions do not exceed the declared execution_substrate "
        "(a remote substrate cannot honour a session-local tool)",
        "violation",
    )
    r11 = RuleResult(
        "SEM-011",
        "an mcp__ token names one specific server AND one specific tool (no wildcard identity)",
        "violation",
    )

    for u in units:
        uid = str(u.get("id"))
        tokens = [parse_tool_token(t) for t in _as_list(u.get("tool_permissions"))]
        substrate = str(u.get("execution_substrate"))
        approved = u.get("owner_approval_required") is True

        # --- SEM-008 deny by default -------------------------------------------------
        if tokens:
            r8.checked += 1
            if not has_policy:
                r8.violations.append(
                    (
                        uid,
                        f"no tool_policy declared for this catalog, so all {len(tokens)} "
                        "requested tools are denied by default: " + _fmt(tokens),
                    )
                )
            else:
                denied = [t for t in tokens if _covered_by(deny, t)]
                unlisted = (
                    [t for t in tokens if t not in denied and not _covered_by(allow, t)]
                    if default_deny
                    else []
                )
                if denied:
                    r8.violations.append(
                        (uid, "explicitly denied by tool_policy.deny: " + _fmt(denied))
                    )
                if unlisted:
                    r8.violations.append(
                        (
                            uid,
                            "not in tool_policy.allow and the policy default is deny: "
                            + _fmt(unlisted),
                        )
                    )

        # --- SEM-009 approval coherence ----------------------------------------------
        gated_floor = [t for t in tokens if t.base in APPROVAL_FLOOR_TOOLS]
        gated_wild = [t for t in tokens if t.identity_wildcard]
        gated_policy = [
            t
            for t in tokens
            if _covered_by(require_approval, t)
            and t not in gated_floor
            and t not in gated_wild
        ]
        if gated_floor or gated_wild or gated_policy:
            r9.checked += 1
            if not approved:
                why = []
                if gated_floor:
                    why.append(f"approval-floor tool {_fmt(gated_floor)}")
                if gated_wild:
                    why.append(f"identity-wildcard grant {_fmt(gated_wild)}")
                if gated_policy:
                    why.append(
                        f"tool_policy.require_owner_approval {_fmt(gated_policy)}"
                    )
                r9.violations.append(
                    (
                        uid,
                        "owner_approval_required="
                        f"{u.get('owner_approval_required')!r} but holds "
                        + "; ".join(why),
                    )
                )

        # --- SEM-010 substrate coherence ---------------------------------------------
        if substrate in REMOTE_SUBSTRATES:
            r10.checked += 1
            local_only = [t for t in tokens if t.base in SESSION_LOCAL_TOOLS]
            if local_only:
                r10.violations.append(
                    (
                        uid,
                        f"execution_substrate={substrate!r} is remote but the unit holds "
                        "session-local " + _fmt(local_only),
                    )
                )

        # --- SEM-011 mcp token specificity -------------------------------------------
        for t in tokens:
            if not t.is_mcp:
                continue
            r11.checked += 1
            if not t.server or not t.method:
                r11.violations.append(
                    (
                        uid,
                        f"{t.raw!r} does not parse as mcp__<server>__<tool>",
                    )
                )
            elif "*" in t.method or "*" in t.server:
                r11.violations.append(
                    (
                        uid,
                        f"{t.raw!r} wildcards the {'server' if '*' in t.server else 'tool'} "
                        "segment; name every tool the unit actually needs",
                    )
                )

    return [r8, r9, r10, r11]


def find_cycles(graph: Mapping[str, Iterable[str]], limit: int = 10) -> list[list[str]]:
    """Iterative DFS cycle finder (no recursion limit risk on a 2k-node graph)."""
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    cycles: list[list[str]] = []
    for start in graph:
        if color[start] != WHITE:
            continue
        color[start] = GREY
        path = [start]
        stack: list[tuple[str, Any]] = [(start, iter(graph[start]))]
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                state = color.get(nxt, BLACK)
                if state == GREY:
                    if len(cycles) < limit and nxt in path:
                        cycles.append(path[path.index(nxt) :] + [nxt])
                elif state == WHITE:
                    color[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, iter(graph[nxt])))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
                if path:
                    path.pop()
    return cycles


# ---------------------------------------------------------------------------- workflows


def iter_stages(workflow: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """Every stage in the document, depth-first, paired with its JSON-pointer-ish path."""
    out: list[tuple[str, Mapping[str, Any]]] = []

    def walk(stages: Any, prefix: str) -> None:
        if not isinstance(stages, list):
            return
        for i, st in enumerate(stages):
            if not isinstance(st, Mapping):
                continue
            here = f"{prefix}/{i}"
            out.append((here, st))
            for key in ("body",):
                if isinstance(st.get(key), list):
                    walk(st[key], f"{here}/{key}")
            for key in ("diagnose", "repair", "verify"):
                sub = st.get(key)
                if isinstance(sub, Mapping):
                    out.append((f"{here}/{key}", sub))
                    if isinstance(sub.get("body"), list):
                        walk(sub["body"], f"{here}/{key}/body")

    walk(workflow.get("stages"), "/stages")
    return out


def _collect_expressions(workflow: Mapping[str, Any]) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                if k in {
                    "when",
                    "expression",
                    "converged_when",
                    "minimum_conditions",
                } and (isinstance(v, str) or isinstance(v, Mapping)):
                    found.append((f"{path}/{k}", v))
                visit(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                visit(v, f"{path}/{i}")

    visit(workflow, "")
    return found


def check_workflow(workflow: Mapping[str, Any]) -> list[RuleResult]:
    """Run DSL-SEM-001..DSL-SEM-014 over one workflow document."""
    stages = iter_stages(workflow)
    wf_id = str(workflow.get("id", "<unnamed>"))
    results: list[RuleResult] = []

    r1 = RuleResult(
        "DSL-SEM-001",
        "stage ids are unique across the whole document",
        "violation",
        checked=len(stages),
    )
    counts: dict[str, list[str]] = {}
    for path, st in stages:
        counts.setdefault(str(st.get("id")), []).append(path)
    for sid, where in counts.items():
        if len(where) > 1:
            r1.violations.append((sid, "declared at " + ", ".join(where)))
    results.append(r1)

    # depends_on must resolve within the same sibling list (a stage cannot wait on a stage
    # inside another stage's body - that body may never run).
    r2 = RuleResult(
        "DSL-SEM-002",
        "every depends_on target exists in the same stage list",
        "violation",
    )

    def check_scope(stage_list: Any, scope: str) -> None:
        if not isinstance(stage_list, list):
            return
        local = {str(s.get("id")) for s in stage_list if isinstance(s, Mapping)}
        for s in stage_list:
            if not isinstance(s, Mapping):
                continue
            r2.checked += 1
            for dep in s.get("depends_on", []) or []:
                if str(dep) not in local:
                    r2.violations.append(
                        (
                            f"{scope}:{s.get('id')}",
                            f"depends_on {dep!r} not in this scope {sorted(local)}",
                        )
                    )
            for key in ("body",):
                if isinstance(s.get(key), list):
                    check_scope(s[key], f"{scope}/{s.get('id')}/{key}")

    check_scope(workflow.get("stages"), "/stages")
    results.append(r2)

    r3 = RuleResult(
        "DSL-SEM-003", "the stage graph is acyclic in every scope", "violation"
    )

    def check_acyclic(stage_list: Any, scope: str) -> None:
        if not isinstance(stage_list, list):
            return
        graph = {
            str(s.get("id")): [
                str(d) for d in (s.get("depends_on") or []) if isinstance(s, Mapping)
            ]
            for s in stage_list
            if isinstance(s, Mapping)
        }
        r3.checked += len(graph)
        for cycle in find_cycles(
            {k: [d for d in v if d in graph] for k, v in graph.items()}
        ):
            r3.violations.append((scope, " -> ".join(cycle)))
        for s in stage_list:
            if isinstance(s, Mapping) and isinstance(s.get("body"), list):
                check_acyclic(s["body"], f"{scope}/{s.get('id')}/body")

    check_acyclic(workflow.get("stages"), "/stages")
    results.append(r3)

    declared_roles = set(workflow.get("roles", {}) or {})
    r4 = RuleResult(
        "DSL-SEM-004",
        "every stage role reference resolves to a declared role",
        "violation",
    )
    for path, st in stages:
        if "role" in st:
            r4.checked += 1
            if str(st["role"]) not in declared_roles:
                r4.violations.append(
                    (path, f"role {st['role']!r} not in roles {sorted(declared_roles)}")
                )
    results.append(r4)

    declared_gates = set(workflow.get("gates", {}) or {})
    r5 = RuleResult(
        "DSL-SEM-005", "every gate_ref resolves to a declared gate", "violation"
    )
    for path, st in stages:
        if "gate_ref" in st:
            r5.checked += 1
            if str(st["gate_ref"]) not in declared_gates:
                r5.violations.append(
                    (
                        path,
                        f"gate_ref {st['gate_ref']!r} not in gates {sorted(declared_gates)}",
                    )
                )
    results.append(r5)

    declared_sub = set(workflow.get("subworkflows", {}) or {})
    r6 = RuleResult(
        "DSL-SEM-006",
        "a subworkflow reference resolves to a declared subworkflow",
        "violation",
    )
    for path, st in stages:
        wf = st.get("workflow")
        if isinstance(wf, Mapping) and "workflow_id" in wf:
            r6.checked += 1
            if str(wf["workflow_id"]) not in declared_sub:
                r6.violations.append(
                    (
                        path,
                        f"workflow_id {wf['workflow_id']!r} not in subworkflows {sorted(declared_sub)}",
                    )
                )
    results.append(r6)

    r7 = RuleResult(
        "DSL-SEM-007",
        "every expression parses (a rule that cannot parse can never fire)",
        "violation",
    )
    for path, e in _collect_expressions(workflow):
        r7.checked += 1
        try:
            _expr.to_ast(e)
        except _expr.ExpressionError as exc:
            r7.violations.append((path, str(exc)))
    results.append(r7)

    r8 = RuleResult(
        "DSL-SEM-008",
        "a loop convergence expression only references declared metrics, loop_var, or params",
        "violation",
    )
    known_params = set(workflow.get("params", {}) or {})
    for path, st in stages:
        conv = st.get("convergence")
        if not isinstance(conv, Mapping):
            continue
        rule = conv.get("converged_when")
        if rule is None:
            continue
        r8.checked += 1
        metric_names = {
            str(m.get("name"))
            for m in conv.get("metrics", []) or []
            if isinstance(m, Mapping)
        }
        allowed = (
            metric_names
            | known_params
            | {str(st.get("loop_var"))}
            | {
                "iteration",
                "iterations",
                "no_progress_rounds",
                "max_iterations",
                "elapsed_seconds",
            }
        )
        try:
            used = _expr.identifiers(rule)
        except _expr.ExpressionError:
            continue  # already reported by DSL-SEM-007
        unknown = sorted(i for i in used if i not in allowed)
        if unknown:
            r8.violations.append(
                (
                    path,
                    f"convergence references undeclared metric(s) {unknown}; declared {sorted(metric_names)}",
                )
            )
    results.append(r8)

    all_ids = {str(st.get("id")) for _, st in stages}
    r9 = RuleResult(
        "DSL-SEM-009", "every repair_loop target names a real stage", "violation"
    )
    for path, st in stages:
        if st.get("kind") == "repair_loop":
            r9.checked += 1
            missing = [t for t in st.get("target", []) or [] if str(t) not in all_ids]
            if missing:
                r9.violations.append((path, f"target(s) {missing} do not name a stage"))
    results.append(r9)

    r10 = RuleResult(
        "DSL-SEM-010",
        "an inline param `schema` escape hatch is itself a valid JSON Schema",
        "violation",
    )
    for name, spec in (workflow.get("params", {}) or {}).items():
        if isinstance(spec, Mapping) and isinstance(spec.get("schema"), Mapping):
            r10.checked += 1
            try:
                from jsonschema import Draft202012Validator

                Draft202012Validator.check_schema(spec["schema"])
            except Exception as exc:  # noqa: BLE001
                r10.violations.append((f"params/{name}/schema", str(exc)[:200]))
    results.append(r10)

    policy = workflow.get("tool_policy") or {}
    default_deny = str(policy.get("default", "deny")) == "deny"
    allow = set(policy.get("allow", []) or [])
    deny = set(policy.get("deny", []) or [])
    r11 = RuleResult(
        "DSL-SEM-011",
        "every tool a stage or role requests is permitted by tool_policy (deny by default)",
        "violation",
    )

    def check_tools(where: str, tools: Any) -> None:
        for t in tools or []:
            r11.checked += 1
            token = str(t)
            if token in deny:
                r11.violations.append(
                    (where, f"tool {token!r} is explicitly denied by tool_policy.deny")
                )
            elif default_deny and token not in allow:
                r11.violations.append(
                    (
                        where,
                        f"tool {token!r} is not in tool_policy.allow and the policy default is deny",
                    )
                )

    for rname, rspec in (workflow.get("roles", {}) or {}).items():
        if isinstance(rspec, Mapping):
            check_tools(f"roles/{rname}", rspec.get("tool_permissions"))
    for path, st in stages:
        check_tools(path, st.get("tool_permissions"))
    results.append(r11)

    r12 = RuleResult(
        "DSL-SEM-012", "a fanout over a param references a declared param", "violation"
    )
    for path, st in stages:
        over = st.get("over")
        if isinstance(over, Mapping) and over.get("source") == "param":
            r12.checked += 1
            ref = str(over.get("ref", ""))
            if ref not in known_params:
                r12.violations.append(
                    (
                        path,
                        f"fanout over param {ref!r} which is not declared in params {sorted(known_params)}",
                    )
                )
    results.append(r12)

    r13 = RuleResult(
        "DSL-SEM-013",
        "a secret param value never travels in an export bundle (only the reference name)",
        "violation",
    )
    secret_params = [
        n
        for n, s in (workflow.get("params", {}) or {}).items()
        if isinstance(s, Mapping) and (s.get("secret") or s.get("type") == "secret_ref")
    ]
    export = (workflow.get("portability") or {}).get("export") or {}
    if secret_params:
        r13.checked += 1
        if export and export.get("redact_secrets") is not True:
            r13.violations.append(
                (
                    wf_id,
                    f"workflow declares secret params {secret_params} but export.redact_secrets is not true",
                )
            )
    results.append(r13)

    r14 = RuleResult(
        "DSL-SEM-014",
        "council stopping-rule TEXT also parses under councilspec.expression (cross-implementation check)",
        "advisory",
    )
    council_rules: list[tuple[str, Any]] = []
    for path, st in stages:
        if st.get("kind") == "council":
            for i, rule in enumerate(st.get("stopping_rules", []) or []):
                if isinstance(rule, Mapping) and isinstance(
                    rule.get("expression"), str
                ):
                    council_rules.append(
                        (f"{path}/stopping_rules/{i}", rule["expression"])
                    )
    if council_rules:
        try:
            from councilspec import expression as council_expr  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            r14.violations.append(
                (
                    "<import>",
                    f"NOT-CHECKED: councilspec.expression unavailable ({type(exc).__name__})",
                )
            )
        else:
            for path, text in council_rules:
                r14.checked += 1
                try:
                    council_expr.parse(text)
                except Exception as exc:  # noqa: BLE001
                    r14.violations.append(
                        (path, f"councilspec rejected: {str(exc)[:160]}")
                    )
    results.append(r14)

    return results
