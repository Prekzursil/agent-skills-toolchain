"""Role-template registry with custom-role authoring (IMP-0360).

Spec anchor ``_USER-PROMPTS.md:11177`` and CNL-0022: a role grants three distinct
things -- *obligations* the participant MUST discharge, *permissions* it MAY use,
and *rights* nobody may deny it.  The rights are exactly the five that
:mod:`council.roles.mandate` enforces at the point of use: ``speaking``, ``vote``
and ``veto`` (booleans) plus ``tool_access`` and ``source_access`` (name-exact
grant sets).  ``vote_weight`` qualifies the vote right; ``incompatible_with``
names templates one seat may not combine with.

The module provides

* ten builtin :class:`RoleMandate` templates behind :func:`builtin_registry`,
  looked up with :func:`resolve_template` (``KeyError`` for an unknown id);
* :func:`author_custom_role`, the only path to a *custom* role: it cites a
  builtin template and may only NARROW it -- fewer rights, never a right the
  template lacks, never a right no template grants, never a shed obligation;
* two independent detectors: :func:`rights_escalation_check` (a role grants a
  right above the global ceiling or above the template it cites) and
  :func:`detect_template_drift` (a template no longer conforms to the mandate
  schema, or the schema no longer matches ``mandate.RIGHTS``);
* :func:`schema_conformance_pass`, the ``parse_role`` walk over any mix of
  builtin and custom mandates.

All output is deterministic: sorted collections, no timestamps, no paths.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .mandate import RIGHTS as MANDATE_RIGHTS

SPEC_ANCHOR = "_USER-PROMPTS.md:11177"
MODULE_REL = "tools/council/roles/templates.py"

#: Grants that no builtin template carries.  A custom role asking for one of them
#: is a rights escalation by construction (probe negative controls).
NEVER_GRANTED_TOOL = "runtime.unrestricted"
NEVER_GRANTED_PERMISSION = "override_quorum"
NEVER_GRANTED_SOURCE = "source.unvetted"

BOOLEAN_RIGHTS: tuple[str, ...] = ("speaking", "vote", "veto")
ACCESS_RIGHTS: tuple[str, ...] = ("tool_access", "source_access")
SCHEMA_RIGHTS: tuple[str, ...] = BOOLEAN_RIGHTS + ACCESS_RIGHTS
KINDS: tuple[str, ...] = ("builtin", "custom")


# --------------------------------------------------------------------------- schema


@dataclass(frozen=True)
class FieldSpec:
    """One field of the mandate schema.

    ``kind`` is one of ``str``, ``optional-str``, ``bool``, ``number`` or ``set``
    (a collection of non-empty strings).
    """

    name: str
    kind: str
    doc: str


MANDATE_SCHEMA: tuple[FieldSpec, ...] = (
    FieldSpec("id", "str", "stable role identifier"),
    FieldSpec("name", "str", "human-readable label"),
    FieldSpec("kind", "str", "builtin | custom"),
    FieldSpec("template_id", "optional-str", "cited builtin template (custom roles only)"),
    FieldSpec("obligations", "set", "duties the participant MUST discharge"),
    FieldSpec("permissions", "set", "actions the participant MAY take"),
    FieldSpec("tool_access", "set", "right: name-exact tool grants"),
    FieldSpec("source_access", "set", "right: name-exact source grants"),
    FieldSpec("speaking", "bool", "right: may take speaking turns"),
    FieldSpec("vote", "bool", "right: may cast a ballot"),
    FieldSpec("veto", "bool", "right: may veto an outcome"),
    FieldSpec("vote_weight", "number", "ballot weight; 0 for non-voters"),
    FieldSpec("incompatible_with", "set", "template ids one seat may not combine with"),
)
MANDATE_FIELDS: tuple[str, ...] = tuple(spec.name for spec in MANDATE_SCHEMA)
_SPEC_BY_NAME: dict[str, FieldSpec] = {spec.name: spec for spec in MANDATE_SCHEMA}
_SET_FIELDS: tuple[str, ...] = tuple(spec.name for spec in MANDATE_SCHEMA if spec.kind == "set")


class MandateSchemaError(ValueError):
    """Raised by :func:`parse_role` when a mandate document violates the schema."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors: tuple[str, ...] = tuple(errors)
        super().__init__("; ".join(self.errors) or "invalid mandate")


