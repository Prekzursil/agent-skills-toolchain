"""Retry-policy engine driven by typed failure class, not raw error text.

IMP-0448. The catalog question is the contract:

* schema-invalid is retried ZERO times
* a provider transient may retry up to the catalog cap
* a second failure on the SAME fingerprint PIVOTs (required_fix named)
  rather than taking a third identical attempt

decide() takes a history of TypedFailure plus a RetryPolicy. TypedFailure
has no text field. Raw strings are the classifier's problem (IMP-0449);
once a class token exists, this module never greps it.

Stdlib-only. Does not sleep; backoff values are recorded, not executed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

# Closed set from IMP-0449's catalog question_or_target, plus UNCLASSIFIED.
TAXONOMY_CLASSES: tuple[str, ...] = (
    "severed-stream",
    "adapter-exit-n",
    "win-arg-limit",
    "timeout",
    "schema-invalid",
    "partial-artifact",
    "degraded",
    "blocked",
)
UNCLASSIFIED = "UNCLASSIFIED"

PROVIDER_TRANSIENT: frozenset[str] = frozenset(
    {"severed-stream", "adapter-exit-n", "timeout"}
)
LIMITED: frozenset[str] = frozenset({"partial-artifact"})
NEVER_RETRY: frozenset[str] = frozenset(
    {
        "schema-invalid",
        "blocked",
        "win-arg-limit",
        "degraded",
        UNCLASSIFIED,
    }
)

KIND_TRANSIENT = "provider-transient"
KIND_LIMITED = "limited"
KIND_NEVER = "never"

LIMITED_ATTEMPTS = 2
SAFETY_MAX_ATTEMPTS = 8
DEFAULT_BACKOFF: tuple[int, ...] = (30, 120)
PIVOT_REQUIRED_FIX = "enumerate-alternative-approaches"

REASON_ZERO = "zero-retry-class"
REASON_CAP = "at-class-or-catalog-cap"
REASON_PIVOT = "two-strikes-same-fingerprint"
REASON_RETRY = "within-class-and-catalog-cap"

_MAX_ATTEMPTS_RE = re.compile(r"max(?:imum)?\s+(\d+)\s+attempts", re.I)
_ZERO_RETRY_RE = re.compile(r"zero\s+retries|no\s+automatic\s+retry", re.I)
_TRANSIENT_ONLY_RE = re.compile(r"transients?\s+only", re.I)
_BACKOFF_RE = re.compile(
    r"backoff\s+(\d+)\s*s(?:\s*/\s*(\d+)\s*s)+",
    re.I,
)
_BACKOFF_NUM_RE = re.compile(r"(\d+)\s*s", re.I)


@dataclass(frozen=True)
class TypedFailure:
    """One observed failure. Class token + structural fingerprint only."""

    failure_class: str
    fingerprint: str


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF
    two_strikes_pivot: bool = True
    transient_only: bool = False
    raw: str = ""

    def __post_init__(self) -> None:
        cap = int(self.max_attempts)
        if cap < 1:
            cap = 1
        if cap > SAFETY_MAX_ATTEMPTS:
            cap = SAFETY_MAX_ATTEMPTS
        object.__setattr__(self, "max_attempts", cap)
        backoff = self.backoff_seconds
        if backoff is None:
            backoff = ()
        object.__setattr__(self, "backoff_seconds", tuple(int(x) for x in backoff))


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str = ""
    required_fix: str | None = None
    failure_class: str = ""
    fingerprint: str = ""
    attempt_count: int = 0
    same_fingerprint_count: int = 0
    configured_policy: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "required_fix": self.required_fix,
            "failure_class": self.failure_class,
            "fingerprint": self.fingerprint,
            "attempt_count": self.attempt_count,
            "same_fingerprint_count": self.same_fingerprint_count,
            "configured_policy": self.configured_policy,
        }


@dataclass(frozen=True)
class Observation:
    failure_class: str
    kind: str
    configured_policy: int
    observed_attempt_count: int
    actions: tuple[str, ...]
    terminal_action: str
    terminal_reason: str
    required_fix: str | None
    match: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_class": self.failure_class,
            "kind": self.kind,
            "configured_policy": self.configured_policy,
            "observed_attempt_count": self.observed_attempt_count,
            "actions": list(self.actions),
            "terminal_action": self.terminal_action,
            "terminal_reason": self.terminal_reason,
            "required_fix": self.required_fix,
            "match": self.match,
        }


def normalize_class(token: str) -> str:
    raw = (token or "").strip()
    if raw in TAXONOMY_CLASSES:
        return raw
    if raw == UNCLASSIFIED or raw.upper() == UNCLASSIFIED:
        return UNCLASSIFIED
    return UNCLASSIFIED


def class_kind(token: str) -> str:
    cls = normalize_class(token)
    if cls in PROVIDER_TRANSIENT:
        return KIND_TRANSIENT
    if cls in LIMITED:
        return KIND_LIMITED
    return KIND_NEVER


def configured_attempts(token: str, policy: RetryPolicy) -> int:
    """Attempts this class is allowed under policy, including the first try.

    never          -> 1 (zero retries)
    limited        -> min(2, catalog cap)
    transient      -> catalog cap
    transient_only -> non-transients collapse to 1
    """
    catalog = min(max(1, policy.max_attempts), SAFETY_MAX_ATTEMPTS)
    kind = class_kind(token)
    if kind == KIND_NEVER:
        return 1
    if policy.transient_only and kind != KIND_TRANSIENT:
        return 1
    if kind == KIND_LIMITED:
        return min(LIMITED_ATTEMPTS, catalog)
    return catalog


def parse_retry_policy(raw: str) -> RetryPolicy:
    """Parse a catalog retry_policy prose string into RetryPolicy.

    Defaults (when the prose names a retry budget but not the details):
    max_attempts=3, backoff 30s/120s, two_strikes_pivot on if attempts>1.
    Zero-retry / no-automatic language forces max_attempts=1 and empty backoff.
    """
    text = raw or ""
    max_attempts = 3
    if _ZERO_RETRY_RE.search(text):
        max_attempts = 1
    found = _MAX_ATTEMPTS_RE.search(text)
    if found:
        max_attempts = int(found.group(1))
    max_attempts = max(1, min(max_attempts, SAFETY_MAX_ATTEMPTS))

    backoff: tuple[int, ...]
    bmatch = _BACKOFF_RE.search(text)
    if bmatch:
        span = text[bmatch.start() : bmatch.end()]
        nums = [int(n) for n in _BACKOFF_NUM_RE.findall(span)]
        backoff = tuple(nums) if nums else DEFAULT_BACKOFF
    elif max_attempts > 1:
        backoff = DEFAULT_BACKOFF
    else:
        backoff = ()

    return RetryPolicy(
        max_attempts=max_attempts,
        backoff_seconds=backoff,
        two_strikes_pivot=max_attempts > 1,
        transient_only=bool(_TRANSIENT_ONLY_RE.search(text)),
        raw=text,
    )


def _same_fingerprint_count(history: Sequence[TypedFailure]) -> int:
    if not history:
        return 0
    latest = history[-1].fingerprint
    return sum(1 for item in history if item.fingerprint == latest)


def decide(history: Sequence[TypedFailure], policy: RetryPolicy) -> Decision:
    """Pure function of typed class + fingerprint history + policy.

    Order (first match wins):
    1. zero-retry class -> STOP
    2. two-strikes on the same fingerprint -> PIVOT with required_fix
    3. class or catalog cap (or safety cap) -> STOP
    4. otherwise RETRY
    """
    if not history:
        return Decision(action="RETRY", reason=REASON_RETRY, attempt_count=0)

    latest = history[-1]
    cls = normalize_class(latest.failure_class)
    cap = configured_attempts(cls, policy)
    n = len(history)
    same = _same_fingerprint_count(history)

    if cap <= 1:
        return Decision(
            action="STOP",
            reason=REASON_ZERO,
            required_fix=None,
            failure_class=cls,
            fingerprint=latest.fingerprint,
            attempt_count=n,
            same_fingerprint_count=same,
            configured_policy=cap,
        )

    if policy.two_strikes_pivot and same >= 2:
        return Decision(
            action="PIVOT",
            reason=REASON_PIVOT,
            required_fix=PIVOT_REQUIRED_FIX,
            failure_class=cls,
            fingerprint=latest.fingerprint,
            attempt_count=n,
            same_fingerprint_count=same,
            configured_policy=cap,
        )

    if n >= cap or n >= SAFETY_MAX_ATTEMPTS:
        return Decision(
            action="STOP",
            reason=REASON_CAP,
            required_fix=None,
            failure_class=cls,
            fingerprint=latest.fingerprint,
            attempt_count=n,
            same_fingerprint_count=same,
            configured_policy=cap,
        )

    return Decision(
        action="RETRY",
        reason=REASON_RETRY,
        required_fix=None,
        failure_class=cls,
        fingerprint=latest.fingerprint,
        attempt_count=n,
        same_fingerprint_count=same,
        configured_policy=cap,
    )


def observe_attempts(
    token: str,
    policy: RetryPolicy,
    *,
    distinct_fingerprints: bool = False,
    fingerprint: str | None = None,
) -> Observation:
    """Grind one class until STOP/PIVOT. Does not sleep."""
    cls = normalize_class(token)
    kind = class_kind(cls)
    cap = configured_attempts(cls, policy)
    base_fp = fingerprint or f"{cls}-fp"
    history: list[TypedFailure] = []
    actions: list[str] = []
    last = Decision(action="STOP", reason=REASON_ZERO)

    for i in range(1, SAFETY_MAX_ATTEMPTS + 1):
        fp = f"{base_fp}-{i}" if distinct_fingerprints else base_fp
        history.append(TypedFailure(failure_class=cls, fingerprint=fp))
        last = decide(history, policy)
        actions.append(last.action)
        if last.action != "RETRY":
            break

    observed = len(actions)
    if last.action == "PIVOT":
        match = (
            observed == 2
            and last.required_fix == PIVOT_REQUIRED_FIX
            and last.reason == REASON_PIVOT
        )
    else:
        match = (
            observed == cap
            and last.action == "STOP"
            and last.reason in {REASON_ZERO, REASON_CAP}
        )

    return Observation(
        failure_class=cls,
        kind=kind,
        configured_policy=cap,
        observed_attempt_count=observed,
        actions=tuple(actions),
        terminal_action=last.action,
        terminal_reason=last.reason,
        required_fix=last.required_fix,
        match=match,
    )


def decision_table(
    policy: RetryPolicy,
    *,
    distinct_fingerprints: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cls in (*TAXONOMY_CLASSES, UNCLASSIFIED):
        obs = observe_attempts(
            cls, policy, distinct_fingerprints=distinct_fingerprints
        )
        rows.append(obs.as_dict())
    return rows


def table_is_sound(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Any class whose observed count differs from its policy is a defect.

    Callers must feed distinct-fingerprint rows; two-strikes is a different
    probe and is allowed to stop early with PIVOT.
    """
    errors: list[str] = []
    by_cls = {
        str(row.get("failure_class")): row
        for row in rows
        if isinstance(row, dict)
    }
    expected = list(TAXONOMY_CLASSES) + [UNCLASSIFIED]
    for cls in expected:
        row = by_cls.get(cls)
        if row is None:
            errors.append(f"missing-class:{cls}")
            continue
        observed = row.get("observed_attempt_count")
        configured = row.get("configured_policy")
        if observed != configured:
            errors.append(
                f"count-mismatch:{cls} observed={observed} policy={configured}"
            )
        if row.get("match") is not True:
            errors.append(f"match-false:{cls}")
    extra = set(by_cls) - set(expected)
    if extra:
        errors.append(f"extra-classes:{sorted(extra)}")
    return errors


