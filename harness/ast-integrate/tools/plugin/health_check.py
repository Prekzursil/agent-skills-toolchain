"""Plugin health aggregate: blocked/unrun/throwing probes prevent HEALTHY (IMP-0043).

A ``health-check`` runner over a pluggable probe registry.  Every probe returns a
terminal state -- ``SUCCESS`` / ``FAILED`` / ``BLOCKED`` -- plus its evidence, and
the aggregate is computed ONCE (``aggregate``) from the registry and the rows, so
the same rule applies whether the rows came from ``run_all`` or from a caller that
assembled them by hand:

* any ``BLOCKED`` row forbids HEALTHY (a blocked probe has proven nothing);
* any row that is not ``SUCCESS`` forbids HEALTHY;
* a probe that is REGISTERED but has no row is ``missing_unrun`` and forbids
  HEALTHY -- unrun is not pass;
* a probe that raises is recorded ``FAILED`` with ``evidence.uncaught = True``,
  never swallowed into a pass;
* an empty row set is not HEALTHY either (nothing was observed).

Probes observe an explicit ``HealthContext.root`` (a fixture tree or a supplied
live tree); nothing here reads the operator's real machine implicitly.  The
built-in probes and their IMP-0044 both-states controls live in
``health_probes.py``.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

STATES = ("SUCCESS", "FAILED", "BLOCKED")
HEALTHY = "HEALTHY"
NOT_HEALTHY = "NOT-HEALTHY"
DEFAULT_UNIT_ID = "IMP-0043"
SCHEMA_PATH = Path(__file__).resolve().with_name("schema") / "health-report.schema.json"


@dataclass
class HealthContext:
    root: Path
    force_state: dict[str, str] = field(default_factory=dict)
    unit_id: str = DEFAULT_UNIT_ID


@dataclass
class ProbeResult:
    probe_id: str
    state: str
    reason: str = ""
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "state": self.state,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


@dataclass
class BothStatesControl:
    """IMP-0044 both-states control: what proves the probe fires AND stays silent."""

    unit_id: str
    known_good: str
    known_broken: str
    expected_good: str
    expected_broken: str
    plant_good: Callable
    plant_broken: Callable

    def to_dict(self, probe_id: str) -> dict[str, Any]:
        return {
            "probe_id": probe_id,
            "unit_id": self.unit_id,
            "known_good": self.known_good,
            "known_broken": self.known_broken,
            "expected_good": self.expected_good,
            "expected_broken": self.expected_broken,
            "present": True,
        }


@dataclass
class HealthReport:
    healthy: bool
    aggregate: str
    probes: list[ProbeResult]
    blocked_ids: list[str]
    missing_unrun: list[str]
    reason: str = ""
    failed_ids: list[str] = field(default_factory=list)
    unit_id: str = DEFAULT_UNIT_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "healthy": self.healthy,
            "aggregate": self.aggregate,
            "probes": [p.to_dict() for p in self.probes],
            "blocked_ids": list(self.blocked_ids),
            "failed_ids": list(self.failed_ids),
            "missing_unrun": list(self.missing_unrun),
            "reason": self.reason,
            "unit_id": self.unit_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class Probe:
    """Base class for a probe: ``probe_id`` plus ``run(ctx) -> ProbeResult``."""

    probe_id = "unnamed"
    both_states: BothStatesControl | None = None

    def run(self, ctx: HealthContext) -> ProbeResult:  # pragma: no cover - interface
        raise NotImplementedError(f"{self.probe_id}: run() not implemented")


def probe_id_of(probe: Any) -> str:
    return str(getattr(probe, "probe_id", None) or probe.__class__.__name__)


_CONTROL_FIELDS = ("unit_id", "known_good", "known_broken", "expected_good", "expected_broken", "plant_good", "plant_broken")


def control_of(probe: Any) -> BothStatesControl | None:
    """The probe's both-states control, or None.

    Structural, not ``isinstance``: when this file runs as ``__main__`` the probes
    module imports a second copy of it, and a control built from that copy is still
    a control.
    """
    control = getattr(probe, "both_states", None)
    if control is None or not all(hasattr(control, name) for name in _CONTROL_FIELDS):
        return None
    if not callable(control.plant_good) or not callable(control.plant_broken):
        return None
    return control


def control_row(control: Any, probe_id: str) -> dict[str, Any]:
    return {
        "probe_id": probe_id,
        "unit_id": control.unit_id,
        "known_good": control.known_good,
        "known_broken": control.known_broken,
        "expected_good": control.expected_good,
        "expected_broken": control.expected_broken,
        "present": True,
    }


class Registry(list):
    """Ordered probe registry; duplicate ids are refused so unrun detection is exact."""

    def register(self, probe: Any) -> None:
        pid = probe_id_of(probe)
        if pid in self.probe_ids():
            raise ValueError(f"probe id {pid!r} is already registered")
        if not callable(getattr(probe, "run", None)):
            raise TypeError(f"probe {pid!r} has no run(ctx)")
        self.append(probe)

    def probe_ids(self) -> list[str]:
        return [probe_id_of(p) for p in self]

    def require_both_states(self) -> list[dict[str, Any]]:
        """One row per registered probe's IMP-0044 control; raises if any probe lacks one."""
        rows: list[dict[str, Any]] = []
        missing: list[str] = []
        for probe in self:
            control = control_of(probe)
            if control is None:
                missing.append(probe_id_of(probe))
                continue
            rows.append(control_row(control, probe_id_of(probe)))
        if missing:
            raise LookupError(f"probes without a both-states control: {missing}")
        return rows


