"""Jury topology: deciders who did not argue, a judge who rules admissibility, a typed verdict.

Roles (IMP-0285, CNL-0034, P17 "jury with allowed hung")
---------------------------------------------------------
* ``Exhibit`` -- one piece of evidence; its ``source_type`` classifies into an evidence
  tier (``any-cited`` < ``peer-reviewed-only`` < ``executable-proof-only``).
* ``Judge`` -- rules which exhibits are admissible under the spec's evidence standard and
  reads the verdict form. The judge never ballots: a judge seated as a juror is refused by
  ``run_jury`` and rejected by ``validate_verdict_form`` (code ``judge-as-juror``).
* ``JurorBrief`` -- one juror's ballot label, verbatim reasoning, and cited exhibit ids.
* ``JurySpec`` -- question, exhibits, jurors, judge, evidence standard, decision rule.

Decision
--------
The finding is computed ONLY from ballot labels. A label is promoted to ``DECISION`` when
its count reaches the threshold set by the decision rule (``unanimity`` = panel size,
``majority`` = floor(n/2)+1, ``supermajority`` = ceil(2n/3); every rule needs more than
half the panel, so at most one label can qualify). Otherwise the outcome is
``NO-DECISION`` with ``finding`` ``None`` and ``hung_reason`` ``threshold-not-met``; the
plurality label is recorded as ``plurality_finding`` but never promoted.
``coerce_plurality_finding`` exists as the negative control for that rule, not as a
decision path. Juror reasoning is copied verbatim into the ``juror-reasoning`` turns and
is never parsed, so instructions planted in a brief cannot retarget the tally (ADV-0071).

Support
-------
``check_verdict_support`` is a separate typed report: a promoted finding is supported only
if at least one juror who balloted for it recorded non-empty reasoning that cites an
admitted exhibit. A lawful hung verdict promotes nothing and is therefore supported.
``plant_unsupported_verdict`` builds the bad state for that check.

``RecordingKernel`` is a local event log standing in for ``tools/council/kernel.py``
(IMP-0264): the topology never writes participant output anywhere else.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

OUTCOME_DECISION = "DECISION"
OUTCOME_NO_DECISION = "NO-DECISION"
OUTCOME_KINDS = frozenset({OUTCOME_DECISION, OUTCOME_NO_DECISION})

HUNG_THRESHOLD_NOT_MET = "threshold-not-met"

RULE_UNANIMITY = "unanimity"
RULE_MAJORITY = "majority"
RULE_SUPERMAJORITY = "supermajority"
DECISION_RULES = (RULE_UNANIMITY, RULE_MAJORITY, RULE_SUPERMAJORITY)

TIER_ANY_CITED = "any-cited"
TIER_PEER_REVIEWED = "peer-reviewed-only"
TIER_EXECUTABLE = "executable-proof-only"
# Ascending strictness; an exhibit is admissible when its tier is at least the standard.
EVIDENCE_TIERS = (TIER_ANY_CITED, TIER_PEER_REVIEWED, TIER_EXECUTABLE)
_TIER_RANK = {tier: rank for rank, tier in enumerate(EVIDENCE_TIERS)}

# source_type -> tier. Anything not listed (anecdote, rumor, blog, forum, ...) is any-cited.
_SOURCE_TYPE_TIER = {
    "executable-proof": TIER_EXECUTABLE,
    "executable": TIER_EXECUTABLE,
    "reproduction": TIER_EXECUTABLE,
    "test-run": TIER_EXECUTABLE,
    "peer-reviewed": TIER_PEER_REVIEWED,
    "peer-reviewed-paper": TIER_PEER_REVIEWED,
    "systematic-review": TIER_PEER_REVIEWED,
    "meta-analysis": TIER_PEER_REVIEWED,
}

REASON_BELOW_STANDARD = "below-evidence-standard"

TURN_ADMISSIBILITY = "admissibility"
TURN_JUROR_REASONING = "juror-reasoning"
TURN_VERDICT = "verdict"

SUPPORT_NEEDED = "at least one juror ballot+reasoning citing an admitted exhibit"
SUPPORT_REASON_NONE = "no juror's recorded reasoning supports this finding"


class JurySpecError(ValueError):
    """The jury cannot be seated as specified (empty panel, judge as juror, unknown rule...)."""


# --------------------------------------------------------------------------- participants


@dataclass(frozen=True)
class Exhibit:
    """A piece of evidence offered to the panel."""

    exhibit_id: str
    claim: str
    source_type: str
    body: str = ""

    @property
    def tier(self) -> str:
        return classify_tier(self.source_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "exhibit_id": self.exhibit_id,
            "claim": self.claim,
            "source_type": self.source_type,
            "body": self.body,
            "tier": self.tier,
        }


@dataclass(frozen=True)
class Judge:
    """Rules admissibility and reads the verdict form; never casts a ballot."""

    judge_id: str


@dataclass
class JurorBrief:
    """One juror's ballot label, verbatim reasoning, and the exhibit ids it cites."""

    juror_id: str
    ballot: str
    reasoning: str = ""
    cites: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self.cites = tuple(str(c) for c in (self.cites or ()))
        self.reasoning = "" if self.reasoning is None else str(self.reasoning)

    def to_dict(self) -> dict[str, Any]:
        return {
            "juror_id": self.juror_id,
            "ballot": self.ballot,
            "reasoning": self.reasoning,
            "cites": list(self.cites),
        }