def two_strikes_demo() -> dict[str, Any]:
    """Same fingerprint PIVOTs at strike two; distinct fingerprints reach cap."""
    policy = RetryPolicy(
        max_attempts=3,
        backoff_seconds=DEFAULT_BACKOFF,
        two_strikes_pivot=True,
        raw="max 3 attempts, backoff 30s/120s",
    )
    same = observe_attempts(
        "severed-stream",
        policy,
        distinct_fingerprints=False,
        fingerprint="sev-same",
    )
    distinct = observe_attempts(
        "severed-stream",
        policy,
        distinct_fingerprints=True,
        fingerprint="sev-dist",
    )
    invalid = observe_attempts(
        "schema-invalid",
        policy,
        distinct_fingerprints=False,
        fingerprint="inv-same",
    )
    same_d = same.as_dict()
    dist_d = distinct.as_dict()
    inv_d = invalid.as_dict()
    return {
        "did_not_take_third_attempt": (
            same.observed_attempt_count == 2 and same.terminal_action == "PIVOT"
        ),
        "distinct_fingerprints": dist_d,
        "distinct_reaches_catalog_cap": (
            distinct.observed_attempt_count == 3
            and distinct.terminal_action == "STOP"
            and distinct.terminal_reason == REASON_CAP
        ),
        "pivot_at_strike_two": (
            same.terminal_action == "PIVOT"
            and same.observed_attempt_count == 2
            and same.required_fix == PIVOT_REQUIRED_FIX
        ),
        "same_fingerprint": same_d,
        "schema_invalid_same_fp": inv_d,
        "schema_invalid_zero_retries": invalid.observed_attempt_count == 1,
    }


def class_overrides_decoy_text() -> dict[str, Any]:
    """Decoy error string is recorded here and is not an input to decide()."""
    decoy = "timeout: connection reset; HTTP 429; schema looks invalid"
    policy = RetryPolicy(
        max_attempts=3,
        backoff_seconds=DEFAULT_BACKOFF,
        two_strikes_pivot=True,
    )
    invalid = decide(
        [TypedFailure(failure_class="schema-invalid", fingerprint="decoy-pair")],
        policy,
    )
    transient = decide(
        [TypedFailure(failure_class="severed-stream", fingerprint="decoy-pair")],
        policy,
    )
    diverged = invalid.action != transient.action
    return {
        "decoy_text": decoy,
        "decoy_text_not_passed_to_decide": True,
        "schema_invalid_action": invalid.action,
        "severed_stream_action": transient.action,
        "schema_invalid_is_stop": invalid.action == "STOP",
        "severed_stream_is_retry": transient.action == "RETRY",
        "diverged": diverged,
    }