def _check_type(spec: FieldSpec, value: Any) -> str | None:
    """Return a reason string when ``value`` has the wrong shape for ``spec``."""
    got = type(value).__name__
    if spec.kind == "str":
        return None if isinstance(value, str) else f"{spec.name}: expected str, got {got}"
    if spec.kind == "optional-str":
        if value is None or isinstance(value, str):
            return None
        return f"{spec.name}: expected str or null, got {got}"
    if spec.kind == "bool":
        return None if isinstance(value, bool) else f"{spec.name}: expected bool, got {got}"
    if spec.kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{spec.name}: expected number, got {got}"
        return None
    if spec.kind == "set":
        if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
            return f"{spec.name}: expected a collection of strings, got {got}"
        for item in value:
            if not isinstance(item, str) or not item:
                return f"{spec.name}: expected non-empty strings, got {type(item).__name__}"
        return None
    raise ValueError(f"unknown field kind {spec.kind!r}")


def validate_mandate(doc: Any, registry: TemplateRegistry | None = None) -> list[str]:
    """Validate a full mandate document against :data:`MANDATE_SCHEMA`.

    Returns the list of violations (empty when the document conforms).  Unknown
    and missing fields, per-field types, ``kind``/``template_id`` agreement and
    vote/vote_weight coherence are checked; when ``registry`` is given, every
    referenced template id must resolve in it.
    """
    if not isinstance(doc, Mapping):
        return [f"mandate: expected an object, got {type(doc).__name__}"]
    errors: list[str] = []
    unknown = sorted(str(key) for key in doc.keys() if key not in _SPEC_BY_NAME)
    if unknown:
        errors.append("unknown mandate fields: " + ", ".join(unknown))
    missing = [name for name in MANDATE_FIELDS if name not in doc]
    if missing:
        errors.append("missing mandate fields: " + ", ".join(missing))
    typed: dict[str, Any] = {}
    for spec in MANDATE_SCHEMA:
        if spec.name not in doc:
            continue
        problem = _check_type(spec, doc[spec.name])
        if problem is None:
            typed[spec.name] = doc[spec.name]
        else:
            errors.append(problem)
    if "id" in typed and not typed["id"].strip():
        errors.append("id: must be a non-empty string")
    if "kind" in typed and typed["kind"] not in KINDS:
        errors.append(f"kind: expected one of {', '.join(KINDS)}; got {typed['kind']!r}")
    if "vote_weight" in typed and typed["vote_weight"] < 0:
        errors.append("vote_weight: must be >= 0")
    if "vote" in typed and "vote_weight" in typed and typed["vote_weight"] >= 0:
        if typed["vote"] and typed["vote_weight"] == 0:
            errors.append("vote_weight: a voting role must weigh more than 0")
        if not typed["vote"] and typed["vote_weight"] != 0:
            errors.append("vote_weight: a non-voting role must weigh 0")
    if "kind" in typed and "template_id" in typed and typed["kind"] in KINDS:
        if typed["kind"] == "builtin" and typed["template_id"] is not None:
            errors.append("template_id: builtin templates carry no template_id")
        if typed["kind"] == "custom" and typed["template_id"] is None:
            errors.append("template_id: custom roles must cite a builtin template")
    if "id" in typed and "incompatible_with" in typed and typed["id"] in set(typed["incompatible_with"]):
        errors.append("incompatible_with: a role cannot be incompatible with itself")
    if registry is not None:
        cited = typed.get("template_id")
        if cited is not None and cited not in registry:
            errors.append(f"template_id: unknown template {cited!r}")
        for other in sorted(typed.get("incompatible_with") or ()):
            if other not in registry:
                errors.append(f"incompatible_with: unknown template {other!r}")
    return errors


# --------------------------------------------------------------------------- mandate