@dataclass
class JurySpec:
    """Everything the panel is seated with."""

    question: str
    exhibits: list[Exhibit]
    jurors: list[JurorBrief]
    judge: Judge
    evidence_standard: str = TIER_ANY_CITED
    decision_rule: str = RULE_MAJORITY


# --------------------------------------------------------------------------- typed outputs


@dataclass
class Verdict:
    """The typed verdict form. ``finding`` is ``None`` exactly when ``outcome_kind`` is hung."""

    outcome_kind: str
    finding: str | None
    hung_reason: str
    ballot_tally: dict[str, int]
    decision_rule: str
    threshold: int
    panel_size: int
    juror_ids: list[str]
    judge_id: str
    plurality_finding: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_kind": self.outcome_kind,
            "finding": self.finding,
            "hung_reason": self.hung_reason,
            "ballot_tally": dict(self.ballot_tally),
            "decision_rule": self.decision_rule,
            "threshold": self.threshold,
            "panel_size": self.panel_size,
            "juror_ids": list(self.juror_ids),
            "judge_id": self.judge_id,
            "plurality_finding": self.plurality_finding,
        }


@dataclass
class UnsupportedFinding:
    """A promoted finding that no juror's recorded reasoning supports."""

    finding: str
    reason: str = SUPPORT_REASON_NONE
    needed: str = SUPPORT_NEEDED

    def to_dict(self) -> dict[str, str]:
        return {"finding": self.finding, "reason": self.reason, "needed": self.needed}


@dataclass
class SupportReport:
    """Which ballot labels are backed by reasoning that cites admitted evidence."""

    ok: bool
    supported_by: dict[str, list[str]] = field(default_factory=dict)
    unsupported: list[UnsupportedFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "supported_by": {k: list(v) for k, v in self.supported_by.items()},
            "unsupported": [u.to_dict() for u in self.unsupported],
        }


@dataclass
class JurorRecord:
    """A juror's brief after admissibility: which of its cites survived the judge's ruling."""

    juror_id: str
    ballot: str
    reasoning: str
    cites: list[str]
    admitted_cites: list[str]
    excluded_cites: list[str]

    def supports_ballot(self) -> bool:
        """True when the reasoning is non-empty and cites at least one admitted exhibit."""
        return bool(self.reasoning.strip()) and bool(self.admitted_cites)

    def to_dict(self) -> dict[str, Any]:
        return {
            "juror_id": self.juror_id,
            "ballot": self.ballot,
            "reasoning": self.reasoning,
            "cites": list(self.cites),
            "admitted_cites": list(self.admitted_cites),
            "excluded_cites": list(self.excluded_cites),
            "supports_ballot": self.supports_ballot(),
        }


@dataclass
class JuryResult:
    """Output of ``run_jury``: verdict form, support report, admissibility ruling, turn log."""

    question: str
    verdict: Verdict
    support: SupportReport
    admitted: list[str]
    excluded: list[dict[str, Any]]
    turns: list[dict[str, Any]]
    juror_records: list[JurorRecord]

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "verdict": self.verdict.to_dict(),
            "support": self.support.to_dict(),
            "admitted": list(self.admitted),
            "excluded": [dict(row) for row in self.excluded],
            "turns": [dict(t) for t in self.turns],
            "juror_records": [r.to_dict() for r in self.juror_records],
        }


