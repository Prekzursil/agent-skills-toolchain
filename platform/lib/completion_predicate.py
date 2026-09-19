"""The ONE shared completion predicate — reference implementation.

Authoritative source of the twelve conditions:
  C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10631-10644 (LF-only
  numbering), transcribed verbatim into
  command-center/COMPLETION-GATES.json -> gate_a_unit_completion_predicate.conditions.

Three hard rules from spec line 10646, each enforced structurally rather than by convention:

  * "Exit code zero alone is never success."  -> condition 1 requires an explicit terminal STATE
    from a closed set and requires that state to be coherent with the sentinel family. A receipt
    carrying only ``exit_code == 0`` cannot reach SATISFIED on condition 1, and conditions 2-12
    are evaluated independently, so no combination of exit codes can produce COMPLETE.
  * "A plausible digest is not a receipt."   -> condition 2 RE-HASHES the bytes on disk and
    compares against the digest the receipt declares. A declared digest is never trusted.
  * "A file path in text is not proof the file exists." -> condition 2 stat()s the resolved path.
    ``artifact.exists`` in the receipt is treated as a CLAIM and, when it contradicts the
    filesystem, is reported as a lying receipt.

Scope, stated so it cannot be over-read: this module implements GATE A (12 conditions, ONE work
unit). It does NOT implement gate B (the 21-condition program stopping rule). COMPLETION-GATES.json
exists specifically to stop those two being conflated; they intersect only at gate B condition 21.

Vocabulary is deliberately aligned to platform/schema/receipt.schema.json ($defs.predicate_report),
authored by the receipt-envelope lane, so that a result produced here can be embedded verbatim as
the ``report`` payload of a predicate_report receipt. Outcomes are SATISFIED / UNSATISFIED /
NOT-APPLICABLE / NOT-CHECKED. NOT-CHECKED is a first-class state distinct from UNSATISFIED
(ARC-0087: "an explicit UNKNOWN state distinct from FALSE") and it BLOCKS completion — an
unmeasured condition is never folded into a pass.

Applicability is a property of the UNIT CLASS supplied by the caller, never a field of the receipt.
A receipt that could declare its own conditions inapplicable would be self-certifying, which is the
failure this predicate exists to prevent. Conditions 1,2,3,4,5,11,12 are NON-WAIVABLE: declaring
one of them inapplicable is reported as UNSATISFIED on that condition, never as a pass.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from vendor_identity import Comparison
from vendor_identity import compare as compare_vendors

__all__ = [
    "ABSOLUTE_MIN_BYTES",
    "CONDITIONS",
    "CONDITION_TEXT",
    "ConditionResult",
    "NON_WAIVABLE",
    "Outcome",
    "PredicateOptions",
    "PredicateResult",
    "REDUCER_ID",
    "Verdict",
    "evaluate",
    "load_receipt",
]

REDUCER_ID = "platform/lib/completion_predicate.py@v1"

SPEC_ANCHOR = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10631-10644"
)

#: The twelve conditions, verbatim from the spec (see COMPLETION-GATES.json for the transcription).
CONDITIONS: tuple[tuple[int, str, int], ...] = (
    (1, "process/task reached a valid terminal state", 10633),
    (2, "expected artifact exists", 10634),
    (3, "artifact is non-empty and exceeds a meaningful minimum size", 10635),
    (4, "artifact parses against its schema", 10636),
    (5, "required sentinel is present", 10637),
    (6, "required evidence anchors exist", 10638),
    (7, "required tests ran and passed", 10639),
    (8, "negative controls or mutations fail as expected", 10640),
    (9, "independent reviewer status is PASS", 10641),
    (10, "no unresolved P0/P1 defect is attached", 10642),
    (11, "output was registered in the artifact manifest", 10643),
    (12, "downstream consumers can read it", 10644),
)
CONDITION_TEXT: dict[int, str] = {n: text for n, text, _ in CONDITIONS}
CONDITION_SPEC_LINE: dict[int, int] = {n: line for n, _, line in CONDITIONS}

#: Conditions that no unit class may waive. Waiving one is reported as UNSATISFIED, not as a pass.
NON_WAIVABLE: frozenset[int] = frozenset({1, 2, 3, 4, 5, 11, 12})

#: Terminal states that are success-class. Every other member of the closed set is a real terminal
#: state that is NOT completion.
SUCCESS_TERMINAL_STATES: frozenset[str] = frozenset({"SUCCESS", "COMPLETED"})

#: Absolute anti-gaming floor for condition 3. ARC-0084 rejects a one-byte floor as "not a real
#: threshold". 64 bytes is below every real artifact measured on this estate (smallest observed:
#: 406 B jsonl, 2,103 B markdown, 2,967 B json - see platform/lib/_derive_size_floors.py output)
#: and far above the degenerate 0/1-byte cases that MSYS redirect-truncation produces.
ABSOLUTE_MIN_BYTES = 64

#: Per-class defaults used only when the receipt declares no threshold at all. Derived from the
#: real on-disk distribution by platform/lib/_derive_size_floors.py: floor = max(64, min/2).
CLASS_SIZE_FLOORS: dict[str, int] = {
    "json": 1483,
    "jsonl": 203,
    "markdown": 1051,
    "other": 64,
}

_ANCHOR_FILE_LINE = re.compile(
    r"^(?P<path>[^\s:]+(?::[^\s:\\/]*)?):(?P<line>\d+)(?:-(?P<end>\d+))?$"
)
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_SENTINEL_ID = re.compile(
    r"^(?:SUCCESS|FAILED|SENTINEL):(?P<uid>[A-Z][A-Z0-9]*-[0-9]{4})\b"
)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class Outcome(str, Enum):
    """Per-condition outcome. Values match receipt.schema.json $defs.predicate_report."""

    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_APPLICABLE = "NOT-APPLICABLE"
    NOT_CHECKED = "NOT-CHECKED"


class Verdict(str, Enum):
    """Overall verdict. Only COMPLETE means done."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class ConditionResult:
    """One condition's typed result, so a caller sees WHICH condition failed and why."""

    n: int
    text: str
    outcome: Outcome
    basis: str
    spec_line: int
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "n": self.n,
            "text": self.text,
            "outcome": self.outcome.value,
            "basis": self.basis,
            "spec_line": self.spec_line,
        }
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass(frozen=True)
class PredicateOptions:
    """Unit-CLASS policy. Supplied by the caller; never read out of the receipt."""

    repo_root: Path
    #: Catalog ``output_schema`` for this unit's primary artifact. None -> condition 4 NOT-CHECKED.
    output_schema: str | None = None
    #: condition -> False marks it inapplicable for this unit class.
    applicability: Mapping[int, bool] = field(default_factory=dict)
    #: condition -> why it is inapplicable. A waiver with no justification is not a waiver.
    applicability_justification: Mapping[int, str] = field(default_factory=dict)
    #: Minimum number of evidence anchors. Default 2: the estate requires two mechanically
    #: independent signals (rules/common/single-signal-verification.md).
    min_evidence_anchors: int = 2
    #: Set when the unit's reviewer_requirement names the other vendor.
    require_cross_vendor_review: bool = False
    require_fresh_context_review: bool = False
    #: Extra roots an evidence anchor may resolve against (e.g. the prompt corpus).
    extra_anchor_roots: tuple[Path, ...] = ()

    def applicable(self, n: int) -> bool:
        return bool(self.applicability.get(n, True))