@dataclass(frozen=True)
class RoleMandate:
    """A role's mandate: obligations (MUST), permissions (MAY) and rights (may not be denied).

    Collection fields are normalised to ``frozenset`` so mandates are hashable and
    comparable; ``as_dict`` renders them as sorted lists.
    """

    id: str
    name: str
    kind: str = "builtin"
    template_id: str | None = None
    obligations: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    tool_access: frozenset[str] = frozenset()
    source_access: frozenset[str] = frozenset()
    speaking: bool = True
    vote: bool = False
    veto: bool = False
    vote_weight: float = 0.0
    incompatible_with: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(self.name, str):
            raise TypeError("name must be a string")
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}")
        if self.template_id is not None and not isinstance(self.template_id, str):
            raise TypeError("template_id must be a string or None")
        for field_name in _SET_FIELDS:
            value = getattr(self, field_name)
            if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Iterable):
                raise TypeError(f"{field_name} must be a collection of strings, not {type(value).__name__}")
            items = tuple(value)
            if any(not isinstance(item, str) or not item for item in items):
                raise TypeError(f"{field_name} must contain non-empty strings only")
            object.__setattr__(self, field_name, frozenset(items))
        for right in BOOLEAN_RIGHTS:
            if not isinstance(getattr(self, right), bool):
                raise TypeError(f"{right} must be a bool")
        if isinstance(self.vote_weight, bool) or not isinstance(self.vote_weight, (int, float)):
            raise TypeError("vote_weight must be a number")
        object.__setattr__(self, "vote_weight", float(self.vote_weight))

    @property
    def is_builtin(self) -> bool:
        return self.kind == "builtin"

    def as_dict(self) -> dict[str, Any]:
        """Schema-shaped, JSON-ready view (sorted lists, stable key order)."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "template_id": self.template_id,
            "obligations": sorted(self.obligations),
            "permissions": sorted(self.permissions),
            "tool_access": sorted(self.tool_access),
            "source_access": sorted(self.source_access),
            "speaking": self.speaking,
            "vote": self.vote,
            "veto": self.veto,
            "vote_weight": self.vote_weight,
            "incompatible_with": sorted(self.incompatible_with),
        }

    def rights(self) -> dict[str, Any]:
        """The five enforceable rights only (the surface ``mandate.RIGHTS`` names)."""
        return {
            "speaking": self.speaking,
            "vote": self.vote,
            "veto": self.veto,
            "tool_access": sorted(self.tool_access),
            "source_access": sorted(self.source_access),
        }

    def as_seat_mandate(self) -> dict[str, Any]:
        """Bridge to :func:`council.roles.mandate.seat`: grants keyed by right.

        Only granted rights appear, so the point-of-use gates in ``mandate.py``
        refuse everything this template does not carry.
        """
        grants: dict[str, set[str]] = {}
        for right in BOOLEAN_RIGHTS:
            if getattr(self, right):
                grants[right] = {right}
        if self.tool_access:
            grants["tool_access"] = set(self.tool_access)
        if self.source_access:
            grants["source_access"] = set(self.source_access)
        return {"name": self.id, "grants": grants}

    @classmethod
    def from_dict(cls, doc: Mapping[str, Any], registry: TemplateRegistry | None = None) -> RoleMandate:
        return parse_role(doc, registry)


def parse_role(doc: Mapping[str, Any], registry: TemplateRegistry | None = None) -> RoleMandate:
    """Parse a schema-shaped document into a :class:`RoleMandate`.

    This is the second code path next to the registry lookup: it validates the
    document field by field and rebuilds the mandate from scratch.
    """
    errors = validate_mandate(doc, registry)
    if errors:
        raise MandateSchemaError(errors)
    return RoleMandate(
        id=doc["id"],
        name=doc["name"],
        kind=doc["kind"],
        template_id=doc["template_id"],
        obligations=frozenset(doc["obligations"]),
        permissions=frozenset(doc["permissions"]),
        tool_access=frozenset(doc["tool_access"]),
        source_access=frozenset(doc["source_access"]),
        speaking=doc["speaking"],
        vote=doc["vote"],
        veto=doc["veto"],
        vote_weight=float(doc["vote_weight"]),
        incompatible_with=frozenset(doc["incompatible_with"]),
    )


# --------------------------------------------------------------------------- registry


@dataclass(frozen=True)
class RightsCeiling:
    """Union of everything any builtin template grants: the global upper bound."""

    tools: frozenset[str]
    sources: frozenset[str]
    permissions: frozenset[str]
    obligations: frozenset[str]
    rights: frozenset[str]
    max_vote_weight: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools": sorted(self.tools),
            "sources": sorted(self.sources),
            "permissions": sorted(self.permissions),
            "obligations": sorted(self.obligations),
            "rights": sorted(self.rights),
            "max_vote_weight": self.max_vote_weight,
        }


class TemplateRegistry:
    """Immutable, id-sorted collection of builtin role templates."""

    def __init__(self, templates: Iterable[RoleMandate]) -> None:
        by_id: dict[str, RoleMandate] = {}
        for template in templates:
            if not isinstance(template, RoleMandate):
                raise TypeError(f"registry accepts RoleMandate only, got {type(template).__name__}")
            if template.kind != "builtin":
                raise ValueError(f"registry accepts builtin templates only: {template.id!r} is {template.kind}")
            if template.id in by_id:
                raise ValueError(f"duplicate template id {template.id!r}")
            by_id[template.id] = template
        self._by_id: dict[str, RoleMandate] = dict(sorted(by_id.items()))

    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def templates(self) -> Iterator[RoleMandate]:
        """Templates in id order."""
        return iter(self._by_id.values())

    def items(self) -> Iterator[tuple[str, RoleMandate]]:
        return iter(self._by_id.items())

    def get(self, template_id: str) -> RoleMandate | None:
        return self._by_id.get(template_id)

    def __contains__(self, template_id: object) -> bool:
        return template_id in self._by_id

    def __len__(self) -> int:
        return len(self._by_id)

    def __iter__(self) -> Iterator[str]:
        return iter(self._by_id)

    def ceiling(self) -> RightsCeiling:
        tools: set[str] = set()
        sources: set[str] = set()
        permissions: set[str] = set()
        obligations: set[str] = set()
        rights: set[str] = set()
        max_weight = 0.0
        for template in self._by_id.values():
            tools |= template.tool_access
            sources |= template.source_access
            permissions |= template.permissions
            obligations |= template.obligations
            rights |= {right for right in BOOLEAN_RIGHTS if getattr(template, right)}
            max_weight = max(max_weight, template.vote_weight)
        return RightsCeiling(
            tools=frozenset(tools),
            sources=frozenset(sources),
            permissions=frozenset(permissions),
            obligations=frozenset(obligations),
            rights=frozenset(rights),
            max_vote_weight=max_weight,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "templates": [template.as_dict() for template in self._by_id.values()],
            "ceiling": self.ceiling().to_dict(),
        }


def _template(
    template_id: str,
    name: str,
    *,
    obligations: Iterable[str],
    permissions: Iterable[str],
    tool_access: Iterable[str],
    source_access: Iterable[str],
    speaking: bool = True,
    vote: bool,
    veto: bool = False,
    incompatible_with: Iterable[str] = (),
) -> RoleMandate:
    return RoleMandate(
        id=template_id,
        name=name,
        kind="builtin",
        template_id=None,
        obligations=frozenset(obligations),
        permissions=frozenset(permissions),
        tool_access=frozenset(tool_access),
        source_access=frozenset(source_access),
        speaking=speaking,
        vote=vote,
        veto=veto,
        vote_weight=1.0 if vote else 0.0,
        incompatible_with=frozenset(incompatible_with),
    )


#: The ten builtin templates.  Tool vocabulary is the workstation surface
#: (read/grep/glob/edit/write); sources are the council's evidence channels;
#: permissions are the structured actions the runtime guard recognises.
#: ``incompatible_with`` is reciprocal (checked by :func:`detect_template_drift`).
BUILTIN_TEMPLATES: tuple[RoleMandate, ...] = (
    _template(
        "architect",
        "Architect",
        obligations=("state_assumptions", "cite_evidence", "declare_conflicts"),
        permissions=("propose", "amend", "request_evidence"),
        tool_access=("read", "grep", "glob", "edit"),
        source_access=("repo", "evidence"),
        vote=True,
        incompatible_with=("critic",),
    ),
    _template(
        "chair",
        "Chair",
        obligations=("declare_conflicts", "close_rounds", "record_dissent", "stay_neutral"),
        permissions=("call_vote", "table_motion", "close_round", "set_agenda"),
        tool_access=("read",),
        source_access=("transcript", "minutes", "evidence"),
        vote=True,
        veto=True,
        incompatible_with=("juror", "proposer", "scribe", "observer"),
    ),
    _template(
        "critic",
        "Critic",
        obligations=("cite_evidence", "argue_against", "declare_conflicts"),
        permissions=("critique", "request_evidence"),
        tool_access=("read", "grep", "glob"),
        source_access=("repo", "evidence", "transcript"),
        vote=True,
        incompatible_with=("proposer", "architect", "synthesiser"),
    ),
    _template(
        "juror",
        "Juror",
        obligations=("answer_independently", "declare_conflicts"),
        permissions=("request_evidence",),
        tool_access=("read",),
        source_access=("transcript", "evidence"),
        vote=True,
        incompatible_with=("chair", "proposer"),
    ),
    _template(
        "observer",
        "Observer",
        obligations=("stay_in_mandate",),
        permissions=("request_clarification",),
        tool_access=("read",),
        source_access=("transcript",),
        vote=False,
        incompatible_with=("chair",),
    ),
    _template(
        "pragmatist",
        "Pragmatist",
        obligations=("test_feasibility", "cite_evidence", "declare_conflicts"),
        permissions=("amend", "request_evidence"),
        tool_access=("read", "grep", "glob"),
        source_access=("repo", "evidence"),
        vote=True,
    ),
    _template(
        "proposer",
        "Proposer",
        obligations=("state_assumptions", "cite_evidence", "declare_conflicts"),
        permissions=("propose", "amend", "withdraw"),
        tool_access=("read", "grep", "glob", "edit", "write"),
        source_access=("repo", "evidence"),
        vote=True,
        incompatible_with=("chair", "critic", "juror", "skeptic", "synthesiser"),
    ),
    _template(
        "scribe",
        "Scribe",
        obligations=("keep_minutes", "record_dissent", "stay_in_mandate"),
        permissions=("record_minutes", "request_clarification"),
        tool_access=("read", "write"),
        source_access=("transcript", "minutes"),
        vote=False,
        incompatible_with=("chair",),
    ),
    _template(
        "skeptic",
        "Skeptic",
        obligations=("argue_against", "cite_evidence", "declare_conflicts"),
        permissions=("critique", "request_evidence"),
        tool_access=("read", "grep", "glob"),
        source_access=("repo", "evidence", "precedent"),
        vote=True,
        incompatible_with=("proposer",),
    ),
    _template(
        "synthesiser",
        "Synthesiser",
        obligations=("record_dissent", "cite_evidence", "stay_neutral"),
        permissions=("summarise", "request_clarification"),
        tool_access=("read", "write"),
        source_access=("transcript", "evidence"),
        vote=False,
        incompatible_with=("proposer", "critic"),
    ),
)


def builtin_registry() -> TemplateRegistry:
    """A fresh registry over :data:`BUILTIN_TEMPLATES` (immutable; cheap to rebuild)."""
    return TemplateRegistry(BUILTIN_TEMPLATES)


def resolve_template(template_id: str, registry: TemplateRegistry | None = None) -> RoleMandate:
    """Look a builtin template up by id; ``KeyError`` when it does not exist."""
    reg = registry if registry is not None else builtin_registry()
    template = reg.get(template_id)
    if template is None:
        raise KeyError(f"unknown role template {template_id!r}; known: {', '.join(reg.ids())}")
    return template


# --------------------------------------------------------------------------- detectors


@dataclass(frozen=True)
class EscalationReport:
    """Outcome of :func:`rights_escalation_check`.

    ``excess_*`` name grants above the global ceiling (no template allows them);
    ``exceeds_template`` names grants above the cited template.  ``reasons`` is
    the ordered union of both detectors and ``fired`` is ``bool(reasons)``.
    """

    role_id: str
    base_id: str | None
    fired: bool
    reasons: tuple[str, ...]
    excess_tools: tuple[str, ...]
    excess_sources: tuple[str, ...]
    excess_permissions: tuple[str, ...]
    excess_rights: tuple[str, ...]
    exceeds_template: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "base_id": self.base_id,
            "fired": self.fired,
            "reasons": list(self.reasons),
            "excess_tools": list(self.excess_tools),
            "excess_sources": list(self.excess_sources),
            "excess_permissions": list(self.excess_permissions),
            "excess_rights": list(self.excess_rights),
            "exceeds_template": list(self.exceeds_template),
        }


def rights_escalation_check(
    role: RoleMandate,
    registry: TemplateRegistry | None = None,
    base: RoleMandate | None = None,
) -> EscalationReport:
    """Fire when ``role`` grants more than the templates allow.

    Detector 1 (global ceiling): any tool, source, permission, boolean right or
    vote weight that no builtin template carries -> ``rights-escalation:<axis>[:<token>]``.
    Detector 2 (cited template): anything above ``base`` (or the template
    ``role.template_id`` resolves to) -> ``exceeds-template:<axis>[:<token>]``,
    including obligations the template imposes that the role dropped.
    A grant that some *other* template carries is only an exceeds-template
    finding, never a global-ceiling one, so the two detectors discriminate.
    """
    if not isinstance(role, RoleMandate):
        raise TypeError(f"rights_escalation_check expects a RoleMandate, got {type(role).__name__}")
    reg = registry if registry is not None else builtin_registry()
    ceiling = reg.ceiling()
    if base is None and role.template_id is not None:
        base = reg.get(role.template_id)

    excess_tools = tuple(sorted(role.tool_access - ceiling.tools))
    excess_sources = tuple(sorted(role.source_access - ceiling.sources))
    excess_permissions = tuple(sorted(role.permissions - ceiling.permissions))
    excess_rights = tuple(right for right in BOOLEAN_RIGHTS if getattr(role, right) and right not in ceiling.rights)

    reasons: list[str] = []
    reasons.extend(f"rights-escalation:tool_access:{token}" for token in excess_tools)
    reasons.extend(f"rights-escalation:source_access:{token}" for token in excess_sources)
    reasons.extend(f"rights-escalation:permissions:{token}" for token in excess_permissions)
    reasons.extend(f"rights-escalation:{right}" for right in excess_rights)
    if role.vote_weight > ceiling.max_vote_weight:
        reasons.append(f"rights-escalation:vote_weight:{role.vote_weight:g}")

    exceeds: list[str] = []
    if base is not None:
        exceeds.extend(f"exceeds-template:tool_access:{token}" for token in sorted(role.tool_access - base.tool_access))
        exceeds.extend(
            f"exceeds-template:source_access:{token}" for token in sorted(role.source_access - base.source_access)
        )
        exceeds.extend(f"exceeds-template:permissions:{token}" for token in sorted(role.permissions - base.permissions))
        exceeds.extend(
            f"exceeds-template:{right}" for right in BOOLEAN_RIGHTS if getattr(role, right) and not getattr(base, right)
        )
        if role.vote_weight > base.vote_weight:
            exceeds.append(f"exceeds-template:vote_weight:{role.vote_weight:g}")
        exceeds.extend(
            f"exceeds-template:obligations-dropped:{token}" for token in sorted(base.obligations - role.obligations)
        )
    reasons.extend(exceeds)

    return EscalationReport(
        role_id=role.id,
        base_id=base.id if base is not None else None,
        fired=bool(reasons),
        reasons=tuple(reasons),
        excess_tools=excess_tools,
        excess_sources=excess_sources,
        excess_permissions=excess_permissions,
        excess_rights=excess_rights,
        exceeds_template=tuple(exceeds),
    )


@dataclass(frozen=True)
class DriftFinding:
    """One way a template (or mutant document) departs from the mandate schema."""

    template_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"template_id": self.template_id, "reason": self.reason}


def detect_template_drift(
    registry: TemplateRegistry | None = None,
    mutant: Mapping[str, Any] | None = None,
) -> list[DriftFinding]:
    """Report every departure from the mandate schema.

    With ``mutant`` given, only that document is checked (the both-states control:
    an extra key or a mistyped right must produce findings).  Otherwise every
    template in ``registry`` is walked: schema conformance, key/id agreement,
    ``as_dict``/``parse_role`` round-trip, reciprocal ``incompatible_with``, and
    agreement between the schema's rights and ``mandate.RIGHTS``.
    """
    reg = registry if registry is not None else builtin_registry()
    findings: list[DriftFinding] = []
    if mutant is not None:
        subject = str(mutant.get("id", "<mutant>")) if isinstance(mutant, Mapping) else "<mutant>"
        findings.extend(DriftFinding(subject, reason) for reason in validate_mandate(mutant, reg))
        return findings

    if set(MANDATE_RIGHTS) != set(SCHEMA_RIGHTS):
        findings.append(
            DriftFinding(
                "<schema>",
                f"rights drift: mandate.RIGHTS={sorted(MANDATE_RIGHTS)} schema={sorted(SCHEMA_RIGHTS)}",
            )
        )
    for template_id, template in reg.items():
        doc = template.as_dict()
        errors = validate_mandate(doc, reg)
        findings.extend(DriftFinding(template_id, reason) for reason in errors)
        if template.id != template_id:
            findings.append(DriftFinding(template_id, f"registered under {template_id!r} but id is {template.id!r}"))
        if template.kind != "builtin":
            findings.append(DriftFinding(template_id, f"kind: builtin registry holds a {template.kind} role"))
        if not errors and parse_role(doc, reg) != template:
            findings.append(DriftFinding(template_id, "as_dict/parse_role round-trip mismatch"))
        for other in sorted(template.incompatible_with):
            peer = reg.get(other)
            if peer is not None and template.id not in peer.incompatible_with:
                findings.append(DriftFinding(template_id, f"incompatible_with: {other} does not reciprocate"))
    return findings


@dataclass(frozen=True)
class ConformanceReport:
    """Result of :func:`schema_conformance_pass`: ``ok`` iff ``errors`` is empty."""

    ok: bool
    checked: int
    errors: tuple[str, ...]
    ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checked": self.checked, "errors": list(self.errors), "ids": list(self.ids)}


def schema_conformance_pass(
    mandates: Iterable[RoleMandate | Mapping[str, Any]],
    registry: TemplateRegistry | None = None,
) -> ConformanceReport:
    """Run every mandate through ``parse_role`` and count the violations.

    ``checked`` counts every item seen, conforming or not.  A
    :class:`RoleMandate` must also survive the ``as_dict`` -> ``parse_role``
    round-trip unchanged.
    """
    reg = registry if registry is not None else builtin_registry()
    errors: list[str] = []
    ids: list[str] = []
    checked = 0
    for item in mandates:
        checked += 1
        if isinstance(item, RoleMandate):
            doc: Mapping[str, Any] = item.as_dict()
        elif isinstance(item, Mapping):
            doc = dict(item)
        else:
            errors.append(f"#{checked}: expected RoleMandate or mapping, got {type(item).__name__}")
            continue
        label = str(doc.get("id") or f"#{checked}")
        ids.append(label)
        try:
            parsed = parse_role(doc, reg)
        except MandateSchemaError as exc:
            errors.extend(f"{label}: {reason}" for reason in exc.errors)
            continue
        if isinstance(item, RoleMandate) and parsed != item:
            errors.append(f"{label}: parse_role round-trip mismatch")
    return ConformanceReport(ok=not errors, checked=checked, errors=tuple(errors), ids=tuple(ids))


# --------------------------------------------------------------------------- authoring


@dataclass(frozen=True)
class AuthoringResult:
    """Outcome of :func:`author_custom_role`.

    ``refusals`` are machine-readable tokens (``schema-invalid:*``,
    ``unknown-template:*``, ``id-collision:*`` or the escalation reasons);
    ``notes`` carry the human-readable detail behind them.
    """

    accepted: bool
    role: RoleMandate | None
    refusals: tuple[str, ...]
    escalation: EscalationReport | None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "role": self.role.as_dict() if self.role is not None else None,
            "refusals": list(self.refusals),
            "escalation": self.escalation.to_dict() if self.escalation is not None else None,
            "notes": list(self.notes),
        }


_CUSTOM_REQUIRED: tuple[str, ...] = ("id", "template_id")


def _refuse(refusals: Iterable[str], notes: Iterable[str], escalation: EscalationReport | None = None) -> AuthoringResult:
    return AuthoringResult(
        accepted=False,
        role=None,
        refusals=tuple(refusals),
        escalation=escalation,
        notes=tuple(notes),
    )


def author_custom_role(spec: Mapping[str, Any], registry: TemplateRegistry | None = None) -> AuthoringResult:
    """Author a custom role from ``spec`` without letting it escalate rights.

    ``spec`` must cite a builtin ``template_id``; fields it omits are inherited
    from that template, so a spec can only narrow.  The spec is refused when it
    carries unknown or mistyped fields, cites an unknown template, collides with
    a builtin id, composes into a schema-invalid mandate, or when
    :func:`rights_escalation_check` fires on the composed role.
    """
    reg = registry if registry is not None else builtin_registry()
    if not isinstance(spec, Mapping):
        return _refuse(("schema-invalid:not-an-object",), (f"spec is a {type(spec).__name__}, not an object",))

    refusals: list[str] = []
    notes: list[str] = []
    unknown = sorted(str(key) for key in spec.keys() if key not in _SPEC_BY_NAME)
    if unknown:
        refusals.append("schema-invalid:unknown-fields")
        notes.append("unknown fields: " + ", ".join(unknown))
    for name in _CUSTOM_REQUIRED:
        if name not in spec:
            refusals.append(f"schema-invalid:missing:{name}")
    typed: dict[str, Any] = {}
    for field_spec in MANDATE_SCHEMA:
        if field_spec.name not in spec:
            continue
        problem = _check_type(field_spec, spec[field_spec.name])
        if problem is None:
            typed[field_spec.name] = spec[field_spec.name]
        else:
            refusals.append(f"schema-invalid:type:{field_spec.name}")
            notes.append(problem)
    if "kind" in typed and typed["kind"] != "custom":
        refusals.append("schema-invalid:kind")
        notes.append(f"kind: authored roles are 'custom', got {typed['kind']!r}")
    if "id" in typed and not typed["id"].strip():
        refusals.append("schema-invalid:empty:id")
    if "template_id" in typed and typed["template_id"] is None:
        refusals.append("schema-invalid:type:template_id")
        notes.append("template_id: a custom role must cite a builtin template")
    if refusals:
        return _refuse(refusals, notes)

    template_id = typed["template_id"]
    base = reg.get(template_id)
    if base is None:
        return _refuse((f"unknown-template:{template_id}",), (f"known templates: {', '.join(reg.ids())}",))
    role_id = typed["id"]
    if role_id in reg:
        return _refuse((f"id-collision:{role_id}",), (f"{role_id!r} is a builtin template id",))

    candidate = RoleMandate(
        id=role_id,
        name=typed.get("name", role_id),
        kind="custom",
        template_id=base.id,
        obligations=frozenset(typed.get("obligations", base.obligations)),
        permissions=frozenset(typed.get("permissions", base.permissions)),
        tool_access=frozenset(typed.get("tool_access", base.tool_access)),
        source_access=frozenset(typed.get("source_access", base.source_access)),
        speaking=typed.get("speaking", base.speaking),
        vote=typed.get("vote", base.vote),
        veto=typed.get("veto", base.veto),
        vote_weight=float(typed.get("vote_weight", base.vote_weight)),
        incompatible_with=frozenset(typed.get("incompatible_with", base.incompatible_with)),
    )

    composed_errors = validate_mandate(candidate.as_dict(), reg)
    for reason in composed_errors:
        refusals.append("schema-invalid:composed:" + reason.split(":", 1)[0].strip())
        notes.append(reason)
    report = rights_escalation_check(candidate, reg, base=base)
    if report.fired:
        refusals.extend(report.reasons)
    if refusals:
        return _refuse(refusals, notes, report)
    return AuthoringResult(accepted=True, role=candidate, refusals=(), escalation=report, notes=tuple(notes))


__all__ = [
    "ACCESS_RIGHTS",
    "AuthoringResult",
    "BOOLEAN_RIGHTS",
    "BUILTIN_TEMPLATES",
    "ConformanceReport",
    "DriftFinding",
    "EscalationReport",
    "FieldSpec",
    "KINDS",
    "MANDATE_FIELDS",
    "MANDATE_SCHEMA",
    "MODULE_REL",
    "MandateSchemaError",
    "NEVER_GRANTED_PERMISSION",
    "NEVER_GRANTED_SOURCE",
    "NEVER_GRANTED_TOOL",
    "RightsCeiling",
    "RoleMandate",
    "SCHEMA_RIGHTS",
    "SPEC_ANCHOR",
    "TemplateRegistry",
    "author_custom_role",
    "builtin_registry",
    "detect_template_drift",
    "parse_role",
    "resolve_template",
    "rights_escalation_check",
    "schema_conformance_pass",
    "validate_mandate",
]