class RecordingKernel:
    """Local event log: every turn the topology produces is recorded here and nowhere else."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.turns_executed = 0

    def record(self, event: Mapping[str, Any]) -> None:
        self.turns_executed += 1
        self.events.append(dict(event))


# --------------------------------------------------------------------------- evidence tiers


def classify_tier(source_type: str | None) -> str:
    """Map an exhibit's ``source_type`` to its evidence tier (unknown types are any-cited)."""
    key = str(source_type or "").strip().lower()
    return _SOURCE_TYPE_TIER.get(key, TIER_ANY_CITED)


def tier_rank(tier: str) -> int:
    """Ordinal of a tier in ``EVIDENCE_TIERS``; unknown tiers raise ``JurySpecError``."""
    try:
        return _TIER_RANK[tier]
    except KeyError:
        raise JurySpecError(
            f"unknown evidence standard {tier!r}; known: {list(EVIDENCE_TIERS)}"
        ) from None


def admit_exhibits(
    exhibits: Iterable[Exhibit], evidence_standard: str
) -> tuple[list[str], list[dict[str, Any]]]:
    """Split exhibits into admitted ids and exclusion records under the evidence standard.

    An exclusion record keeps the tier the exhibit was offered under (``claimed_tier``,
    the panel's standard) beside the tier its source type actually earns
    (``classified_tier``), so a later reader can see what was claimed and what was found.
    """
    floor = tier_rank(evidence_standard)
    admitted: list[str] = []
    excluded: list[dict[str, Any]] = []
    for ex in exhibits:
        tier = classify_tier(ex.source_type)
        if tier_rank(tier) >= floor:
            admitted.append(ex.exhibit_id)
        else:
            excluded.append(
                {
                    "exhibit_id": ex.exhibit_id,
                    "source_type": ex.source_type,
                    "claimed_tier": evidence_standard,
                    "classified_tier": tier,
                    "reason": REASON_BELOW_STANDARD,
                }
            )
    return admitted, excluded


# --------------------------------------------------------------------------- ballots