@dataclass(frozen=True)
class PredicateResult:
    unit_id: str
    reducer_id: str
    verdict: Verdict
    conditions: tuple[ConditionResult, ...]

    @property
    def is_complete(self) -> bool:
        return self.verdict is Verdict.COMPLETE

    def _ns(self, outcome: Outcome) -> list[int]:
        return [c.n for c in self.conditions if c.outcome is outcome]

    @property
    def unsatisfied(self) -> list[int]:
        return self._ns(Outcome.UNSATISFIED)

    @property
    def not_checked(self) -> list[int]:
        return self._ns(Outcome.NOT_CHECKED)

    @property
    def not_applicable(self) -> list[int]:
        return self._ns(Outcome.NOT_APPLICABLE)

    @property
    def satisfied(self) -> list[int]:
        return self._ns(Outcome.SATISFIED)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "satisfied": len(self.satisfied),
            "unsatisfied": len(self.unsatisfied),
            "not_checked": len(self.not_checked),
            "not_applicable": len(self.not_applicable),
        }

    def condition(self, n: int) -> ConditionResult:
        for c in self.conditions:
            if c.n == n:
                return c
        raise KeyError(n)

    @property
    def sentinel_line(self) -> str:
        """Terminal-state marker (AGENTS.md section 4). Never open-ended prose."""
        if self.is_complete:
            return f"SUCCESS:{self.unit_id} predicate=COMPLETE satisfied={len(self.satisfied)}/12"
        reason = f"verdict={self.verdict.value} unsatisfied={self.unsatisfied} not_checked={self.not_checked}"
        return f"FAILED:{self.unit_id} predicate {reason}"

    def to_report(self) -> dict[str, Any]:
        """The ``report`` payload of a predicate_report receipt (receipt.schema.json)."""
        return {
            "kind": "predicate_report",
            "reducer_id": self.reducer_id,
            "spec_anchor": SPEC_ANCHOR,
            "verdict": self.verdict.value,
            "is_complete": self.is_complete,
            "counts": self.counts,
            "unsatisfied": self.unsatisfied,
            "not_checked": self.not_checked,
            "not_applicable": self.not_applicable,
            "sentinel_line": self.sentinel_line,
            "conditions": [c.to_dict() for c in self.conditions],
        }

    def to_dict(self) -> dict[str, Any]:
        return {"unit_id": self.unit_id, **self.to_report()}


# --------------------------------------------------------------------------------------- helpers


