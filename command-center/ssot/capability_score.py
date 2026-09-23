#!/usr/bin/env python3
"""capability_score.py -- the 0-100 capability score sidecar with hysteresis.

One row of probe observations per endpoint (an MCP server or a ``models.json``
endpoint) goes in; ``state/capability-scores.json`` comes out. The score is a
snapshot of the latest observations, the STATE carries the memory::

    score = 40 availability + 20 capability match + 15 latency vs own baseline
          + 10 freshness + 10 security + 5 claim agreement

States: ``live`` / ``degraded`` / ``quarantined`` / ``deprecation-candidate`` /
``retired``.

* ``degraded`` is entered when the score drops under 60 or a claim disagrees with
  an observation; it takes TWO consecutive good runs (score >= 70, claim agreement
  intact) to leave it.
* ``quarantined`` follows ``mcp.supervision``: 3 failures inside 600 s. A failure
  outside the window is forgotten. Quarantine holds until the window has passed;
  then the same two-good-runs rule applies (``degraded`` until they have accrued).
* ``deprecation-candidate`` is driven by an upstream signal from the catalog diff
  (``expired`` / ``status_not_live`` / ``decommissioned_host``); it holds while
  the signal holds.
* ``retired`` is ONLY ever a human write-back: an owner adds ``retired_by`` to the
  entry. This script never sets, clears or invents that field; it preserves it.

The sidecar is a closed schema (unknown keys are errors, not warnings) so a typo
cannot pass as a state, and every write is atomic (temp file + ``os.replace``).
Rows come from any producer that follows ``ROW_SPEC``; ``rows_from_ladder`` turns
the ``hooks/mcp-liveness/liveness.py --mode all`` report into rows.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = REPO_ROOT / "state" / "capability-scores.json"
DEFAULT_AGENTS_CONFIG = REPO_ROOT / ".agents" / "agents.json"
CONTROL_PLANE = REPO_ROOT / ".agents" / "scripts" / "mcp_control_plane.py"

SCHEMA_VERSION = 1

WEIGHTS: dict[str, int] = {
    "availability": 40,
    "capability": 20,
    "latency": 15,
    "freshness": 10,
    "security": 10,
    "claim_agreement": 5,
}
COMPONENTS = tuple(WEIGHTS)

LIVE = "live"
DEGRADED = "degraded"
QUARANTINED = "quarantined"
DEPRECATION_CANDIDATE = "deprecation-candidate"
RETIRED = "retired"
STATES = (LIVE, DEGRADED, QUARANTINED, DEPRECATION_CANDIDATE, RETIRED)

DEGRADED_BELOW = 60
RECOVER_AT = 70
RECOVERY_RUNS = 2
FAILURE_THRESHOLD = 3
FAILURE_WINDOW_SECONDS = 600
FRESH_HOURS = 24
STALE_DAYS = 7
LATENCY_OK_RATIO = 1.5
LATENCY_ZERO_RATIO = 3.0
BASELINE_ALPHA = 0.2

DIGEST_STATES = ("unchanged", "changed", "pinned", "unavailable", "none")
SCAN_STATES = ("clean", "findings", "skipped")
DEPRECATION_KINDS = ("expired", "status_not_live")

TOP_KEYS = ("schemaVersion", "updated_at", "endpoints")
ENTRY_KEYS = (
    "score",
    "components",
    "state",
    "consecutive_good",
    "failures",
    "last_probe",
    "retired_by",
)
ENTRY_REQUIRED = ENTRY_KEYS[:-1]
LAST_PROBE_KEYS = ("at", "ok", "latency_ms", "baseline_latency_ms", "last_success_at")

_NONE = type(None)
# Closed row schema: key -> accepted types. ``id`` and ``ok`` are required.
ROW_SPEC: dict[str, tuple[type, ...]] = {
    "id": (str,),
    "ok": (bool,),
    "availability": (int, float, _NONE),
    "latency_ms": (int, float, _NONE),
    "baseline_latency_ms": (int, float, _NONE),
    "claimed": (list,),
    "observed": (dict,),
    "digest": (str,),
    "reviewed": (bool,),
    "scan": (str,),
    "claim_agreement": (bool, _NONE),
    "deprecation_signal": (str, _NONE),
    "last_success_at": (str, _NONE),
}
ROW_REQUIRED = ("id", "ok")

Json = dict[str, Any]
Writer = Callable[[Path, Mapping[str, Any]], None]


class CapabilityScoreError(Exception):
    """Misuse, a malformed sidecar or a malformed row -- the only exit-2 path."""


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp; naive values are read as UTC."""
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CapabilityScoreError(f"bad timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _local_atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Same shape as ``mcp_control_plane.atomic_write_json``: temp file in the
    target directory, fsync, ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def load_atomic_writer(module_path: Path = CONTROL_PLANE) -> Writer:
    """``atomic_write_json`` imported by path from ``.agents/scripts/mcp_control_plane.py``
    (the estate's one publication primitive); the local copy when that file is not
    beside this checkout."""
    if not module_path.is_file():
        return _local_atomic_write_json
    spec = importlib.util.spec_from_file_location(
        "_capability_score_control_plane", module_path
    )
    if spec is None or spec.loader is None:
        return _local_atomic_write_json
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.atomic_write_json


atomic_write_json: Writer = load_atomic_writer()


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


# ---------------------------------------------------------------------------
# Closed schemas
# ---------------------------------------------------------------------------
def _check_keys(
    mapping: Any, allowed: Iterable[str], required: Iterable[str], where: str
) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        raise CapabilityScoreError(f"{where} must be an object")
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise CapabilityScoreError(f"{where} has unknown key(s): {', '.join(unknown)}")
    missing = sorted(set(required) - set(mapping))
    if missing:
        raise CapabilityScoreError(f"{where} lacks key(s): {', '.join(missing)}")
    return mapping


def _string_list(value: Any, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CapabilityScoreError(f"{where} must be a list of strings")
    return value


def validate_entry(endpoint_id: str, entry: Any) -> dict[str, Any]:
    where = f"endpoints.{endpoint_id}"
    checked = _check_keys(entry, ENTRY_KEYS, ENTRY_REQUIRED, where)
    _check_keys(checked["components"], COMPONENTS, COMPONENTS, f"{where}.components")
    _check_keys(checked["last_probe"], LAST_PROBE_KEYS, (), f"{where}.last_probe")
    if checked["state"] not in STATES:
        raise CapabilityScoreError(f"{where}.state is not a known state")
    for key in ("score", "consecutive_good"):
        if not isinstance(checked[key], int) or isinstance(checked[key], bool):
            raise CapabilityScoreError(f"{where}.{key} must be an integer")
    _string_list(checked["failures"], f"{where}.failures")
    if "retired_by" in checked and not (
        isinstance(checked["retired_by"], str) and checked["retired_by"].strip()
    ):
        raise CapabilityScoreError(f"{where}.retired_by must be a non-empty string")
    if checked["state"] == RETIRED and "retired_by" not in checked:
        raise CapabilityScoreError(
            f"{where} is retired without retired_by; retirement is a human write-back"
        )
    return checked


def validate_state(state: Any) -> dict[str, Any]:
    """The sidecar document, or ``CapabilityScoreError`` on any unknown key."""
    checked = _check_keys(state, TOP_KEYS, TOP_KEYS, "state")
    if checked["schemaVersion"] != SCHEMA_VERSION:
        raise CapabilityScoreError(
            f"state.schemaVersion must be {SCHEMA_VERSION}, got {checked['schemaVersion']!r}"
        )
    endpoints = checked["endpoints"]
    if not isinstance(endpoints, dict):
        raise CapabilityScoreError("state.endpoints must be an object")
    for endpoint_id, entry in endpoints.items():
        validate_entry(str(endpoint_id), entry)
    return checked


def validate_row(row: Any) -> dict[str, Any]:
    checked = _check_keys(row, ROW_SPEC, ROW_REQUIRED, "row")
    for key, types in ROW_SPEC.items():
        if key in checked and not isinstance(checked[key], types):
            raise CapabilityScoreError(f"row.{key} has the wrong type")
    if not checked["id"].strip():
        raise CapabilityScoreError("row.id must be non-empty")
    if "claimed" in checked:
        _string_list(checked["claimed"], "row.claimed")
    if checked.get("digest", "none") not in DIGEST_STATES:
        raise CapabilityScoreError(f"row.digest must be one of {DIGEST_STATES}")
    if checked.get("scan", "skipped") not in SCAN_STATES:
        raise CapabilityScoreError(f"row.scan must be one of {SCAN_STATES}")
    return checked


def empty_state(now: str) -> Json:
    return {"schemaVersion": SCHEMA_VERSION, "updated_at": now, "endpoints": {}}


def load_state(path: Path, *, now: str) -> Json:
    """The validated sidecar, or an empty one when the file does not exist yet.

    A file that exists but does not parse or validate is an error: a hand-edited
    sidecar must never be silently replaced.
    """
    if not path.exists():
        return empty_state(now)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise CapabilityScoreError(f"state is not valid JSON: {path}") from exc
    return validate_state(payload)


# ---------------------------------------------------------------------------
# Score components (each documented, each its own function)
# ---------------------------------------------------------------------------
def availability_points(row: Mapping[str, Any]) -> int:
    """40 * availability. ``row["availability"]`` (a 0..1 fraction from a producer
    with history, such as the hub ledger) wins; otherwise this run's ``ok``."""
    fraction = row.get("availability")
    if fraction is None:
        fraction = 1.0 if row["ok"] else 0.0
    return round(WEIGHTS["availability"] * _clamp(float(fraction)))


def capability_points(row: Mapping[str, Any]) -> int:
    """20 * (claims observed true / claims observed at all).

    A claim that has never been observed is neither confirmed nor refuted, so it
    is left out of the ratio; when nothing has been observed the component is
    worth half (unknown, not disproven).
    """
    observed = row.get("observed") or {}
    judged = [name for name in row.get("claimed") or [] if name in observed]
    if not judged:
        return WEIGHTS["capability"] // 2
    matched = sum(1 for name in judged if observed[name])
    return round(WEIGHTS["capability"] * matched / len(judged))


def latency_points(row: Mapping[str, Any]) -> int:
    """15 * latency health against the endpoint's OWN baseline: 1.0 while the
    observed latency is within 1.5x the baseline, linear to 0 at 3x. No
    observation this run -> 0; no baseline yet -> 15 (nothing to regress against)."""
    latency = row.get("latency_ms")
    if latency is None:
        return 0
    baseline = row.get("baseline_latency_ms")
    if not baseline:
        return WEIGHTS["latency"]
    ratio = float(latency) / float(baseline)
    if ratio <= LATENCY_OK_RATIO:
        health = 1.0
    elif ratio >= LATENCY_ZERO_RATIO:
        health = 0.0
    else:
        health = (LATENCY_ZERO_RATIO - ratio) / (LATENCY_ZERO_RATIO - LATENCY_OK_RATIO)
    return round(WEIGHTS["latency"] * health)


def freshness_points(row: Mapping[str, Any], now: str) -> int:
    """10 when the last successful probe is <= 24 h old, 5 when <= 7 days, else 0."""
    last_success = row.get("last_success_at")
    if last_success is None:
        return 0
    age = parse_iso(now) - parse_iso(last_success)
    if age <= timedelta(hours=FRESH_HOURS):
        return WEIGHTS["freshness"]
    if age <= timedelta(days=STALE_DAYS):
        return WEIGHTS["freshness"] // 2
    return 0


def security_points(row: Mapping[str, Any]) -> int:
    """10 when there is no open scan finding and the tool digest has not drifted;
    5 when the digest changed but an owner marked the change reviewed; 0 for an
    open finding or unreviewed drift. A skipped scan is not a finding."""
    if row.get("scan", "skipped") == "findings":
        return 0
    if row.get("digest", "none") == "changed":
        return WEIGHTS["security"] // 2 if row.get("reviewed") else 0
    return WEIGHTS["security"]


def claim_agreement_points(row: Mapping[str, Any]) -> int:
    """5 unless a catalog/vendor claim and our observation are known to disagree."""
    return 0 if row.get("claim_agreement") is False else WEIGHTS["claim_agreement"]


def components(row: Mapping[str, Any], *, now: str | None = None) -> dict[str, int]:
    now = now or utc_now_iso()
    return {
        "availability": availability_points(row),
        "capability": capability_points(row),
        "latency": latency_points(row),
        "freshness": freshness_points(row, now),
        "security": security_points(row),
        "claim_agreement": claim_agreement_points(row),
    }


def score(row: Mapping[str, Any], *, now: str | None = None) -> int:
    return sum(components(row, now=now).values())


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
def prune_failures(failures: Iterable[Any], now: str, window_seconds: int) -> list[str]:
    """Only failures inside the trailing window count (``mcp.supervision``)."""
    cutoff = parse_iso(now) - timedelta(seconds=window_seconds)
    return [str(value) for value in failures if parse_iso(value) >= cutoff]


def decide_state(
    previous_state: str | None,
    *,
    retired_by: str | None,
    deprecation_signal: str | None,
    failures_in_window: int,
    threshold: int,
    total: int,
    claim_points: int,
    consecutive_good: int,
) -> str:
    """The next state. Precedence: human retirement > quarantine window > upstream
    deprecation signal > hysteresis between ``live`` and ``degraded``."""
    if retired_by is not None:
        return RETIRED
    if failures_in_window >= threshold:
        return QUARANTINED
    if deprecation_signal:
        return DEPRECATION_CANDIDATE
    if previous_state in (None, LIVE):
        unhealthy = total < DEGRADED_BELOW or claim_points == 0
        return DEGRADED if unhealthy else LIVE
    return LIVE if consecutive_good >= RECOVERY_RUNS else DEGRADED


def update_entry(
    previous: Mapping[str, Any] | None,
    row: Mapping[str, Any],
    *,
    now: str,
    threshold: int = FAILURE_THRESHOLD,
    window_seconds: int = FAILURE_WINDOW_SECONDS,
) -> Json:
    """Fold one observation row into one sidecar entry."""
    prev: Mapping[str, Any] = previous or {}
    last_probe: Mapping[str, Any] = prev.get("last_probe") or {}
    ok = bool(row["ok"])
    baseline = row.get("baseline_latency_ms", last_probe.get("baseline_latency_ms"))
    if ok:
        last_success = now
    else:
        last_success = row.get("last_success_at") or last_probe.get("last_success_at")
    enriched = {
        **row,
        "baseline_latency_ms": baseline,
        "last_success_at": last_success,
    }
    parts = components(enriched, now=now)
    total = sum(parts.values())

    failures = prune_failures(prev.get("failures") or [], now, window_seconds)
    if not ok:
        failures.append(now)
    good = ok and total >= RECOVER_AT and parts["claim_agreement"] > 0
    consecutive_good = int(prev.get("consecutive_good") or 0) + 1 if good else 0
    state = decide_state(
        prev.get("state"),
        retired_by=prev.get("retired_by"),
        deprecation_signal=row.get("deprecation_signal"),
        failures_in_window=len(failures),
        threshold=threshold,
        total=total,
        claim_points=parts["claim_agreement"],
        consecutive_good=consecutive_good,
    )

    latency = row.get("latency_ms")
    if ok and latency is not None:
        baseline = (
            round(float(latency))
            if not baseline
            else round(
                (1 - BASELINE_ALPHA) * float(baseline) + BASELINE_ALPHA * latency
            )
        )
    entry: Json = {
        "score": total,
        "components": parts,
        "state": state,
        "consecutive_good": consecutive_good,
        "failures": failures,
        "last_probe": {
            "at": now,
            "ok": ok,
            "latency_ms": latency,
            "baseline_latency_ms": baseline,
            "last_success_at": last_success,
        },
    }
    if "retired_by" in prev:
        entry["retired_by"] = prev["retired_by"]
    return entry


def update_scores(
    state: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    *,
    now: str,
    threshold: int = FAILURE_THRESHOLD,
    window_seconds: int = FAILURE_WINDOW_SECONDS,
) -> Json:
    """A new sidecar document: every row folded in, every other entry untouched."""
    checked = validate_state(state)
    endpoints: Json = {
        endpoint_id: dict(entry) for endpoint_id, entry in checked["endpoints"].items()
    }
    for raw in rows:
        row = validate_row(raw)
        endpoints[row["id"]] = update_entry(
            endpoints.get(row["id"]),
            row,
            now=now,
            threshold=threshold,
            window_seconds=window_seconds,
        )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "updated_at": now,
        "endpoints": dict(sorted(endpoints.items())),
    }


def summarise(state: Mapping[str, Any], *, updated: int) -> dict[str, int]:
    counts = {name: 0 for name in STATES}
    for entry in state["endpoints"].values():
        counts[entry["state"]] += 1
    return {
        "endpoints": len(state["endpoints"]),
        "updated": updated,
        **{name.replace("-", "_"): count for name, count in counts.items()},
    }


# ---------------------------------------------------------------------------
# Rows from the mcp-liveness ladder report
# ---------------------------------------------------------------------------
def _rung(report: Mapping[str, Any], rung: str) -> dict[str, Any]:
    rungs = report.get("rungs")
    entry = rungs.get(rung) if isinstance(rungs, dict) else None
    return entry if isinstance(entry, dict) else {}


def _items(report: Mapping[str, Any], rung: str) -> list[dict[str, Any]]:
    items = _rung(report, rung).get("items")
    return [item for item in items if isinstance(item, dict)] if items else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def scan_verdict(name: str, report: Mapping[str, Any]) -> str:
    """``findings`` when L5 flagged this server, ``clean`` when L5 ran without
    naming it, ``skipped`` when L5 did not run (or errored)."""
    if _rung(report, "L5").get("status") not in ("clean", "findings"):
        return "skipped"
    for item in _items(report, "L5"):
        if name in _strings(item.get("flagged")):
            return "findings"
    return "clean"


def deprecation_signal(
    endpoint_id: str,
    url: Any,
    remote_ids: Iterable[str],
    diff: Mapping[str, Any] | None,
) -> str | None:
    """Which standing catalog-diff signal names this endpoint, if any: an
    ``expired`` / ``status_not_live`` row on the endpoint's own feed for one of
    its REGISTERED models, or its host among ``decommissioned_hosts``."""
    if diff is None:
        return None
    wanted = set(remote_ids)
    for kind in DEPRECATION_KINDS:
        rows = diff.get(kind)
        for row in rows if isinstance(rows, list) else []:
            if (
                isinstance(row, dict)
                and row.get("feed") == endpoint_id
                and row.get("id") in wanted
            ):
                return kind
    hosts = diff.get("decommissioned_hosts")
    host = urlparse(url).hostname if isinstance(url, str) else None
    if host and isinstance(hosts, list) and host in hosts:
        return "decommissioned_host"
    return None


def rows_from_ladder(
    report: Mapping[str, Any], catalog_diff: Mapping[str, Any] | None = None
) -> list[Json]:
    """One row per L1 MCP server and per L3-probed endpoint. Skipped L3 items
    (hosted, owner-run; disabled) yield no row: no observation, nothing to score."""
    rows: list[Json] = []
    digests = {
        str(item.get("server")): item
        for item in _items(report, "L2")
        if "server" in item
    }
    for item in _items(report, "L1"):
        name = str(item.get("name"))
        pin = digests.get(name) or {}
        digest = str(pin.get("status") or "none")
        rows.append(
            {
                "id": name,
                "ok": item.get("state") == "up",
                "latency_ms": item.get("latency_ms"),
                "claimed": ["tools"],
                "observed": {"tools": bool(item["tools_ok"])}
                if "tools_ok" in item
                else {},
                "digest": digest if digest in DIGEST_STATES else "none",
                "reviewed": bool(pin.get("reviewed")),
                "scan": scan_verdict(name, report),
                "claim_agreement": None,
            }
        )
    inference = {
        str(item.get("endpoint")): item
        for item in _items(report, "L4")
        if item.get("status") in ("ok", "error")
    }
    for item in _items(report, "L3"):
        if item.get("status") == "skipped":
            continue
        endpoint_id = str(item.get("endpoint"))
        probe = inference.get(endpoint_id)
        observed = probe.get("observed") if probe else None
        observed = (
            {str(k): bool(v) for k, v in observed.items()}
            if isinstance(observed, dict)
            else {}
        )
        rows.append(
            {
                "id": endpoint_id,
                "ok": item.get("status") == "up",
                "latency_ms": item.get("latency_ms"),
                "claimed": _strings(item.get("claims")),
                "observed": observed,
                "claim_agreement": all(observed.values()) if observed else None,
                "deprecation_signal": deprecation_signal(
                    endpoint_id,
                    item.get("url"),
                    _strings(item.get("registry_models")),
                    catalog_diff,
                ),
            }
        )
    return rows


def rows_from_input(payload: Any, catalog_diff: Mapping[str, Any] | None) -> list[Json]:
    """``{"rows": [...]}`` from any producer, or a ``--mode all`` ladder report."""
    if not isinstance(payload, dict):
        raise CapabilityScoreError("input must be a JSON object")
    if isinstance(payload.get("rows"), list):
        return list(payload["rows"])
    if isinstance(payload.get("rungs"), dict):
        return rows_from_ladder(payload, catalog_diff)
    raise CapabilityScoreError("input has neither 'rows' nor a ladder 'rungs' block")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def load_json_file(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CapabilityScoreError(f"{what} not readable: {path}") from exc
    except ValueError as exc:
        raise CapabilityScoreError(f"{what} is not valid JSON: {path}") from exc


def supervision_policy(path: Path) -> tuple[int, int]:
    """``(failureThreshold, failureWindowSeconds)`` from ``agents.json``'s
    ``mcp.supervision`` block; the module defaults when it is absent."""
    threshold, window = FAILURE_THRESHOLD, FAILURE_WINDOW_SECONDS
    if not path.is_file():
        return threshold, window
    config = load_json_file(path, "agents config")
    mcp = config.get("mcp") if isinstance(config, dict) else None
    supervision = mcp.get("supervision") if isinstance(mcp, dict) else None
    if isinstance(supervision, dict):
        threshold = int(supervision.get("failureThreshold", threshold))
        window = int(supervision.get("failureWindowSeconds", window))
    return threshold, window


def run(
    state_path: Path,
    input_path: Path,
    *,
    agents_config: Path,
    catalog_diff: Path | None,
    now: str | None = None,
) -> Json:
    now = now or utc_now_iso()
    threshold, window = supervision_policy(agents_config)
    diff = load_json_file(catalog_diff, "catalog diff") if catalog_diff else None
    if diff is not None and not isinstance(diff, dict):
        raise CapabilityScoreError("catalog diff must be a JSON object")
    rows = rows_from_input(load_json_file(input_path, "input"), diff)
    state = update_scores(
        load_state(state_path, now=now),
        rows,
        now=now,
        threshold=threshold,
        window_seconds=window,
    )
    atomic_write_json(state_path, state)
    return {
        "updated_at": now,
        "state": str(state_path),
        "policy": {"failureThreshold": threshold, "failureWindowSeconds": window},
        "counts": summarise(state, updated=len(rows)),
        "endpoints": {
            endpoint_id: {"score": entry["score"], "state": entry["state"]}
            for endpoint_id, entry in state["endpoints"].items()
        },
    }


def _success_line(counts: Mapping[str, int]) -> str:
    return (
        "SUCCESS:capability-score "
        f"endpoints={counts['endpoints']} live={counts['live']} "
        f"degraded={counts['degraded']} quarantined={counts['quarantined']} "
        f"deprecation_candidate={counts['deprecation_candidate']} "
        f"retired={counts['retired']} updated={counts['updated']}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="capability_score.py",
        description="Fold probe observations into the capability-score sidecar.",
    )
    parser.add_argument(
        "--state", type=Path, default=DEFAULT_STATE, help="sidecar path"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="ladder report from `liveness.py --mode all --out`, or {rows: [...]}",
    )
    parser.add_argument(
        "--agents-config",
        type=Path,
        default=DEFAULT_AGENTS_CONFIG,
        help="agents.json whose mcp.supervision sets the quarantine window",
    )
    parser.add_argument(
        "--catalog-diff",
        type=Path,
        default=None,
        help="state/catalog/last-diff.json for deprecation signals",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable summary")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        summary = run(
            args.state,
            args.input,
            agents_config=args.agents_config,
            catalog_diff=args.catalog_diff,
        )
    except CapabilityScoreError as exc:
        print(f"FAILED:capability-score {exc}")
        return 2
    except Exception as exc:  # a bug, not a finding: still one terminal line
        print(f"FAILED:capability-score {type(exc).__name__}: {exc}")
        return 2
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for endpoint_id, entry in summary["endpoints"].items():
            print(f"  {endpoint_id}: {entry['state']} ({entry['score']})")
    print(_success_line(summary["counts"]))
    return 0


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    sys.exit(main())
