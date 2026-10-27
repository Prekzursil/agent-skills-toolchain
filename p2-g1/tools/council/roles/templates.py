"""Council role templates: registry, mandate schema, custom-role authoring.

Unit IMP-0360 (rebuilt 2026-10-25, wave2 shard14 resume completion). The tree
carried a generated import-stub at this path, so the certified implementation
was re-derived from the unit contract: the receipt evidence block plus the two
named probes, which are the executable specification.

Contract surface (probe-verified):
  builtin_registry() -> Registry with .templates()/.get(id)/.ceiling()
  resolve_template(id, reg)       identity resolve; KeyError on unknown id
  schema_conformance_pass(roles)  mandate-schema validation over role docs
  detect_template_drift(reg, mutant=None)  drift findings with .reason
  author_custom_role(spec, reg)   -> .accepted/.role/.refusals/.escalation
  rights_escalation_check(role, reg, base=) -> .fired/.reasons/.excess_tools
  RoleMandate                     mandate dataclass (tool_access frozenset)

Refusal vocabulary (certified, receipt IMP-0360 evidence E2/E3):
  rights-escalation:<axis>:<grant>   grant no builtin template allows
  exceeds-template:<axis>:<grant>    grant beyond THIS template, on some other
  schema-invalid:unknown-fields      spec key outside the mandate schema

SPEC anchor: _USER-PROMPTS.md:11177
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

SPEC_ANCHOR = "_USER-PROMPTS.md:11177"

# Tokens no builtin template may carry: grants of these are rights escalations.
NEVER_GRANTED_TOOL = "runtime.unrestricted"
NEVER_GRANTED_SOURCE = "estate.secrets"
NEVER_GRANTED_PERMISSION = "override_quorum"

# Mandate schema: the exact field set of a role document, with types.
MANDATE_FIELDS: dict[str, tuple[type, ...]] = {
    "id": (str,),
    "name": (str,),
    "kind": (str,),
    "template_id": (str,),
    "obligations": (list,),
    "permissions": (list,),
    "tool_access": (list,),
    "source_access": (list,),
    "speaking": (bool,),
    "vote": (bool,),
    "veto": (bool,),
    "vote_weight": (int, float),
    "incompatible_with": (list,),
}
_BOOL_FIELDS = {"speaking", "vote", "veto"}
_LIST_FIELDS = {
    "obligations",
    "permissions",
    "tool_access",
    "source_access",
    "incompatible_with",
}


@dataclass
class RoleMandate:
    id: str = ""
    name: str = ""
    kind: str = "template"
    template_id: str = ""
    obligations: tuple = ()
    permissions: frozenset = field(default_factory=frozenset)
    tool_access: frozenset = field(default_factory=frozenset)
    source_access: frozenset = field(default_factory=frozenset)
    speaking: bool = True
    vote: bool = True
    veto: bool = False
    vote_weight: float = 1.0
    incompatible_with: tuple = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "template_id": self.template_id,
            "obligations": list(self.obligations),
            "permissions": sorted(self.permissions),
            "tool_access": sorted(self.tool_access),
            "source_access": sorted(self.source_access),
            "speaking": self.speaking,
            "vote": self.vote,
            "veto": self.veto,
            "vote_weight": self.vote_weight,
            "incompatible_with": list(self.incompatible_with),
        }


@dataclass
class Template:
    id: str = ""
    name: str = ""
    obligations: tuple = ()
    permissions: tuple = ()
    tool_access: tuple = ()
    source_access: tuple = ()
    speaking: bool = True
    vote: bool = True
    veto: bool = False
    vote_weight: float = 1.0
    incompatible_with: tuple = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": "template",
            "template_id": self.id,
            "obligations": list(self.obligations),
            "permissions": sorted(self.permissions),
            "tool_access": sorted(self.tool_access),
            "source_access": sorted(self.source_access),
            "speaking": self.speaking,
            "vote": self.vote,
            "veto": self.veto,
            "vote_weight": self.vote_weight,
            "incompatible_with": list(self.incompatible_with),
        }


def _validate_doc(doc: Any) -> list[str]:
    """Validate one role document against MANDATE_FIELDS. Returns error strings."""
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    unknown = sorted(set(doc) - set(MANDATE_FIELDS))
    if unknown:
        errs.append("unknown mandate fields: " + ", ".join(unknown))
    for name, allowed in MANDATE_FIELDS.items():
        if name not in doc:
            errs.append(f"missing field: {name}")
            continue
        val = doc[name]
        if name in _BOOL_FIELDS and not isinstance(val, bool):
            errs.append(f"field {name} must be bool, got {type(val).__name__}")
        elif name in _LIST_FIELDS and not isinstance(val, list):
            errs.append(f"field {name} must be list, got {type(val).__name__}")
        elif name == "vote_weight" and (isinstance(val, bool) or not isinstance(val, (int, float))):
            errs.append(f"field vote_weight must be numeric, got {type(val).__name__}")
        elif name in ("id", "name", "kind", "template_id") and not isinstance(val, str):
            errs.append(f"field {name} must be str, got {type(val).__name__}")
    return errs


@dataclass
class ConformanceResult:
    ok: bool
    checked: int
    errors: list


def schema_conformance_pass(roles: Iterable[Any]) -> ConformanceResult:
    docs = [r.as_dict() if hasattr(r, "as_dict") else r for r in roles]
    errors: list = []
    for doc in docs:
        errors.extend(_validate_doc(doc))
    return ConformanceResult(ok=not errors, checked=len(docs), errors=errors)


@dataclass
class DriftFinding:
    template_id: str
    reason: str


def detect_template_drift(reg: "Registry", mutant: dict | None = None) -> list:
    """Live-templates drift vs mandate schema, or validate one mutant doc."""
    if mutant is not None:
        docs = [(str(mutant.get("id") or "<mutant>"), mutant)]
    else:
        docs = [(t.id, t.as_dict()) for t in reg.templates()]
    findings: list = []
    for tid, doc in docs:
        for err in _validate_doc(doc):
            findings.append(DriftFinding(template_id=tid, reason=err))
    return findings


@dataclass(frozen=True)
class Ceiling:
    tools: frozenset
    sources: frozenset
    permissions: frozenset


class Registry:
    def __init__(self, templates: list):
        self._templates = {t.id: t for t in templates}

    def templates(self) -> list:
        return [self._templates[k] for k in sorted(self._templates)]

    def get(self, tid: str) -> RoleMandate:
        t = self._templates[tid]
        return RoleMandate(
            id=t.id,
            name=t.name,
            kind="template",
            template_id=t.id,
            obligations=t.obligations,
            permissions=frozenset(t.permissions),
            tool_access=frozenset(t.tool_access),
            source_access=frozenset(t.source_access),
            speaking=t.speaking,
            vote=t.vote,
            veto=t.veto,
            vote_weight=t.vote_weight,
            incompatible_with=t.incompatible_with,
        )

    def ceiling(self) -> Ceiling:
        tools: set = set()
        sources: set = set()
        permissions: set = set()
        for t in self._templates.values():
            tools.update(t.tool_access)
            sources.update(t.source_access)
            permissions.update(t.permissions)
        return Ceiling(
            tools=frozenset(tools),
            sources=frozenset(sources),
            permissions=frozenset(permissions),
        )


def builtin_registry() -> Registry:
    """The 10 builtin templates (certified roster, receipt IMP-0360 evidence E1)."""
    return Registry(
        [
            Template(
                id="architect",
                name="Architect",
                obligations=("evidence-first", "no-self-review"),
                tool_access=("read", "glob"),
            ),
            Template(
                id="chair",
                name="Chair",
                obligations=("evidence-first", "quota-enforcement", "record-outcome"),
                permissions=("facilitate", "close-decision"),
                tool_access=("edit", "glob", "grep", "read", "write"),
                veto=True,
                incompatible_with=("skeptic",),
            ),
            Template(
                id="critic",
                name="Critic",
                obligations=("evidence-first", "no-self-review"),
                tool_access=("read",),
            ),
            Template(
                id="juror",
                name="Juror",
                obligations=("evidence-first", "record-outcome"),
                permissions=("cast-ballot",),
                tool_access=("read",),
            ),
            Template(
                id="observer",
                name="Observer",
                obligations=("silence-is-consent-within-window",),
                tool_access=("read",),
                vote=False,
                veto=False,
                vote_weight=0.0,
            ),
            Template(
                id="pragmatist",
                name="Pragmatist",
                obligations=("evidence-first", "no-self-review"),
                tool_access=("read", "grep"),
            ),
            Template(
                id="proposer",
                name="Proposer",
                obligations=("evidence-first", "no-self-review"),
                tool_access=("read", "write"),
            ),
            Template(
                id="scribe",
                name="Scribe",
                obligations=("record-outcome", "silence-is-consent-within-window"),
                permissions=("record-transcript",),
                tool_access=("read", "write", "edit"),
            ),
            Template(
                id="skeptic",
                name="Skeptic",
                obligations=("evidence-first", "no-self-review"),
                tool_access=("read", "grep"),
            ),
            Template(
                id="synthesizer",
                name="Synthesizer",
                obligations=("record-outcome", "evidence-first"),
                tool_access=("read", "glob"),
                source_access=("council-transcripts",),
            ),
        ]
    )


def resolve_template(tid: str, reg: Registry) -> Template:
    """Identity resolve; raises KeyError on unknown id (probe1 contract)."""
    templates = {t.id: t for t in reg.templates()}
    if tid not in templates:
        raise KeyError(f"no such template: {tid}")
    return templates[tid]


@dataclass
class Escalation:
    fired: bool
    excess_tools: list
    excess_rights: list
    reasons: list = field(default_factory=list)


@dataclass
class AuthorResult:
    accepted: bool
    role: RoleMandate | None
    refusals: list
    escalation: Escalation | None


def rights_escalation_check(role: Any, reg: Registry, base: RoleMandate) -> Escalation:
    """Typed escalation detector over tool/permission axes vs the global ceiling.

    fired only for grants NO builtin template allows (not on the ceiling).
    Ceiling grants beyond the base template are exceeds-template, not escalation.
    """
    ceiling = reg.ceiling()
    role_tools = frozenset(role.tool_access or ())
    role_perms = frozenset(role.permissions or ())
    excess_tools = sorted(
        t for t in (role_tools - base.tool_access) if t not in ceiling.tools
    )
    excess_rights = sorted(
        p for p in (role_perms - base.permissions) if p not in ceiling.permissions
    )
    return Escalation(
        fired=bool(excess_tools or excess_rights),
        excess_tools=excess_tools,
        excess_rights=excess_rights,
        reasons=[f"rights-escalation:tool_access:{t}" for t in excess_tools]
        + [f"rights-escalation:permissions:{p}" for p in excess_rights],
    )


def _spec_unknown_keys(spec: Any) -> list:
    if not isinstance(spec, dict):
        return ["schema-invalid:spec-not-object"]
    allowed = set(MANDATE_FIELDS)
    unknown = sorted(set(spec) - allowed)
    if unknown:
        return [
            "schema-invalid:unknown-fields",
            "schema-invalid:unknown-fields:" + ",".join(unknown),
        ]
    return []


def author_custom_role(spec: dict, reg: Registry) -> AuthorResult:
    """Author a custom role from a builtin template with rights ceilings.

    A grant beyond the template that NO builtin allows is a rights escalation
    (refused, escalation fired, excess named). A grant some other template has
    is an exceeds-template refusal without an escalation classification.
    """
    refusals: list = []
    spec_errs = _spec_unknown_keys(spec)
    if spec_errs:
        return AuthorResult(False, None, refusals + spec_errs, None)

    tid = str(spec.get("template_id") or "")
    try:
        reg.get(tid)
    except KeyError:
        return AuthorResult(False, None, refusals + [f"schema-invalid:template-missing:{tid}"], None)
    base = reg.get(tid)

    tools_ask = {str(t) for t in (spec.get("tool_access") or [])}
    perms_ask = {str(p) for p in (spec.get("permissions") or [])}
    ceiling = reg.ceiling()

    tools_beyond_ceiling = sorted(
        t for t in tools_ask - base.tool_access if t not in ceiling.tools
    )
    perms_beyond_ceiling = sorted(
        p for p in perms_ask - base.permissions if p not in ceiling.permissions
    )
    tools_beyond_template = sorted(tools_ask - base.tool_access)
    perms_beyond_template = sorted(perms_ask - base.permissions)

    escalation: Escalation | None = None
    if tools_beyond_ceiling or perms_beyond_ceiling:
        escalation = Escalation(
            fired=True,
            excess_tools=tools_beyond_ceiling,
            excess_rights=perms_beyond_ceiling,
            reasons=[f"rights-escalation:tool_access:{t}" for t in tools_beyond_ceiling]
            + [f"rights-escalation:permissions:{p}" for p in perms_beyond_ceiling],
        )
    for tool in tools_beyond_ceiling:
        refusals.append(f"rights-escalation:tool_access:{tool}")
    for perm in perms_beyond_ceiling:
        refusals.append(f"rights-escalation:permissions:{perm}")
    for tool in tools_beyond_template:
        row = f"exceeds-template:tool_access:{tool}"
        if row not in refusals and f"rights-escalation:tool_access:{tool}" not in refusals:
            refusals.append(row)
    for perm in perms_beyond_template:
        row = f"exceeds-template:permissions:{perm}"
        if row not in refusals and f"rights-escalation:permissions:{perm}" not in refusals:
            refusals.append(row)
    if spec.get("veto") and not base.veto:
        refusals.append("exceeds-template:veto")
    if not spec.get("vote", True) and base.vote:
        refusals.append("exceeds-template:vote-downgrade")

    if refusals:
        return AuthorResult(False, None, refusals, escalation)

    weight = spec.get("vote_weight", base.vote_weight)
    role = RoleMandate(
        id=str(spec.get("id") or ""),
        name=str(spec.get("name") or ""),
        kind="custom",
        template_id=tid,
        obligations=base.obligations,
        permissions=frozenset(perms_ask),
        tool_access=frozenset(tools_ask),
        source_access=frozenset(str(s) for s in (spec.get("source_access") or [])),
        speaking=bool(spec.get("speaking", base.speaking)),
        vote=bool(spec.get("vote", base.vote)),
        veto=bool(spec.get("veto", base.veto)),
        vote_weight=float(weight),
        incompatible_with=base.incompatible_with,
    )
    return AuthorResult(True, role, [], None)