def default_registry() -> Registry:
    from health_probes import default_probes

    registry = Registry()
    for probe in default_probes():
        registry.register(probe)
    return registry


def aggregate(
    registry: list[Any], rows: list[ProbeResult], *, unit_id: str = DEFAULT_UNIT_ID
) -> HealthReport:
    """THE aggregation rule.  ``run_all`` and hand-assembled rows both go through here."""
    ids = [probe_id_of(p) for p in registry]
    seen = {r.probe_id for r in rows}
    unrun = [i for i in ids if i not in seen]
    blocked = [r.probe_id for r in rows if r.state == "BLOCKED"]
    failed = [r.probe_id for r in rows if r.state not in ("SUCCESS", "BLOCKED")]
    healthy = bool(rows) and not blocked and not failed and not unrun
    if healthy:
        reason = "all-registered-probes-ran-and-succeeded"
    else:
        parts = []
        if not rows:
            parts.append("no-probes-ran")
        if blocked:
            parts.append("blocked:" + ",".join(blocked))
        if failed:
            parts.append("failed:" + ",".join(failed))
        if unrun:
            parts.append("unrun:" + ",".join(unrun))
        reason = ";".join(parts)
    return HealthReport(
        healthy=healthy,
        aggregate=HEALTHY if healthy else NOT_HEALTHY,
        probes=list(rows),
        blocked_ids=blocked,
        missing_unrun=unrun,
        reason=reason,
        failed_ids=failed,
        unit_id=unit_id,
    )


def run_probe(probe: Any, ctx: HealthContext) -> ProbeResult:
    """Run one probe to a terminal row.  Raising is FAILED+uncaught; a bad return is FAILED."""
    pid = probe_id_of(probe)
    forced = (ctx.force_state or {}).get(pid)
    if forced:
        if forced not in STATES:
            raise ValueError(f"force_state[{pid!r}]={forced!r} is not one of {STATES}")
        return ProbeResult(
            pid,
            forced,
            reason="forced-state",
            evidence={"forced": True, "forced_state": forced, "reason": "forced-state"},
        )
    try:
        row = probe.run(ctx)
    except Exception as exc:  # noqa: BLE001 - a throwing probe is a FAILED probe, by contract
        return ProbeResult(
            pid,
            "FAILED",
            reason=f"uncaught {type(exc).__name__}: {exc}",
            evidence={"uncaught": True, "exception": type(exc).__name__, "message": str(exc)},
        )
    if not isinstance(row, ProbeResult):
        # Structural acceptance: a ProbeResult built from a second import of this
        # module (health_probes imports ``health_check`` while this file runs as
        # ``__main__``) is still a result.  Anything without state+evidence is not.
        state = getattr(row, "state", None)
        evidence = getattr(row, "evidence", None)
        if not isinstance(state, str) or not isinstance(evidence, dict):
            return ProbeResult(
                pid,
                "FAILED",
                reason="probe returned a non-ProbeResult",
                evidence={"uncaught": False, "returned_type": type(row).__name__},
            )
        row = ProbeResult(pid, state, reason=str(getattr(row, "reason", "") or ""), evidence=dict(evidence))
    row.probe_id = pid
    if row.state not in STATES:
        return ProbeResult(
            pid,
            "FAILED",
            reason=f"probe returned non-terminal state {row.state!r}",
            evidence={"uncaught": False, "returned_state": row.state, **row.evidence},
        )
    return row


def run_all(registry: list[Any], ctx: HealthContext) -> HealthReport:
    rows = [run_probe(probe, ctx) for probe in registry]
    return aggregate(registry, rows, unit_id=ctx.unit_id)