def decision_threshold(decision_rule: str, panel_size: int) -> int:
    """Ballots a label needs under the rule; always more than half the panel."""
    if not isinstance(panel_size, int) or isinstance(panel_size, bool) or panel_size < 1:
        raise JurySpecError(f"panel_size must be a positive int, got {panel_size!r}")
    if decision_rule == RULE_UNANIMITY:
        return panel_size
    if decision_rule == RULE_MAJORITY:
        return panel_size // 2 + 1
    if decision_rule == RULE_SUPERMAJORITY:
        return -(-2 * panel_size // 3)
    raise JurySpecError(
        f"unknown decision rule {decision_rule!r}; known: {list(DECISION_RULES)}"
    )


def tally_ballots(jurors: Iterable[JurorBrief | JurorRecord]) -> dict[str, int]:
    """Count ballot labels; keys sorted so the tally is deterministic."""
    counts: dict[str, int] = {}
    for juror in jurors:
        counts[juror.ballot] = counts.get(juror.ballot, 0) + 1
    return dict(sorted(counts.items()))


def coerce_plurality_finding(ballot_tally: Mapping[str, int]) -> str | None:
    """The label with strictly the most ballots, or ``None`` when the top is tied or empty.

    This is what a plurality rule WOULD return. ``run_jury`` records it as
    ``plurality_finding`` and never promotes it; the probes use it as the coercion control.
    """
    if not ballot_tally:
        return None
    best = max(ballot_tally.values())
    leaders = sorted(label for label, n in ballot_tally.items() if n == best)
    return leaders[0] if len(leaders) == 1 else None


# --------------------------------------------------------------------------- seating


def validate_spec(spec: JurySpec) -> None:
    """Refuse a panel that cannot lawfully be seated (raises ``JurySpecError``)."""
    if not isinstance(spec, JurySpec):
        raise JurySpecError(f"run_jury needs a JurySpec, got {type(spec).__name__}")
    if not spec.jurors:
        raise JurySpecError("a jury needs at least one juror")
    if not isinstance(spec.judge, Judge) or not str(spec.judge.judge_id or "").strip():
        raise JurySpecError("a jury needs a judge with a non-empty judge_id")
    juror_ids = [j.juror_id for j in spec.jurors]
    if any(not str(j or "").strip() for j in juror_ids):
        raise JurySpecError("every juror needs a non-empty juror_id")
    if len(set(juror_ids)) != len(juror_ids):
        raise JurySpecError(f"duplicate juror ids: {sorted(set(juror_ids))}")
    if spec.judge.judge_id in juror_ids:
        raise JurySpecError(
            f"judge {spec.judge.judge_id!r} is seated as a juror; the judge never ballots"
        )
    for juror in spec.jurors:
        if not str(juror.ballot or "").strip():
            raise JurySpecError(f"juror {juror.juror_id!r} cast an empty ballot")
    exhibit_ids = [ex.exhibit_id for ex in spec.exhibits]
    if any(not str(e or "").strip() for e in exhibit_ids):
        raise JurySpecError("every exhibit needs a non-empty exhibit_id")
    if len(set(exhibit_ids)) != len(exhibit_ids):
        raise JurySpecError(f"duplicate exhibit ids: {sorted(set(exhibit_ids))}")
    known = set(exhibit_ids)
    for juror in spec.jurors:
        unknown = [c for c in juror.cites if c not in known]
        if unknown:
            raise JurySpecError(f"juror {juror.juror_id!r} cites unknown exhibits {unknown}")
    tier_rank(spec.evidence_standard)
    decision_threshold(spec.decision_rule, len(spec.jurors))


def run_jury(spec: JurySpec, kernel: RecordingKernel | None = None) -> JuryResult:
    """Seat the panel, rule admissibility, record every brief verbatim, decide from ballots.

    Turn order: the judge's ``admissibility`` ruling, one ``juror-reasoning`` turn per
    juror in panel order (ballot, reasoning copied verbatim, cites split into admitted and
    excluded), then the judge's ``verdict`` turn reading the form. The judge never records
    a ``juror-reasoning`` turn.
    """
    validate_spec(spec)
    log = kernel if kernel is not None else RecordingKernel()
    admitted, excluded = admit_exhibits(spec.exhibits, spec.evidence_standard)
    admitted_set = set(admitted)
    turns: list[dict[str, Any]] = []

    def turn(**fields: Any) -> None:
        rec = {"seq": len(turns) + 1, **fields}
        turns.append(rec)
        log.record(rec)

    turn(
        participant_id=spec.judge.judge_id,
        role="judge",
        kind=TURN_ADMISSIBILITY,
        evidence_standard=spec.evidence_standard,
        admitted=list(admitted),
        excluded=[dict(row) for row in excluded],
    )

    records: list[JurorRecord] = []
    for juror in spec.jurors:
        admitted_cites = [c for c in juror.cites if c in admitted_set]
        excluded_cites = [c for c in juror.cites if c not in admitted_set]
        record = JurorRecord(
            juror_id=juror.juror_id,
            ballot=juror.ballot,
            reasoning=juror.reasoning,
            cites=list(juror.cites),
            admitted_cites=admitted_cites,
            excluded_cites=excluded_cites,
        )
        records.append(record)
        turn(
            participant_id=juror.juror_id,
            role="juror",
            kind=TURN_JUROR_REASONING,
            ballot=juror.ballot,
            reasoning=juror.reasoning,
            cites=list(juror.cites),
            admitted_cites=list(admitted_cites),
            excluded_cites=list(excluded_cites),
        )

    tally = tally_ballots(spec.jurors)
    panel_size = len(spec.jurors)
    threshold = decision_threshold(spec.decision_rule, panel_size)
    plurality = coerce_plurality_finding(tally)
    reached = [label for label, n in tally.items() if n >= threshold]
    if reached:
        outcome_kind, finding, hung_reason = OUTCOME_DECISION, reached[0], ""
    else:
        outcome_kind, finding, hung_reason = OUTCOME_NO_DECISION, None, HUNG_THRESHOLD_NOT_MET

    verdict = Verdict(
        outcome_kind=outcome_kind,
        finding=finding,
        hung_reason=hung_reason,
        ballot_tally=tally,
        decision_rule=spec.decision_rule,
        threshold=threshold,
        panel_size=panel_size,
        juror_ids=[j.juror_id for j in spec.jurors],
        judge_id=spec.judge.judge_id,
        plurality_finding=plurality,
    )
    support = check_verdict_support(verdict, records)
    turn(
        participant_id=spec.judge.judge_id,
        role="judge",
        kind=TURN_VERDICT,
        outcome_kind=outcome_kind,
        finding=finding,
        hung_reason=hung_reason,
        ballot_tally=dict(tally),
        threshold=threshold,
        plurality_finding=plurality,
        support_ok=support.ok,
    )
    return JuryResult(
        question=spec.question,
        verdict=verdict,
        support=support,
        admitted=list(admitted),
        excluded=excluded,
        turns=turns,
        juror_records=records,
    )


# --------------------------------------------------------------------------- support check


def _as_form(verdict: Verdict | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(verdict, Verdict):
        return verdict.to_dict()
    if isinstance(verdict, Mapping):
        return dict(verdict)
    raise TypeError(f"expected a Verdict or mapping, got {type(verdict).__name__}")


def check_verdict_support(
    verdict: Verdict | Mapping[str, Any], juror_records: Iterable[JurorRecord]
) -> SupportReport:
    """Report whether the promoted finding is backed by juror reasoning citing admitted evidence.

    ``supported_by`` lists, per ballot label, the jurors whose record supports that label
    (non-empty reasoning plus at least one admitted cite). A ``DECISION`` whose finding has
    no supporter, or any finding that is not ``None``, is listed in ``unsupported`` and the
    report is not ok. A hung verdict promotes nothing and is ok.
    """
    form = _as_form(verdict)
    supported_by: dict[str, list[str]] = {}
    for record in juror_records:
        if record.supports_ballot():
            supported_by.setdefault(record.ballot, []).append(record.juror_id)
    unsupported: list[UnsupportedFinding] = []
    finding = form.get("finding")
    if form.get("outcome_kind") == OUTCOME_DECISION or finding is not None:
        if not finding or finding not in supported_by:
            unsupported.append(UnsupportedFinding(finding=str(finding)))
    return SupportReport(ok=not unsupported, supported_by=supported_by, unsupported=unsupported)


def plant_unsupported_verdict(source: JuryResult | Verdict, finding: str) -> Verdict:
    """Negative-control constructor: the same verdict form with a finding nobody reasoned toward.

    The tally, panel and rule are left untouched, so the planted form is detectable only by
    ``check_verdict_support`` (and by ``validate_verdict_form``'s ``decision-threshold`` code
    when the planted label was never balloted).
    """
    verdict = source.verdict if isinstance(source, JuryResult) else source
    if not isinstance(verdict, Verdict):
        raise TypeError(f"expected a JuryResult or Verdict, got {type(source).__name__}")
    return dataclasses.replace(
        verdict,
        outcome_kind=OUTCOME_DECISION,
        finding=str(finding),
        hung_reason="",
        ballot_tally=dict(verdict.ballot_tally),
        juror_ids=list(verdict.juror_ids),
    )


# --------------------------------------------------------------------------- verdict form


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def validate_verdict_form(verdict: Verdict | Mapping[str, Any]) -> list[dict[str, str]]:
    """Return the list of ``{"code", "message"}`` defects in a verdict form (empty = valid).

    Codes: ``outcome-kind`` (not DECISION / NO-DECISION), ``decision-finding`` (DECISION
    without a finding), ``decision-threshold`` (finding below its rule's threshold),
    ``decision-hung-reason`` (DECISION carrying a hung reason), ``hung-finding`` (NO-DECISION
    carrying a finding, i.e. a coerced plurality), ``hung-reason`` (NO-DECISION without a
    reason), ``hung-threshold-met`` (a label reached the threshold yet the form is hung),
    ``judge-as-juror``, ``judge-id``, ``juror-ids``, ``tally`` (empty or non-positive counts),
    ``panel-size`` (panel does not match jurors or ballots), ``decision-rule``, ``threshold``.
    """
    form = _as_form(verdict)
    errors: list[dict[str, str]] = []

    def err(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    kind = form.get("outcome_kind")
    if kind not in OUTCOME_KINDS:
        err("outcome-kind", f"outcome_kind must be one of {sorted(OUTCOME_KINDS)}, got {kind!r}")

    tally = form.get("ballot_tally")
    tally_ok = (
        isinstance(tally, Mapping)
        and bool(tally)
        and all(isinstance(k, str) and k and _positive_int(v) for k, v in tally.items())
    )
    if not tally_ok:
        err("tally", "ballot_tally must be a non-empty mapping of ballot label -> positive count")
    counts: dict[str, int] = dict(tally) if tally_ok else {}

    juror_ids = form.get("juror_ids")
    ids_ok = (
        isinstance(juror_ids, (list, tuple))
        and bool(juror_ids)
        and all(isinstance(j, str) and j for j in juror_ids)
    )
    if not ids_ok:
        err("juror-ids", "juror_ids must be a non-empty list of juror id strings")
    elif len(set(juror_ids)) != len(juror_ids):
        err("juror-ids", "juror_ids must be unique")
    seated = list(juror_ids) if ids_ok else []

    judge_id = form.get("judge_id")
    if not isinstance(judge_id, str) or not judge_id:
        err("judge-id", "judge_id must be a non-empty string")
    elif judge_id in seated:
        err(
            "judge-as-juror",
            f"judge {judge_id!r} is seated as a juror; the judge rules admissibility, never ballots",
        )

    panel_size = form.get("panel_size")
    if not _positive_int(panel_size):
        err("panel-size", f"panel_size must be a positive int, got {panel_size!r}")
    else:
        if seated and len(seated) != panel_size:
            err("panel-size", f"panel_size {panel_size} does not match {len(seated)} juror_ids")
        if counts and sum(counts.values()) != panel_size:
            err("panel-size", "ballot_tally must account for every juror exactly once")

    rule = form.get("decision_rule")
    threshold = form.get("threshold")
    if rule not in DECISION_RULES:
        err("decision-rule", f"decision_rule must be one of {list(DECISION_RULES)}, got {rule!r}")
    if not _positive_int(threshold):
        err("threshold", f"threshold must be a positive int, got {threshold!r}")
    elif rule in DECISION_RULES and _positive_int(panel_size):
        want = decision_threshold(rule, panel_size)
        if threshold != want:
            err("threshold", f"threshold {threshold} is not {rule} over {panel_size} (want {want})")
    threshold_n = threshold if _positive_int(threshold) else None

    finding = form.get("finding")
    hung_reason = str(form.get("hung_reason") or "")
    if kind == OUTCOME_DECISION:
        if not isinstance(finding, str) or not finding:
            err("decision-finding", "a DECISION must name its finding")
        elif counts and threshold_n is not None and counts.get(finding, 0) < threshold_n:
            err(
                "decision-threshold",
                f"finding {finding!r} has {counts.get(finding, 0)} ballots, below threshold {threshold_n}",
            )
        if hung_reason:
            err("decision-hung-reason", "a DECISION carries no hung_reason")
    elif kind == OUTCOME_NO_DECISION:
        if finding is not None:
            err("hung-finding", f"a NO-DECISION carries no finding; {finding!r} is a coerced plurality")
        if not hung_reason:
            err("hung-reason", "a NO-DECISION must state its hung_reason")
        if counts and threshold_n is not None and max(counts.values()) >= threshold_n:
            err("hung-threshold-met", "a label reached the threshold; this panel is not hung")
    return errors


# --------------------------------------------------------------------------- fixtures

_PROOF = Exhibit(
    exhibit_id="EX-PROOF-1",
    claim="the binary returns exit 1 on the planted input",
    source_type="executable-proof",
    body="repro: python probe.py --planted",
)
_RUMOR = Exhibit(
    exhibit_id="EX-RUMOR-9",
    claim="someone on the list said the binary is fine",
    source_type="anecdote",
    body="forwarded hallway remark; no reproduction attached",
)
_CONVICT_REASON = "EX-PROOF-1 reproduces the exit-1 failure on the planted input; ballot CONVICT."
_ACQUIT_REASON = (
    "EX-PROOF-1 shows exit 1, but the planted input is outside the documented range; "
    "ballot ACQUIT."
)


def hung_jury_fixture() -> JurySpec:
    """Five jurors split 3 CONVICT / 2 ACQUIT under unanimity: a lawful hung panel.

    EX-RUMOR-9 (anecdote) is offered under the executable-proof-only standard and must be
    excluded; J-5 cites it, so its cite is dropped while EX-PROOF-1 survives.
    """
    return JurySpec(
        question="Does the binary fail on the planted input?",
        exhibits=[_PROOF, _RUMOR],
        jurors=[
            JurorBrief("J-1", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-2", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-3", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-4", "ACQUIT", _ACQUIT_REASON, ("EX-PROOF-1",)),
            JurorBrief(
                "J-5",
                "ACQUIT",
                _ACQUIT_REASON + " EX-RUMOR-9 agrees, for what a rumor is worth.",
                ("EX-PROOF-1", "EX-RUMOR-9"),
            ),
        ],
        judge=Judge("JUDGE-1"),
        evidence_standard=TIER_EXECUTABLE,
        decision_rule=RULE_UNANIMITY,
    )


def tie_hung_fixture() -> JurySpec:
    """Four jurors split 2-2 under majority: no plurality exists and nothing is promoted."""
    return JurySpec(
        question="Does the binary fail on the planted input?",
        exhibits=[_PROOF],
        jurors=[
            JurorBrief("J-1", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-2", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-3", "ACQUIT", _ACQUIT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-4", "ACQUIT", _ACQUIT_REASON, ("EX-PROOF-1",)),
        ],
        judge=Judge("JUDGE-1"),
        evidence_standard=TIER_EXECUTABLE,
        decision_rule=RULE_MAJORITY,
    )


def unanimous_supported_fixture() -> JurySpec:
    """Three jurors, all CONVICT, each citing the admitted proof: a supported DECISION."""
    return JurySpec(
        question="Does the binary fail on the planted input?",
        exhibits=[_PROOF],
        jurors=[
            JurorBrief("J-1", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-2", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
            JurorBrief("J-3", "CONVICT", _CONVICT_REASON, ("EX-PROOF-1",)),
        ],
        judge=Judge("JUDGE-1"),
        evidence_standard=TIER_EXECUTABLE,
        decision_rule=RULE_UNANIMITY,
    )


def empty_reasoning_fixture() -> JurySpec:
    """Unanimous CONVICT ballots with no reasoning: the tally decides, the support check fails."""
    return JurySpec(
        question="Does the binary fail on the planted input?",
        exhibits=[_PROOF],
        jurors=[
            JurorBrief("J-1", "CONVICT", "", ("EX-PROOF-1",)),
            JurorBrief("J-2", "CONVICT", "", ("EX-PROOF-1",)),
            JurorBrief("J-3", "CONVICT", "", ("EX-PROOF-1",)),
        ],
        judge=Judge("JUDGE-1"),
        evidence_standard=TIER_EXECUTABLE,
        decision_rule=RULE_UNANIMITY,
    )


def verdict_form_fixtures() -> dict[str, dict[str, Any]]:
    """Canonical valid forms as plain dicts: one DECISION, one NO-DECISION, both from live runs."""
    return {
        "valid_decision": run_jury(unanimous_supported_fixture()).verdict.to_dict(),
        "valid_hung": run_jury(hung_jury_fixture()).verdict.to_dict(),
    }


__all__ = [
    "DECISION_RULES",
    "EVIDENCE_TIERS",
    "Exhibit",
    "HUNG_THRESHOLD_NOT_MET",
    "Judge",
    "JurorBrief",
    "JurorRecord",
    "JuryResult",
    "JurySpec",
    "JurySpecError",
    "OUTCOME_DECISION",
    "OUTCOME_KINDS",
    "OUTCOME_NO_DECISION",
    "REASON_BELOW_STANDARD",
    "RULE_MAJORITY",
    "RULE_SUPERMAJORITY",
    "RULE_UNANIMITY",
    "RecordingKernel",
    "SUPPORT_NEEDED",
    "SUPPORT_REASON_NONE",
    "SupportReport",
    "TIER_ANY_CITED",
    "TIER_EXECUTABLE",
    "TIER_PEER_REVIEWED",
    "TURN_ADMISSIBILITY",
    "TURN_JUROR_REASONING",
    "TURN_VERDICT",
    "UnsupportedFinding",
    "Verdict",
    "admit_exhibits",
    "check_verdict_support",
    "classify_tier",
    "coerce_plurality_finding",
    "decision_threshold",
    "empty_reasoning_fixture",
    "hung_jury_fixture",
    "plant_unsupported_verdict",
    "run_jury",
    "tally_ballots",
    "tie_hung_fixture",
    "tier_rank",
    "unanimous_supported_fixture",
    "validate_spec",
    "validate_verdict_form",
    "verdict_form_fixtures",
]