def load_receipt(path: str | Path) -> dict[str, Any]:
    """Read a receipt from disk. Always UTF-8: cp1252 is the default on this box and corrupts."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve(root: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute() or _WINDOWS_DRIVE.match(raw):
        return p
    return root / raw


def _sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _digest_match(p: Path, recorded: str) -> tuple[bool, str, str]:
    """Compare a recorded digest against the bytes on disk, EOL-aware.

    Returns ``(matched, mode, worktree_digest)``.

    A naive worktree-bytes comparison is WRONG on this box and was measured to be wrong: of the 13
    checkable entries in command-center/ARTIFACT-MANIFEST.json, ZERO match the working-tree bytes and
    12 match only after CRLF->LF normalisation, because the manifest is rendered from the LF form
    that CI checks out. A digest gate that only compared worktree bytes would fire on every real
    artifact - a false-positive rate of 13/13 - and its operators would learn to ignore it.

    Content identical modulo line endings is not corruption, so an LF match counts, but the MODE is
    always reported so a reader knows which bytes were compared (rules/common/windows-shell.md 8b).
    Only a digest matching neither form is drift.
    """
    worktree = _sha256_of(p)
    if worktree == recorded:
        return (True, "worktree-bytes", worktree)
    try:
        lf = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:  # pragma: no cover - stat already succeeded
        return (False, "unreadable", worktree)
    if lf == recorded:
        return (True, "lf-normalised", worktree)
    return (False, "no-match", worktree)


def _artifacts(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = receipt.get("artifacts")
    return [a for a in raw if isinstance(a, dict)] if isinstance(raw, list) else []


def _primaries(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    arts = _artifacts(receipt)
    primary = [a for a in arts if a.get("role") == "primary"]
    return primary or arts


def _seq(value: Any) -> list[Any]:
    return [x for x in value] if isinstance(value, (list, tuple)) else []


def _text_of(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------- condition evaluators


def _c1_terminal_state(
    receipt: Mapping[str, Any],
) -> tuple[Outcome, str, dict[str, Any]]:
    state = receipt.get("state")
    sentinel = receipt.get("sentinel")
    detail: dict[str, Any] = {"state": state, "sentinel": sentinel}
    if not isinstance(state, str) or not state:
        return (
            Outcome.UNSATISFIED,
            "no terminal state declared; exit code zero alone is never success (spec line 10646)",
            detail,
        )
    if state not in SUCCESS_TERMINAL_STATES:
        return (
            Outcome.UNSATISFIED,
            f"terminal state {state!r} is a real terminal state but is not success-class "
            f"{sorted(SUCCESS_TERMINAL_STATES)}",
            detail,
        )
    # Coherence: a success-class state may not carry a FAILED sentinel family.
    if isinstance(sentinel, str) and sentinel.startswith("FAILED:"):
        return (
            Outcome.UNSATISFIED,
            f"incoherent receipt: state={state} but sentinel family is FAILED",
            detail,
        )
    if not isinstance(sentinel, str) or not sentinel:
        return (
            Outcome.UNSATISFIED,
            "success-class state with no sentinel declared",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"state={state} is success-class and coherent with sentinel family "
        f"{sentinel.split(':', 1)[0]}",
        detail,
    )


def _c2_artifact_exists(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    prims = _primaries(receipt)
    detail: dict[str, Any] = {"checked": []}
    if not prims:
        return (Outcome.UNSATISFIED, "receipt declares no artifacts", detail)
    for art in prims:
        raw = art.get("path")
        if not isinstance(raw, str) or not raw:
            return (Outcome.UNSATISFIED, "artifact entry carries no path", detail)
        p = _resolve(opts.repo_root, raw)
        row: dict[str, Any] = {"path": raw, "resolved": str(p)}
        if not p.is_file():
            row["exists_on_disk"] = False
            detail["checked"].append(row)
            claim = art.get("exists")
            lie = " (receipt claims exists=true)" if claim is True else ""
            return (
                Outcome.UNSATISFIED,
                f"stat says absent: {p}{lie} - a file path in text is not proof the file exists",
                detail,
            )
        row["exists_on_disk"] = True
        real_bytes = p.stat().st_size
        row["bytes_on_disk"] = real_bytes
        declared_bytes = art.get("bytes")
        if isinstance(declared_bytes, int) and declared_bytes != real_bytes:
            row["declared_bytes"] = declared_bytes
            detail["checked"].append(row)
            return (
                Outcome.UNSATISFIED,
                f"declared bytes {declared_bytes} != {real_bytes} on disk for {raw}",
                detail,
            )
        declared_sha = art.get("sha256")
        if isinstance(declared_sha, str) and _SHA256_HEX.match(declared_sha):
            matched, mode, actual = _digest_match(p, declared_sha)
            row["sha256_recomputed"] = actual
            row["digest_match_mode"] = mode
            if not matched:
                row["sha256_declared"] = declared_sha
                detail["checked"].append(row)
                return (
                    Outcome.UNSATISFIED,
                    f"re-hash mismatch for {raw}: declared {declared_sha[:12]} != "
                    f"recomputed {actual[:12]} (neither worktree nor LF-normalised bytes match) "
                    "- a plausible digest is not a receipt",
                    detail,
                )
        detail["checked"].append(row)
    return (
        Outcome.SATISFIED,
        f"{len(prims)} primary artifact(s) stat()ed present and re-hashed against the receipt",
        detail,
    )


def _c3_min_size(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    prims = _primaries(receipt)
    declared = receipt.get("min_bytes_threshold")
    detail: dict[str, Any] = {"declared_min_bytes_threshold": declared}
    if not prims:
        return (Outcome.NOT_CHECKED, "no artifacts to size", detail)

    missing = [
        a.get("path")
        for a in prims
        if not _resolve(opts.repo_root, str(a.get("path", ""))).is_file()
    ]
    if missing:
        return (
            Outcome.NOT_CHECKED,
            f"artifact absent, size not measurable: {missing[0]!r} (condition 2 owns this failure)",
            detail,
        )

    if not isinstance(declared, int) or declared <= 0:
        cls = str(prims[0].get("artifact_class") or "other")
        return (
            Outcome.UNSATISFIED,
            "no min_bytes_threshold declared; an undeclared threshold makes 'exceeds a meaningful "
            f"minimum' unfalsifiable (class default would be {CLASS_SIZE_FLOORS.get(cls, ABSOLUTE_MIN_BYTES)})",
            detail,
        )

    effective = max(declared, ABSOLUTE_MIN_BYTES)
    detail["effective_min_bytes"] = effective
    if effective != declared:
        detail["weak_threshold_declared"] = True
        detail["note"] = (
            f"declared threshold {declared} is below the absolute floor {ABSOLUTE_MIN_BYTES}; "
            "ARC-0084 rejects a one-byte floor as not a real threshold, so the floor was raised"
        )
    for art in prims:
        p = _resolve(opts.repo_root, str(art.get("path")))
        n = p.stat().st_size
        if n == 0:
            return (Outcome.UNSATISFIED, f"{art.get('path')} is 0 bytes", detail)
        if n < effective:
            return (
                Outcome.UNSATISFIED,
                f"{art.get('path')} is {n} bytes, below the effective minimum {effective}",
                detail,
            )
    return (
        Outcome.SATISFIED,
        f"every primary artifact is non-empty and >= {effective} bytes",
        detail,
    )


def _c4_parses_against_schema(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    prims = _primaries(receipt)
    detail: dict[str, Any] = {"output_schema": opts.output_schema}
    if not prims:
        return (Outcome.NOT_CHECKED, "no artifacts to parse", detail)
    paths = [_resolve(opts.repo_root, str(a.get("path"))) for a in prims]
    if any(not p.is_file() for p in paths):
        return (
            Outcome.NOT_CHECKED,
            "artifact absent, cannot parse (condition 2 owns this failure)",
            detail,
        )
    if not opts.output_schema:
        return (
            Outcome.NOT_CHECKED,
            "no output_schema supplied by the caller; settling experiment: pass the unit's "
            "catalog output_schema into PredicateOptions.output_schema",
            detail,
        )
    schema_path = _resolve(opts.repo_root, opts.output_schema)
    detail["schema_resolved"] = str(schema_path)
    if not schema_path.is_file():
        return (
            Outcome.NOT_CHECKED,
            f"declared schema does not exist on disk: {schema_path} - a missing schema is "
            "NOT-CHECKED, never a pass",
            detail,
        )
    try:
        import jsonschema  # noqa: PLC0415 - optional dependency, absence must be NOT-CHECKED
    except ImportError:  # pragma: no cover - measured separately
        return (
            Outcome.NOT_CHECKED,
            "jsonschema is not installed; cannot validate",
            detail,
        )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return (
            Outcome.NOT_CHECKED,
            f"declared schema is unreadable/unparsable: {exc}",
            detail,
        )

    results: list[dict[str, Any]] = []
    for art, p in zip(prims, paths, strict=True):
        cls = str(
            art.get("artifact_class") or ("json" if p.suffix == ".json" else "other")
        )
        if p.suffix.lower() not in {".json", ".jsonl"} and cls not in {"json", "jsonl"}:
            results.append(
                {
                    "path": str(art.get("path")),
                    "outcome": "NOT-CHECKED",
                    "why": "not JSON-bearing",
                }
            )
            continue
        try:
            instance = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            detail["results"] = results
            return (
                Outcome.UNSATISFIED,
                f"{art.get('path')} does not parse as JSON: {exc}",
                detail,
            )
        try:
            jsonschema.validate(instance, schema)
        except jsonschema.ValidationError as exc:
            detail["results"] = results
            detail["validation_error"] = str(exc).splitlines()[0]
            loc = "/".join(str(x) for x in exc.absolute_path) or "<root>"
            return (
                Outcome.UNSATISFIED,
                f"{art.get('path')} fails its schema at {loc}: {exc.message}",
                detail,
            )
        except jsonschema.SchemaError as exc:
            detail["results"] = results
            return (
                Outcome.NOT_CHECKED,
                f"declared schema is not a valid JSON Schema: {exc.message}",
                detail,
            )
        results.append({"path": str(art.get("path")), "outcome": "SATISFIED"})
    detail["results"] = results
    if results and all(r["outcome"] == "NOT-CHECKED" for r in results):
        return (
            Outcome.NOT_CHECKED,
            "no JSON-bearing primary artifact to validate",
            detail,
        )
    return (Outcome.SATISFIED, f"validated against {opts.output_schema}", detail)


def _c5_sentinel_present(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    sentinel = receipt.get("sentinel")
    unit_id = receipt.get("unit_id")
    detail: dict[str, Any] = {"sentinel": sentinel}
    if not isinstance(sentinel, str) or not sentinel:
        return (Outcome.UNSATISFIED, "no sentinel declared", detail)

    m = _SENTINEL_ID.match(sentinel)
    if not m:
        return (
            Outcome.UNSATISFIED,
            f"sentinel {sentinel[:60]!r} matches no known family "
            "(SUCCESS:<ID> / FAILED:<ID> / SENTINEL:<ID>:<TOKEN>)",
            detail,
        )
    embedded = m.group("uid")
    detail["embedded_unit_id"] = embedded
    if isinstance(unit_id, str) and embedded != unit_id:
        return (
            Outcome.UNSATISFIED,
            f"sentinel is for {embedded} but this receipt is for {unit_id}",
            detail,
        )

    prims = _primaries(receipt)
    if not prims:
        return (Outcome.UNSATISFIED, "no artifact to carry the sentinel", detail)
    checked = 0
    for art in prims:
        p = _resolve(opts.repo_root, str(art.get("path")))
        if not p.is_file():
            return (
                Outcome.NOT_CHECKED,
                "artifact absent, sentinel not measurable (condition 2 owns this failure)",
                detail,
            )
        if str(art.get("artifact_class")) == "binary":
            continue
        text = _text_of(p)
        if text is None:
            return (
                Outcome.NOT_CHECKED,
                f"{art.get('path')} is not UTF-8 text; sentinel not searchable",
                detail,
            )
        checked += 1
        if sentinel not in text:
            return (
                Outcome.UNSATISFIED,
                f"{art.get('path')} exists but does not carry the sentinel - an artifact "
                "without its sentinel is INCOMPLETE (spec failure class, line 11313)",
                detail,
            )
    if checked == 0:
        return (
            Outcome.NOT_CHECKED,
            "no text-bearing primary artifact to search",
            detail,
        )
    detail["artifacts_searched"] = checked
    return (
        Outcome.SATISFIED,
        f"sentinel found verbatim in {checked} primary artifact(s)",
        detail,
    )


def _anchor_resolves(anchor: str, opts: PredicateOptions) -> tuple[bool, str]:
    m = _ANCHOR_FILE_LINE.match(anchor.strip())
    if not m:
        return (False, "not a file:line anchor")
    raw = m.group("path")
    line = int(m.group("line"))
    roots = (opts.repo_root, *opts.extra_anchor_roots)
    for root in roots:
        p = _resolve(root, raw)
        if p.is_file():
            try:
                n = len(p.read_bytes().split(b"\n"))
            except OSError as exc:  # pragma: no cover
                return (False, f"unreadable: {exc}")
            if line <= n:
                return (True, f"{p} has {n} lines >= {line}")
            return (False, f"{p} has only {n} lines, anchor cites {line}")
    return (False, f"path {raw!r} not found under {[str(r) for r in roots]}")


def _c6_evidence_anchors(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    items = [x for x in _seq(receipt.get("evidence")) if isinstance(x, dict)]
    detail: dict[str, Any] = {
        "required": opts.min_evidence_anchors,
        "found": len(items),
    }
    if len(items) < opts.min_evidence_anchors:
        return (
            Outcome.UNSATISFIED,
            f"{len(items)} evidence item(s) < required {opts.min_evidence_anchors} "
            "(two mechanically independent signals)",
            detail,
        )

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        anchor = item.get("anchor")
        row: dict[str, Any] = {"i": idx, "anchor": anchor}
        if not isinstance(anchor, str) or not anchor.strip():
            detail["items"] = rows
            return (Outcome.UNSATISFIED, f"evidence[{idx}] has no anchor", detail)

        probes = [p for p in _seq(item.get("probes")) if isinstance(p, dict)]
        row["probes"] = len(probes)
        if not probes:
            detail["items"] = rows
            return (Outcome.UNSATISFIED, f"evidence[{idx}] declares no probe", detail)

        by_role: dict[str, list[dict[str, Any]]] = {}
        for pr in probes:
            by_role.setdefault(str(pr.get("role")), []).append(pr)
        sources = by_role.get("source", [])
        verifiers = by_role.get("verifier", [])

        # The measured claim_gate.py hole: an absent/empty source normalises to empty strings that
        # any non-empty verifier trivially differs from, so same-probe-rerun cannot fire and the
        # gate certifies corroboration for a claim declaring no producing measurement at all.
        if not sources or not str(sources[0].get("command") or "").strip():
            detail["items"] = rows
            return (
                Outcome.UNSATISFIED,
                f"evidence[{idx}] declares no non-empty SOURCE probe; an undeclared source is "
                "zero signals, not one",
                detail,
            )

        verdict = item.get("verdict")
        if verdict in {"CONFIRMED", "REFUTED"}:
            if not verifiers:
                detail["items"] = rows
                return (
                    Outcome.UNSATISFIED,
                    f"evidence[{idx}] verdict={verdict} with no VERIFIER probe",
                    detail,
                )
            s_fp = str(sources[0].get("fingerprint") or "")
            v_fp = str(verifiers[0].get("fingerprint") or "")
            row["source_fingerprint"] = s_fp
            row["verifier_fingerprint"] = v_fp
            if not s_fp or not v_fp:
                detail["items"] = rows
                return (
                    Outcome.UNSATISFIED,
                    f"evidence[{idx}] probe fingerprint is empty",
                    detail,
                )
            if s_fp == v_fp:
                detail["items"] = rows
                return (
                    Outcome.UNSATISFIED,
                    f"evidence[{idx}] same-probe-rerun: source and verifier fingerprints are "
                    f"identical ({s_fp[:16]}); re-running the same probe is not a second signal",
                    detail,
                )
            if str(sources[0].get("method")) == str(verifiers[0].get("method")):
                detail["items"] = rows
                return (
                    Outcome.UNSATISFIED,
                    f"evidence[{idx}] source and verifier share method "
                    f"{sources[0].get('method')!r}; two probes of the same mechanism class are "
                    "not independent",
                    detail,
                )

        if (
            item.get("unverified") is True
            and not str(item.get("settling_experiment") or "").strip()
        ):
            detail["items"] = rows
            return (
                Outcome.UNSATISFIED,
                f"evidence[{idx}] is UNVERIFIED with no named settling experiment",
                detail,
            )

        ok, why = _anchor_resolves(anchor, opts)
        row["anchor_resolves"] = ok
        row["anchor_basis"] = why
        if not ok and why == "not a file:line anchor":
            raw_out = "".join(str(pr.get("raw_output") or "") for pr in probes)
            if not raw_out.strip():
                detail["items"] = rows
                return (
                    Outcome.UNSATISFIED,
                    f"evidence[{idx}] anchor {anchor[:60]!r} is a command/URL and no probe "
                    "carries verbatim raw_output",
                    detail,
                )
            row["anchor_basis"] = "command/URL anchor backed by verbatim probe output"
        elif not ok:
            detail["items"] = rows
            return (
                Outcome.UNSATISFIED,
                f"evidence[{idx}] anchor does not resolve: {why}",
                detail,
            )
        rows.append(row)

    detail["items"] = rows
    return (
        Outcome.SATISFIED,
        f"{len(items)} evidence anchors resolve and carry probe pairs",
        detail,
    )


def _c7_tests(receipt: Mapping[str, Any]) -> tuple[Outcome, str, dict[str, Any]]:
    tests = [t for t in _seq(receipt.get("tests")) if isinstance(t, dict)]
    detail: dict[str, Any] = {"count": len(tests)}
    if "tests" not in receipt:
        return (
            Outcome.NOT_CHECKED,
            "receipt declares no tests key; a missing test record is NOT-CHECKED, never a pass",
            detail,
        )
    if not tests:
        return (
            Outcome.UNSATISFIED,
            "tests list is empty; no required test ran",
            detail,
        )
    bad: list[dict[str, Any]] = []
    for t in tests:
        res = t.get("result")
        if res != "PASS":
            bad.append({"id": t.get("id"), "result": res})
        elif not str(t.get("command") or "").strip():
            bad.append(
                {
                    "id": t.get("id"),
                    "result": res,
                    "why": "PASS with no command is unverifiable",
                }
            )
    if bad:
        detail["failing"] = bad
        return (
            Outcome.UNSATISFIED,
            f"{len(bad)} of {len(tests)} test records are not a verifiable PASS: {bad[:3]}",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"{len(tests)} test record(s), all PASS with a re-runnable command",
        detail,
    )


def _c8_negative_controls(
    receipt: Mapping[str, Any],
) -> tuple[Outcome, str, dict[str, Any]]:
    controls = [
        c for c in _seq(receipt.get("negative_controls")) if isinstance(c, dict)
    ]
    detail: dict[str, Any] = {"count": len(controls)}
    if "negative_controls" not in receipt:
        return (
            Outcome.NOT_CHECKED,
            "receipt declares no negative_controls key",
            detail,
        )
    if not controls:
        return (
            Outcome.UNSATISFIED,
            "no negative control: a detector that was never run against a known-broken state "
            "measures nothing",
            detail,
        )
    bad: list[dict[str, Any]] = []
    for c in controls:
        fired = c.get("fired_on_bad_state")
        silent = c.get("silent_on_good_state")
        if fired is not True or silent is not True:
            bad.append(
                {
                    "id": c.get("id"),
                    "fired_on_bad_state": fired,
                    "silent_on_good_state": silent,
                }
            )
    if bad:
        detail["failing"] = bad
        return (
            Outcome.UNSATISFIED,
            f"{len(bad)} control(s) failed the both-states rule: {bad[:3]} - a probe silent in "
            "both states measures nothing, one that fires in both over-fires",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"{len(controls)} control(s) each fired on the bad state and stayed silent on the good one",
        detail,
    )


def _c9_reviewer(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    rv = receipt.get("reviewer")
    detail: dict[str, Any] = {}
    if not isinstance(rv, dict):
        return (
            Outcome.NOT_CHECKED,
            "no reviewer record; absence of a review is NOT-CHECKED, never a pass",
            detail,
        )
    detail.update(
        {
            "reviewer_id": rv.get("reviewer_id"),
            "verdict": rv.get("verdict"),
            "independent": rv.get("independent"),
            "vendor": rv.get("vendor"),
        }
    )
    if rv.get("verdict") != "PASS":
        return (
            Outcome.UNSATISFIED,
            f"reviewer verdict is {rv.get('verdict')!r}, not PASS",
            detail,
        )
    if rv.get("independent") is not True:
        return (
            Outcome.UNSATISFIED,
            "reviewer is not marked independent; self-review is not review",
            detail,
        )
    produced = (
        receipt.get("produced_by")
        if isinstance(receipt.get("produced_by"), dict)
        else {}
    )
    if opts.require_cross_vendor_review:
        # DEFECT D1: this used to be `rev_vendor == exec_vendor` over free text, which accepted
        # 10/10 same-vendor ALIAS pairs (anthropic/claude, openai/codex, google/gemini, and a
        # trailing space) as cross-vendor. Comparison now runs on CANONICAL identity resolved
        # against platform/registry/VENDOR-REGISTRY.json, and a vendor string that does not
        # resolve is REJECTED as NOT-CHECKED instead of being promoted to "distinct" merely for
        # differing. NOT-CHECKED blocks completion, so an unregistered vendor cannot pass.
        comparison, vendor_reason, vendor_detail = compare_vendors(
            produced.get("vendor"), rv.get("vendor")
        )
        detail["vendor_comparison"] = comparison.value
        detail["vendor_identity"] = vendor_detail
        if comparison is Comparison.NOT_COMPUTABLE:
            return (
                Outcome.NOT_CHECKED,
                f"unit requires a cross-vendor reviewer but {vendor_reason}",
                detail,
            )
        if comparison is Comparison.SAME_VENDOR:
            return (
                Outcome.UNSATISFIED,
                f"unit requires a cross-vendor reviewer; {vendor_reason}",
                detail,
            )
    if opts.require_fresh_context_review and rv.get("fresh_context") is not True:
        return (
            Outcome.UNSATISFIED,
            "unit requires a fresh-context reviewer; not recorded",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"independent reviewer {rv.get('reviewer_id')!r} returned PASS",
        detail,
    )


def _c10_defects(receipt: Mapping[str, Any]) -> tuple[Outcome, str, dict[str, Any]]:
    defects = [d for d in _seq(receipt.get("defects")) if isinstance(d, dict)]
    detail: dict[str, Any] = {"count": len(defects)}
    if not defects:
        return (Outcome.SATISFIED, "no defect is attached to this unit", detail)
    unsevered = [d.get("id") for d in defects if d.get("severity") in (None, "")]
    if unsevered:
        detail["defects_without_severity"] = unsevered
        return (
            Outcome.NOT_CHECKED,
            f"{len(unsevered)} attached defect(s) carry no severity, so 'no unresolved P0/P1' is "
            "not computable (the same gap COMPLETION-GATES.json records for CLAIM-REGISTRY.json). "
            "Settling experiment: backfill severity, then recount",
            detail,
        )
    blocking = [
        {"id": d.get("id"), "severity": d.get("severity"), "status": d.get("status")}
        for d in defects
        if d.get("severity") in {"P0", "P1"}
        and d.get("status")
        not in {
            "resolved",
            "waived-by-owner",
            "superseded",
            "closed",
            "externally-blocked-proven",
        }
    ]
    if blocking:
        detail["blocking"] = blocking
        return (
            Outcome.UNSATISFIED,
            f"{len(blocking)} unresolved P0/P1 defect(s): {blocking}",
            detail,
        )
    waived = [d.get("id") for d in defects if d.get("status") == "waived-by-owner"]
    if waived:
        detail["waived_by_owner"] = waived
    return (
        Outcome.SATISFIED,
        f"{len(defects)} attached defect(s), none an unresolved P0/P1",
        detail,
    )


def _c11_manifest(
    receipt: Mapping[str, Any], opts: PredicateOptions
) -> tuple[Outcome, str, dict[str, Any]]:
    reg = receipt.get("manifest_registration")
    detail: dict[str, Any] = {}
    if not isinstance(reg, dict):
        return (Outcome.UNSATISFIED, "no manifest_registration record", detail)
    detail["claimed_registered"] = reg.get("registered")
    manifest_rel = reg.get("manifest_path")
    if not isinstance(manifest_rel, str) or not manifest_rel:
        return (
            Outcome.UNSATISFIED,
            "manifest_registration declares no manifest_path",
            detail,
        )
    mp = _resolve(opts.repo_root, manifest_rel)
    detail["manifest_resolved"] = str(mp)
    if not mp.is_file():
        return (
            Outcome.NOT_CHECKED,
            f"manifest not found at {mp}; registration is not measurable",
            detail,
        )
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return (
            Outcome.NOT_CHECKED,
            f"manifest is unreadable/unparsable: {exc}",
            detail,
        )

    entries = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        return (Outcome.NOT_CHECKED, "manifest has no artifacts array", detail)
    index: dict[str, dict[str, Any]] = {}
    for e in entries:
        if isinstance(e, dict) and isinstance(e.get("path"), str):
            index[e["path"].replace("\\", "/")] = e

    rows: list[dict[str, Any]] = []
    for art in _primaries(receipt):
        raw = str(art.get("path") or "").replace("\\", "/")
        entry = index.get(raw)
        row: dict[str, Any] = {"path": raw, "in_manifest": entry is not None}
        if entry is None:
            detail["rows"] = rows + [row]
            return (
                Outcome.UNSATISFIED,
                f"{raw!r} is not registered in {manifest_rel}; an artifact on disk but "
                "unregistered is not complete (ARC-0084)",
                detail,
            )
        recorded = entry.get("sha256")
        p = _resolve(opts.repo_root, raw)
        if isinstance(recorded, str) and _SHA256_HEX.match(recorded) and p.is_file():
            matched, mode, actual = _digest_match(p, recorded)
            row["manifest_sha256_matches"] = matched
            row["digest_match_mode"] = mode
            if not matched:
                detail["rows"] = rows + [row]
                return (
                    Outcome.UNSATISFIED,
                    f"manifest digest drift for {raw}: recorded {recorded[:12]} != "
                    f"recomputed {actual[:12]}, and the LF-normalised form does not match either "
                    "- this is real drift, not a CRLF artifact",
                    detail,
                )
            if mode == "lf-normalised":
                row["why"] = (
                    "matched only after CRLF->LF normalisation; the manifest hashed the LF form "
                    "that CI checks out (rules/common/windows-shell.md 8b)"
                )
        elif isinstance(recorded, str):
            row["manifest_sha256_matches"] = None
            row["why"] = (
                f"manifest records non-hex digest {recorded[:16]!r}; digest check skipped"
            )
        rows.append(row)

    # CC-0009 / ARC-0084 reverse check: every registered entry must exist on disk.
    # A path string in the manifest is not proof the file exists; registered-but-absent
    # must fail condition 11 rather than pass on the strength of the registration row.
    # Primary paths named by THIS receipt are owned by condition 2 (and cascade to 3/4/5
    # as NOT-CHECKED); skipping them keeps the mutation battery's isolation honest.
    primary_paths = {
        str(a.get("path") or "").replace("\\", "/") for a in _primaries(receipt)
    }
    reverse_rows: list[dict[str, Any]] = []
    for e in entries:
        if not isinstance(e, dict) or not isinstance(e.get("path"), str):
            continue
        if e.get("present") is False:
            continue
        mpath = e["path"].replace("\\", "/")
        if mpath in primary_paths:
            continue
        resolved = _resolve(opts.repo_root, mpath)
        rev: dict[str, Any] = {"path": mpath, "exists_on_disk": resolved.is_file()}
        if not resolved.is_file():
            reverse_rows.append(rev)
            detail["rows"] = rows
            detail["manifest_entry_existence"] = reverse_rows
            return (
                Outcome.UNSATISFIED,
                f"registered-but-absent: manifest lists {mpath!r} but stat says missing "
                "- a file path in text is not proof the file exists",
                detail,
            )
        reverse_rows.append(rev)
    detail["rows"] = rows
    detail["manifest_entry_existence"] = reverse_rows
    if reg.get("registered") is not True:
        return (
            Outcome.UNSATISFIED,
            "receipt itself records registered=false",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"every primary artifact is registered in {manifest_rel} and every "
        f"manifest entry exists on disk",
        detail,
    )


def _c12_downstream(receipt: Mapping[str, Any]) -> tuple[Outcome, str, dict[str, Any]]:
    consumers = [
        c for c in _seq(receipt.get("downstream_consumers")) if isinstance(c, dict)
    ]
    detail: dict[str, Any] = {"count": len(consumers)}
    if not consumers:
        return (
            Outcome.UNSATISFIED,
            "no downstream consumer declared; condition 12 is non-waivable, and a condition with "
            "no declared subject is decorative (the ADV-0001 attack)",
            detail,
        )
    unexecuted = [c.get("consumer") for c in consumers if c.get("executed") is not True]
    if unexecuted:
        detail["not_executed"] = unexecuted
        return (
            Outcome.NOT_CHECKED,
            f"{len(unexecuted)} declared consumer(s) were never executed: {unexecuted[:3]} - a "
            "claim that a consumer can read the artifact is not a measurement",
            detail,
        )
    bad: list[dict[str, Any]] = []
    for c in consumers:
        exit_code = c.get("exit_code")
        probe = c.get("probe") if isinstance(c.get("probe"), dict) else {}
        if c.get("read_ok") is not True:
            bad.append({"consumer": c.get("consumer"), "why": "read_ok is not true"})
        elif isinstance(exit_code, int) and exit_code != 0:
            bad.append({"consumer": c.get("consumer"), "why": f"exit_code={exit_code}"})
        elif not str(probe.get("raw_output") or "").strip():
            bad.append(
                {
                    "consumer": c.get("consumer"),
                    "why": "probe carries no verbatim output",
                }
            )
    if bad:
        detail["failing"] = bad
        return (
            Outcome.UNSATISFIED,
            f"{len(bad)} consumer(s) could not read the artifact: {bad[:3]}",
            detail,
        )
    return (
        Outcome.SATISFIED,
        f"{len(consumers)} consumer(s) executed against the artifact and read it (exit 0)",
        detail,
    )


# ------------------------------------------------------------------------------------ the reducer


def _waiver(n: int, opts: PredicateOptions) -> ConditionResult | None:
    """Return a condition result when the unit class waives ``n``, else None."""
    if opts.applicable(n):
        return None
    text = CONDITION_TEXT[n]
    line = CONDITION_SPEC_LINE[n]
    if n in NON_WAIVABLE:
        return ConditionResult(
            n,
            text,
            Outcome.UNSATISFIED,
            f"condition {n} is NON-WAIVABLE but the unit class declared it inapplicable; a waiver "
            "of a structural condition is a failure of that condition, never a pass",
            line,
            {"non_waivable": True},
        )
    why = str(opts.applicability_justification.get(n) or "").strip()
    if not why:
        return ConditionResult(
            n,
            text,
            Outcome.UNSATISFIED,
            f"condition {n} declared inapplicable with no justification; a waiver with no "
            "justification is not a waiver",
            line,
            {"waiver_justified": False},
        )
    return ConditionResult(
        n,
        text,
        Outcome.NOT_APPLICABLE,
        f"declared inapplicable for this unit class: {why}",
        line,
        {"waiver_justified": True},
    )


def evaluate(receipt: Mapping[str, Any], opts: PredicateOptions) -> PredicateResult:
    """Evaluate all twelve conditions. Total function: never raises on a malformed receipt.

    A malformed or hostile receipt yields UNSATISFIED / NOT-CHECKED per condition, never an
    exception and never COMPLETE. An UNSATISFIED or NOT-CHECKED on any condition blocks
    completion; NOT-APPLICABLE is never counted as a pass.
    """
    if not isinstance(
        receipt, Mapping
    ):  # defensive: callers pass parsed JSON of unknown shape
        receipt = {}
    unit_id = receipt.get("unit_id")
    unit_id = unit_id if isinstance(unit_id, str) and unit_id else "UNKNOWN-0000"

    evaluators: dict[int, Any] = {
        1: lambda: _c1_terminal_state(receipt),
        2: lambda: _c2_artifact_exists(receipt, opts),
        3: lambda: _c3_min_size(receipt, opts),
        4: lambda: _c4_parses_against_schema(receipt, opts),
        5: lambda: _c5_sentinel_present(receipt, opts),
        6: lambda: _c6_evidence_anchors(receipt, opts),
        7: lambda: _c7_tests(receipt),
        8: lambda: _c8_negative_controls(receipt),
        9: lambda: _c9_reviewer(receipt, opts),
        10: lambda: _c10_defects(receipt),
        11: lambda: _c11_manifest(receipt, opts),
        12: lambda: _c12_downstream(receipt),
    }

    results: list[ConditionResult] = []
    for n, text, line in CONDITIONS:
        waived = _waiver(n, opts)
        if waived is not None:
            results.append(waived)
            continue
        try:
            outcome, basis, detail = evaluators[n]()
        except Exception as exc:  # noqa: BLE001 - a reducer crash must not read as completion
            results.append(
                ConditionResult(
                    n,
                    text,
                    Outcome.NOT_CHECKED,
                    f"evaluator raised {type(exc).__name__}: {exc}",
                    line,
                    {"evaluator_error": True},
                )
            )
            continue
        results.append(ConditionResult(n, text, outcome, basis, line, detail))

    conds = tuple(results)
    if any(c.outcome is Outcome.UNSATISFIED for c in conds):
        verdict = Verdict.INCOMPLETE
    elif any(c.outcome is Outcome.NOT_CHECKED for c in conds):
        verdict = Verdict.INDETERMINATE
    else:
        verdict = Verdict.COMPLETE
    return PredicateResult(unit_id, REDUCER_ID, verdict, conds)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python completion_predicate.py <receipt.json> [--repo-root R] [--output-schema S]``.

    Exit 0 only on COMPLETE. Prints the terminal-state marker on the last line.
    """
    import argparse

    ap = argparse.ArgumentParser(
        description="Evaluate the shared 12-condition completion predicate."
    )
    ap.add_argument("receipt")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--output-schema", default=None)
    ap.add_argument("--require-cross-vendor-review", action="store_true")
    ap.add_argument("--min-evidence-anchors", type=int, default=2)
    ap.add_argument("--anchor-root", action="append", default=[])
    ap.add_argument(
        "--na",
        action="append",
        default=[],
        metavar="N=WHY",
        help="mark condition N inapplicable with a justification",
    )
    ns = ap.parse_args(list(argv) if argv is not None else None)

    applicability: dict[int, bool] = {}
    justification: dict[int, str] = {}
    for spec in ns.na:
        num, _, why = spec.partition("=")
        try:
            k = int(num)
        except ValueError:
            print(f"FAILED:cli bad --na {spec!r}")
            return 2
        applicability[k] = False
        justification[k] = why
    opts = PredicateOptions(
        repo_root=Path(ns.repo_root),
        output_schema=ns.output_schema,
        applicability=applicability,
        applicability_justification=justification,
        min_evidence_anchors=ns.min_evidence_anchors,
        require_cross_vendor_review=ns.require_cross_vendor_review,
        extra_anchor_roots=tuple(Path(r) for r in ns.anchor_root),
    )
    try:
        receipt = load_receipt(ns.receipt)
    except (OSError, ValueError) as exc:
        print(f"FAILED:cli receipt unreadable: {exc}")
        return 2
    result = evaluate(receipt, opts)
    print(json.dumps(result.to_dict(), indent=2))
    print(result.sentinel_line)
    return 0 if result.is_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