# ---------------------------------------------------------------------------
# both-states execution and schema validation (stdlib; no jsonschema dependency)
# ---------------------------------------------------------------------------


def run_both_states(registry: list[Any], workdir: Path | None = None) -> list[dict[str, Any]]:
    """Execute every probe's IMP-0044 control: good tree -> expected_good, broken -> expected_broken."""
    rows: list[dict[str, Any]] = []
    for probe in registry:
        control = control_of(probe)
        pid = probe_id_of(probe)
        if control is None:
            rows.append({"probe_id": pid, "present": False, "ok": False})
            continue
        with tempfile.TemporaryDirectory(prefix=f"both-states-{pid}-", dir=workdir) as good_td, \
                tempfile.TemporaryDirectory(prefix=f"both-states-{pid}-", dir=workdir) as bad_td:
            control.plant_good(Path(good_td))
            control.plant_broken(Path(bad_td))
            good = run_probe(probe, HealthContext(root=Path(good_td)))
            bad = run_probe(probe, HealthContext(root=Path(bad_td)))
        rows.append(
            {
                **control_row(control, pid),
                "observed_good": good.state,
                "observed_broken": bad.state,
                "ok": good.state == control.expected_good and bad.state == control.expected_broken,
            }
        )
    return rows


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}


def _check(node: dict[str, Any], value: Any, where: str, errors: list[str]) -> None:
    kind = node.get("type")
    if kind is not None:
        expected = _TYPES.get(kind)
        if expected is not None and (
            not isinstance(value, expected) or (kind in ("integer", "number") and isinstance(value, bool))
        ):
            errors.append(f"{where}: expected {kind}, got {type(value).__name__}")
            return
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{where}: {value!r} not in {node['enum']}")
    if isinstance(value, dict):
        for key in node.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required {key!r}")
        props = node.get("properties", {})
        for key, sub in props.items():
            if key in value:
                _check(sub, value[key], f"{where}.{key}", errors)
        if node.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{where}: additional property {key!r}")
    if isinstance(value, list) and "items" in node:
        for index, item in enumerate(value):
            _check(node["items"], item, f"{where}[{index}]", errors)


def validate_report(document: dict[str, Any]) -> list[str]:
    """Errors (empty = valid) of a report dict against health-report.schema.json."""
    errors: list[str] = []
    _check(_load_schema(), document, "$", errors)
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="health-check",
        description="Run the plugin health probes over an observation root and aggregate.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--root", type=Path, help="observation root the probes read")
    target.add_argument(
        "--fixture",
        choices=("healthy", "broken"),
        help="plant a known-good / known-broken tree in a temp dir and observe that",
    )
    parser.add_argument(
        "--force",
        action="append",
        default=[],
        metavar="PROBE_ID=STATE",
        help="force one probe's terminal state (e.g. hooks_loaded=BLOCKED); repeatable",
    )
    parser.add_argument("--both-states", action="store_true", help="also execute every IMP-0044 control")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    force: dict[str, str] = {}
    for item in args.force:
        pid, sep, state = item.partition("=")
        if not sep or state not in STATES:
            print(f"FAILED:health-check --force wants PROBE_ID=STATE with STATE in {STATES}", file=sys.stderr)
            return 2
        force[pid] = state
    registry = default_registry()
    scratch = None
    try:
        if args.fixture:
            from health_probes import plant_broken_tree, plant_healthy_tree

            scratch = tempfile.TemporaryDirectory(prefix=f"health-check-{args.fixture}-")
            root = Path(scratch.name)
            (plant_healthy_tree if args.fixture == "healthy" else plant_broken_tree)(root)
        else:
            root = args.root
        report = run_all(registry, HealthContext(root=root, force_state=force))
        document = report.to_dict()
        if args.both_states:
            document["both_states"] = run_both_states(registry)
        errors = validate_report(document)
        print(json.dumps(document, indent=2, sort_keys=True))
        if errors:
            print(f"FAILED:health-check report violates schema: {errors}", file=sys.stderr)
            return 2
        if args.both_states and not all(row.get("ok") for row in document["both_states"]):
            print("FAILED:health-check a both-states control did not discriminate", file=sys.stderr)
            return 1
        if report.healthy:
            print(f"SUCCESS:health-check {report.aggregate} probes={len(report.probes)}")
            return 0
        print(f"FAILED:health-check {report.aggregate} reason={report.reason}")
        return 1
    finally:
        if scratch is not None:
            scratch.cleanup()


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
