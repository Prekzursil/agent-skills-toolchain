"""Receipt validation + the 12-condition unit-completion predicate.

Two layers, deliberately separate:

  LAYER 1  validate_receipt()   - JSON Schema structural validation against
                                  platform/schema/receipt.schema.json (or one of
                                  its $defs fragments).
  LAYER 2  evaluate_gate_a()    - the 12-condition predicate from
                                  command-center/COMPLETION-GATES.json
                                  (gate_a_unit_completion_predicate, spec lines
                                  10631-10644).

Layer 1 is NOT layer 2. A schema-valid receipt can still fail the predicate:
eight obligations are cross-field or filesystem facts that JSON Schema provably
cannot express, and they are enforced here --

  1. the sentinel embeds THIS unit's id
  2. every primary artifact exceeds the DECLARED min_bytes_threshold
  3. the recorded sha256 equals the hash of the bytes on disk
  4. the artifact path actually exists
  5. the source and verifier probe fingerprints are mechanically DIFFERENT
  6. started_at <= ended_at
  7. duration_seconds agrees with the timestamp delta
  8. a downstream consumer was EXECUTED, not merely claimed

Reporting a schema pass as a completion verdict is the exact defect ADV-0001
attacks (is condition 12 evaluated, or decorative?). It is decorative unless
layer 2 runs.

NOT-CHECKED is never folded into a pass: any condition that could not be
evaluated leaves the receipt incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012
except ImportError as exc:  # pragma: no cover - dependency presence is a setup fact
    raise SystemExit(
        "receipt_gate requires the 'jsonschema' package (>=4.18 for the "
        f"referencing API). Import failed: {exc}"
    ) from exc

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema" / "receipt.schema.json"

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
NOT_APPLICABLE = "NOT-APPLICABLE"
NOT_CHECKED = "NOT-CHECKED"

#: Condition text taken verbatim from command-center/COMPLETION-GATES.json.
CONDITION_TEXT: dict[int, str] = {
    1: "process/task reached a valid terminal state",
    2: "expected artifact exists",
    3: "artifact is non-empty and exceeds a meaningful minimum size",
    4: "artifact parses against its schema",
    5: "required sentinel is present",
    6: "required evidence anchors exist",
    7: "required tests ran and passed",
    8: "negative controls or mutations fail as expected",
    9: "independent reviewer status is PASS",
    10: "no unresolved P0/P1 defect is attached",
    11: "output was registered in the artifact manifest",
    12: "downstream consumers can read it",
}

#: Hard rules from the same gate (spec line 10646). Kept as data so a caller
#: cannot quietly reinterpret them.
HARD_RULES: tuple[str, ...] = (
    "Exit code zero alone is never success.",
    "A plausible digest is not a receipt.",
    "A file path in text is not proof the file exists.",
)

_TERMINAL_STATES = {
    "SUCCESS",
    "FAILED",
    "BLOCKED",
    "SEVERED",
    "TIMEOUT",
    "SUPERSEDED",
    "DROPPED-BY-OWNER",
}


@dataclass(frozen=True)
class ConditionOutcome:
    n: int
    text: str
    outcome: str
    basis: str

    @property
    def blocking(self) -> bool:
        """True when this condition prevents completion.

        NOT-CHECKED blocks: an unevaluated condition is not a pass.
        """
        return self.outcome in (UNSATISFIED, NOT_CHECKED)


@dataclass
class GateResult:
    unit_id: str
    state: str
    conditions: list[ConditionOutcome] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """ALL applicable conditions must hold (gate quantifier)."""
        if self.schema_errors:
            return False
        if len(self.conditions) != 12:
            return False
        return not any(c.blocking for c in self.conditions)

    @property
    def blocking_conditions(self) -> list[ConditionOutcome]:
        return [c for c in self.conditions if c.blocking]

    def marker(self) -> str:
        """Terminal-state marker: never open-ended prose."""
        if self.complete:
            return f"SUCCESS:{self.unit_id}"
        if self.schema_errors:
            reason = f"schema-invalid ({len(self.schema_errors)} error(s))"
        else:
            failed = ",".join(f"c{c.n}={c.outcome}" for c in self.blocking_conditions)
            reason = f"predicate-unsatisfied {failed}"
        return f"FAILED:{self.unit_id} {reason}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "state": self.state,
            "complete": self.complete,
            "marker": self.marker(),
            "schema_errors": self.schema_errors,
            "conditions": [
                {"n": c.n, "text": c.text, "outcome": c.outcome, "basis": c.basis}
                for c in self.conditions
            ],
            "hard_rules": list(HARD_RULES),
        }


# --------------------------------------------------------------------------- #
# Layer 1: schema validation
# --------------------------------------------------------------------------- #


def load_schema(path: Path | str = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def build_validator(
    schema: dict[str, Any] | None = None, fragment: str | None = None
) -> Draft202012Validator:
    """Build a validator for the whole receipt or for one ``$defs`` fragment.

    ``fragment`` accepts the forms used verbatim in the work-unit catalog, e.g.
    ``"#/$defs/security_report"``, ``"/$defs/security_report"`` or
    ``"security_report"``.
    """
    schema = schema if schema is not None else load_schema()
    registry = Registry().with_resource(
        schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
    )
    if fragment is None:
        return Draft202012Validator(schema, registry=registry)

    frag = fragment.lstrip("#")
    if not frag.startswith("/"):
        frag = f"/$defs/{frag}"
    if frag.startswith("/$defs/"):
        name = frag.split("/")[-1]
        if name not in schema.get("$defs", {}):
            raise KeyError(f"no such fragment in receipt schema: {frag}")
    return Draft202012Validator({"$ref": schema["$id"] + "#" + frag}, registry=registry)


def validate_receipt(
    receipt: Any,
    schema: dict[str, Any] | None = None,
    fragment: str | None = None,
) -> list[str]:
    """Return a sorted list of human-readable schema errors ('' means valid)."""
    validator = build_validator(schema, fragment)
    out: list[str] = []
    for err in validator.iter_errors(receipt):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def parse_schema_ref(output_schema: str) -> tuple[str, str | None]:
    """Split a catalog ``output_schema`` value into (schema file, fragment).

    The catalog carries decorated forms -- a ``profile=...`` suffix, a
    ``#/$defs/...`` pointer, or ``a.json + b.json`` co-references. Only the
    receipt-schema part is returned; the fragment is None when absent.
    """
    text = (output_schema or "").strip()
    head = text.split(" profile=")[0].split(" + ")[0].split(" (")[0].strip()
    if "#" in head:
        base, frag = head.split("#", 1)
        return base.strip(), "#" + frag.strip()
    return head, None


# --------------------------------------------------------------------------- #
# Layer 2: the 12-condition predicate
# --------------------------------------------------------------------------- #


def _iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _primary_artifacts(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    arts = [a for a in receipt.get("artifacts", []) if isinstance(a, dict)]
    primary = [a for a in arts if a.get("role", "primary") == "primary"]
    return primary or arts


def evaluate_gate_a(
    receipt: Any,
    repo_root: Path | str | None = None,
    verify_filesystem: bool = True,
    schema: dict[str, Any] | None = None,
    fragment: str | None = None,
) -> GateResult:
    """Compute the 12-condition unit-completion predicate for one receipt.

    ``verify_filesystem=False`` makes conditions 2 and 3 report NOT-CHECKED
    rather than silently passing -- an unrunnable probe is not a pass.
    """
    schema_errors = validate_receipt(receipt, schema=schema, fragment=fragment)
    if not isinstance(receipt, dict):
        return GateResult(unit_id="<unparseable>", state="<none>", schema_errors=schema_errors or ["root: not an object"])

    unit_id = str(receipt.get("unit_id", "<missing>"))
    state = str(receipt.get("state", "<missing>"))
    root = Path(repo_root) if repo_root is not None else None
    cond: list[ConditionOutcome] = []

    def add(n: int, outcome: str, basis: str) -> None:
        cond.append(ConditionOutcome(n, CONDITION_TEXT[n], outcome, basis))

    # --- 1. valid terminal state ------------------------------------------- #
    if state in _TERMINAL_STATES:
        if state == "SUCCESS":
            add(1, SATISFIED, "state=SUCCESS")
        else:
            add(1, UNSATISFIED, f"state={state} is terminal but not a completion")
    else:
        add(1, UNSATISFIED, f"state={state!r} is not a recognised terminal state")

    arts = _primary_artifacts(receipt)

    # --- 2. artifact exists ------------------------------------------------ #
    if not arts:
        add(2, UNSATISFIED, "no artifacts recorded")
    elif not verify_filesystem:
        add(2, NOT_CHECKED, "filesystem verification disabled; a path in text is not proof")
    elif root is None:
        add(2, NOT_CHECKED, "no repo_root supplied, cannot resolve relative artifact paths")
    else:
        missing = [a["path"] for a in arts if not (root / a["path"]).is_file()]
        if missing:
            add(2, UNSATISFIED, f"absent on disk: {missing}")
        else:
            add(2, SATISFIED, f"{len(arts)} artifact(s) stat-confirmed under {root}")

    # --- 3. non-empty AND exceeds the declared minimum --------------------- #
    threshold = receipt.get("min_bytes_threshold")
    if not isinstance(threshold, int) or threshold < 1:
        add(3, UNSATISFIED, "min_bytes_threshold absent or < 1; 'meaningful minimum' is unfalsifiable")
    elif not arts:
        add(3, UNSATISFIED, "no artifacts recorded")
    else:
        undersize = [
            f"{a['path']}={a.get('bytes')}<{threshold}"
            for a in arts
            if not isinstance(a.get("bytes"), int) or a["bytes"] < threshold
        ]
        if undersize:
            add(3, UNSATISFIED, f"below declared threshold: {undersize}")
        elif not verify_filesystem or root is None:
            add(3, NOT_CHECKED, "declared sizes accepted but not measured off disk")
        else:
            mismatched = []
            for a in arts:
                p = root / a["path"]
                if not p.is_file():
                    mismatched.append(f"{a['path']}: absent")
                    continue
                actual = p.stat().st_size
                if actual != a["bytes"]:
                    mismatched.append(f"{a['path']}: declared {a['bytes']} != on-disk {actual}")
                    continue
                digest = _sha256_file(p)
                if digest != a.get("sha256"):
                    mismatched.append(f"{a['path']}: sha256 mismatch (on-disk {digest[:12]}...)")
            if mismatched:
                add(3, UNSATISFIED, f"declared bytes/sha256 disagree with disk: {mismatched}")
            else:
                add(3, SATISFIED, f"all primary artifacts >= {threshold} B, sizes and sha256 re-measured")

    # --- 4. parses against its schema -------------------------------------- #
    if schema_errors:
        add(4, UNSATISFIED, f"{len(schema_errors)} schema error(s); first: {schema_errors[0][:200]}")
    else:
        add(4, SATISFIED, f"validates against {SCHEMA_PATH.name}" + (f"{fragment}" if fragment else ""))

    # --- 5. sentinel present AND names this unit --------------------------- #
    sentinel = receipt.get("sentinel")
    if not isinstance(sentinel, str) or not sentinel:
        add(5, UNSATISFIED, "sentinel absent")
    elif unit_id not in sentinel:
        add(5, UNSATISFIED, f"sentinel does not embed unit_id {unit_id!r}: {sentinel[:80]!r}")
    elif sentinel.startswith("FAILED:"):
        add(5, UNSATISFIED, "sentinel is a FAILED marker")
    else:
        add(5, SATISFIED, f"sentinel embeds {unit_id}")

    # --- 6. evidence anchors, with an independent probe pair --------------- #
    ev = [e for e in receipt.get("evidence", []) if isinstance(e, dict)]
    if len(ev) < 2:
        add(6, UNSATISFIED, f"{len(ev)} evidence item(s); two mechanically independent signals required")
    else:
        problems: list[str] = []
        for i, item in enumerate(ev):
            probes = [p for p in item.get("probes", []) if isinstance(p, dict)]
            roles = {p.get("role") for p in probes}
            if item.get("verdict") in ("CONFIRMED", "REFUTED"):
                if "source" not in roles:
                    problems.append(f"evidence[{i}]: no source probe (undeclared source = zero signals)")
                if "verifier" not in roles:
                    problems.append(f"evidence[{i}]: no verifier probe")
                srcs = {p.get("fingerprint") for p in probes if p.get("role") == "source"}
                vers = {p.get("fingerprint") for p in probes if p.get("role") == "verifier"}
                if srcs & vers:
                    problems.append(f"evidence[{i}]: same-probe-rerun, fingerprints overlap {sorted(srcs & vers)}")
                methods_s = {p.get("method") for p in probes if p.get("role") == "source"}
                methods_v = {p.get("method") for p in probes if p.get("role") == "verifier"}
                if methods_s and methods_v and methods_s == methods_v:
                    problems.append(
                        f"evidence[{i}]: source and verifier share method {sorted(methods_s)}; not mechanically independent"
                    )
            if item.get("unverified") and not item.get("settling_experiment"):
                problems.append(f"evidence[{i}]: UNVERIFIED with no settling experiment")
            if not item.get("anchor"):
                problems.append(f"evidence[{i}]: no anchor")
        if problems:
            add(6, UNSATISFIED, "; ".join(problems[:6]))
        else:
            add(6, SATISFIED, f"{len(ev)} anchored evidence item(s), source/verifier pairs independent")

    # --- 7. required tests ran and passed ---------------------------------- #
    tests = [t for t in receipt.get("tests", []) if isinstance(t, dict)]
    if not tests:
        add(7, UNSATISFIED, "no tests recorded")
    else:
        bad = [f"{t.get('id')}={t.get('result')}" for t in tests if t.get("result") != "PASS"]
        if bad:
            add(7, UNSATISFIED, f"non-PASS results (SKIP/NOT-RUN are not passes): {bad[:8]}")
        else:
            add(7, SATISFIED, f"{len(tests)} test(s) PASS")

    # --- 8. negative controls fail as expected (both-states) --------------- #
    ctrls = [c for c in receipt.get("negative_controls", []) if isinstance(c, dict)]
    if not ctrls:
        add(8, UNSATISFIED, "no negative control; a detector unproven against a known-broken state measures nothing")
    else:
        bad = []
        for c in ctrls:
            if c.get("fired_on_bad_state") is not True:
                bad.append(f"{c.get('id')}: did not fire on bad state (inert detector)")
            if c.get("silent_on_good_state") is not True:
                bad.append(f"{c.get('id')}: not silent on good state (over-fires)")
        if bad:
            add(8, UNSATISFIED, "; ".join(bad[:6]))
        else:
            add(8, SATISFIED, f"{len(ctrls)} both-states control(s) fired on bad and silent on good")

    # --- 9. independent reviewer PASS -------------------------------------- #
    rev = receipt.get("reviewer")
    if not isinstance(rev, dict):
        add(9, UNSATISFIED, "no reviewer block")
    elif rev.get("verdict") != "PASS":
        add(9, UNSATISFIED, f"reviewer verdict={rev.get('verdict')!r}")
    elif rev.get("independent") is not True:
        add(9, UNSATISFIED, "reviewer not independent (self-review is not review)")
    elif rev.get("reviewer_id") and rev.get("reviewer_id") == (receipt.get("produced_by") or {}).get("role"):
        add(9, UNSATISFIED, "reviewer_id equals the producing role")
    else:
        add(9, SATISFIED, f"independent reviewer {rev.get('reviewer_id')} PASS")

    # --- 10. no unresolved P0/P1 ------------------------------------------- #
    defects = [d for d in receipt.get("defects", []) if isinstance(d, dict)]
    open_high = [
        d.get("id")
        for d in defects
        if d.get("severity") in ("P0", "P1") and d.get("status") == "open"
    ]
    if open_high:
        add(10, UNSATISFIED, f"open P0/P1 defect(s): {open_high}")
    else:
        add(10, SATISFIED, f"{len(defects)} defect(s) recorded, none open at P0/P1")

    # --- 11. registered in the artifact manifest --------------------------- #
    reg = receipt.get("manifest_registration")
    if not isinstance(reg, dict):
        add(11, UNSATISFIED, "no manifest_registration block")
    elif reg.get("registered") is not True:
        add(11, UNSATISFIED, "manifest_registration.registered is not true")
    elif verify_filesystem and root is not None and not (root / str(reg.get("manifest_path"))).is_file():
        add(11, UNSATISFIED, f"manifest absent on disk: {reg.get('manifest_path')}")
    else:
        add(11, SATISFIED, f"registered in {reg.get('manifest_path')}")

    # --- 12. downstream consumers can read it ----------------------------- #
    cons = [c for c in receipt.get("downstream_consumers", []) if isinstance(c, dict)]
    if not cons:
        add(12, UNSATISFIED, "no downstream consumer probe; condition 12 would be decorative")
    else:
        bad = []
        for c in cons:
            if c.get("executed") is not True:
                bad.append(f"{c.get('consumer')}: not executed (claim only)")
            elif c.get("read_ok") is not True:
                bad.append(f"{c.get('consumer')}: read_ok false")
            elif not isinstance(c.get("probe"), dict) or not c["probe"].get("raw_output"):
                bad.append(f"{c.get('consumer')}: no raw probe output")
        art_paths = {a.get("path") for a in receipt.get("artifacts", []) if isinstance(a, dict)}
        unconsumed = {c.get("artifact_path") for c in cons} - art_paths
        if unconsumed:
            bad.append(f"consumer references artifact(s) not in this receipt: {sorted(unconsumed)}")
        if bad:
            add(12, UNSATISFIED, "; ".join(bad[:6]))
        else:
            add(12, SATISFIED, f"{len(cons)} consumer(s) executed and read the artifact")

    cond.sort(key=lambda c: c.n)
    return GateResult(unit_id=unit_id, state=state, conditions=cond, schema_errors=schema_errors)


def check_timestamps(receipt: dict[str, Any]) -> list[str]:
    """Cross-field timestamp coherence (schema cannot compare two fields)."""
    problems: list[str] = []
    ts = receipt.get("timestamps")
    if not isinstance(ts, dict):
        return ["timestamps absent"]
    start, end = _iso(ts.get("started_at", "")), _iso(ts.get("ended_at", ""))
    if start is None:
        problems.append("started_at unparseable")
    if end is None:
        problems.append("ended_at unparseable")
    if start and end:
        if end < start:
            problems.append(f"ended_at {ts['ended_at']} precedes started_at {ts['started_at']}")
        declared = ts.get("duration_seconds")
        if isinstance(declared, (int, float)):
            actual = (end - start).total_seconds()
            if abs(actual - declared) > max(1.0, 0.02 * actual):
                problems.append(f"duration_seconds={declared} disagrees with delta {actual:.1f}s")
    return problems


def check_retry_policy(receipt: dict[str, Any]) -> list[str]:
    """Two-strikes: a third attempt on the same fingerprint needs alternatives."""
    problems: list[str] = []
    retry = receipt.get("retry")
    if not isinstance(retry, dict):
        return ["retry absent"]
    attempts = [a for a in retry.get("attempts", []) if isinstance(a, dict)]
    fps = [a.get("error_fingerprint") for a in attempts if a.get("error_fingerprint")]
    repeated = {fp for fp in fps if fps.count(fp) >= 2}
    if repeated and len(retry.get("pivot_alternatives") or []) < 2:
        problems.append(
            f"two strikes on {sorted(repeated)} without >=2 enumerated pivot alternatives"
        )
    count = retry.get("count")
    if isinstance(count, int) and attempts and count > len(attempts):
        problems.append(f"retry.count={count} exceeds recorded attempts={len(attempts)}")
    return problems


def evaluate_full(
    receipt: Any,
    repo_root: Path | str | None = None,
    verify_filesystem: bool = True,
    fragment: str | None = None,
) -> tuple[GateResult, list[str]]:
    """Gate A plus the coherence checks that are not numbered conditions."""
    result = evaluate_gate_a(
        receipt, repo_root=repo_root, verify_filesystem=verify_filesystem, fragment=fragment
    )
    extra: list[str] = []
    if isinstance(receipt, dict):
        extra += check_timestamps(receipt)
        extra += check_retry_policy(receipt)
    return result, extra


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate a work-unit receipt and evaluate the 12-condition completion predicate."
    )
    ap.add_argument("receipt", nargs="+", help="path(s) to receipt JSON")
    ap.add_argument("--repo-root", default=None, help="root for resolving artifact paths")
    ap.add_argument("--no-fs", action="store_true", help="skip filesystem checks (conditions 2/3 -> NOT-CHECKED)")
    ap.add_argument("--fragment", default=None, help="validate against a $defs fragment, e.g. security_report")
    ap.add_argument("--schema-only", action="store_true", help="layer 1 only; does NOT imply completion")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)

    worst = 0
    payloads = []
    for path in args.receipt:
        p = Path(path)
        try:
            receipt = json.loads(p.read_bytes().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED:<unparseable> {p}: {type(exc).__name__}: {exc}")
            worst = 1
            continue

        if args.schema_only:
            errs = validate_receipt(receipt, fragment=args.fragment)
            uid = receipt.get("unit_id", "<missing>") if isinstance(receipt, dict) else "<missing>"
            if errs:
                print(f"FAILED:{uid} schema-invalid ({len(errs)} error(s))")
                for e in errs[:20]:
                    print(f"    - {e}")
                worst = 1
            else:
                print(f"SCHEMA-VALID:{uid} (layer 1 only - this is NOT a completion verdict)")
            payloads.append({"unit_id": uid, "schema_errors": errs})
            continue

        result, extra = evaluate_full(
            receipt,
            repo_root=args.repo_root,
            verify_filesystem=not args.no_fs,
            fragment=args.fragment,
        )
        d = result.to_dict()
        d["coherence_problems"] = extra
        payloads.append(d)

        if not args.json:
            print(result.marker())
            for c in result.conditions:
                mark = {SATISFIED: "  ok", UNSATISFIED: "FAIL", NOT_CHECKED: "  ??", NOT_APPLICABLE: "  na"}[c.outcome]
                print(f"  [{mark}] {c.n:2d}. {c.text}")
                if c.outcome != SATISFIED:
                    print(f"           -> {c.basis}")
            for prob in extra:
                print(f"  [FAIL] coherence: {prob}")
        if not result.complete or extra:
            worst = 1

    if args.json:
        print(json.dumps(payloads, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(_main())
