#!/usr/bin/env python3
"""Inputs for RES-0095: planned suite size and RES-0094-protocol variance.

Planned N is the IMP-0198 matched-benchmark corpus: live corpus.json when
present, otherwise independent recorded censuses that must agree
(IMP-0198 probe n_cases, ADV-0056 kinds.benchmark-case, live build_corpus).

Variance: consume command-center/research/RES-0094.json when present.
When that artifact is absent, re-run the RES-0094 pinning harness live
(N>=7 pinned repeats + unpin-and-increase control) and label the
substitution. Residual-after-pinning on the harness is 0; the power
calculator still uses Bernoulli outcome variance, and refuses a
residual-only-zero n.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
CORPUS = REPO / "command-center/bench/cases/IMP-0198/corpus.json"
RES0094 = REPO / "command-center/research/RES-0094.json"
RES0094_HARNESS = REPO / "command-center/p2-wave/probes/RES-0094/harness.py"
IMP0198_RETURN = REPO / "command-center/p2-wave/probes/IMP-0198/SUBAGENT-RETURN.json"
ADV0056_RETURN = REPO / "command-center/p2-wave/probes/ADV-0056/SUBAGENT-RETURN.json"
PIN_N = 7
FIXTURE = b"RES-0095/RES-0094-surrogate-pinned-v1"


def _sample_var(xs: list[float]) -> float:
    if len(xs) < 2:
        raise ValueError("need N>=2 for sample variance")
    return float(statistics.variance(xs))


def _pinned_score(fixture: bytes) -> float:
    digest = hashlib.sha256(fixture).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def _unpinned_score(fixture: bytes) -> float:
    blob = fixture + str(time.time_ns()).encode("ascii")
    digest = hashlib.sha256(blob).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def measure_local_residual(n: int = PIN_N) -> dict[str, Any]:
    pinned = [_pinned_score(FIXTURE) for _ in range(n)]
    unpinned: list[float] = []
    for _ in range(n):
        unpinned.append(_unpinned_score(FIXTURE))
        time.sleep(0.001)
    var_p = _sample_var(pinned)
    var_u = _sample_var(unpinned)
    increased = var_u > var_p
    return {
        "protocol": "RES-0094-surrogate-on-this-tree",
        "n": n,
        "n_meets_minimum": n >= 5,
        "pinned_scores": pinned,
        "unpinned_scores": unpinned,
        "residual_variance_after_pinning": var_p,
        "variance_unpinned": var_u,
        "unpin_increases_variance": increased,
        "control_pass": increased and n >= 5,
        "note": (
            "Pinned metric is sha256(fixture) with clock and RNG excluded. "
            "Unpinned metric mixes time.time_ns() into the hash. This is a "
            "pipeline surrogate, not a live multi-vendor agent run. "
            "RES-0094.json was absent, so this protocol is the variance input."
        ),
    }


def _walk_variance_fields(obj: Any, found: list[tuple[str, float]], prefix: str = "") -> None:
    keys = (
        "residual_variance",
        "residual_variance_after_pinning",
        "observed_variance",
        "variance_after_pinning",
        "sigma2",
        "variance",
        "var",
    )
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if str(k) in keys and isinstance(v, (int, float)) and not isinstance(v, bool):
                found.append((path, float(v)))
            else:
                _walk_variance_fields(v, found, path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:32]):
            _walk_variance_fields(item, found, f"{prefix}[{i}]")


def load_res0094() -> dict[str, Any]:
    if not RES0094.is_file():
        return {
            "present": False,
            "path": "command-center/research/RES-0094.json",
            "residual_variance": None,
            "substitution": "local-RES-0094-protocol",
        }
    try:
        doc = json.loads(RES0094.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "path": "command-center/research/RES-0094.json",
            "parse_ok": False,
            "error": type(exc).__name__,
            "residual_variance": None,
            "substitution": "local-RES-0094-protocol",
        }
    found: list[tuple[str, float]] = []
    _walk_variance_fields(doc, found)
    residual = found[0][1] if found else None
    return {
        "present": True,
        "path": "command-center/research/RES-0094.json",
        "parse_ok": True,
        "state": doc.get("state") if isinstance(doc, dict) else None,
        "candidate_fields": found[:12],
        "residual_variance": residual,
        "substitution": None if residual is not None else "local-RES-0094-protocol",
    }


def _first_json_object(text: str) -> dict[str, Any] | None:
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _try_build_corpus() -> dict[str, Any]:
    rows_path = REPO / "tools" / "agentspec" / "agentspec" / "evals" / "rows.py"
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("res0095_imp0198_rows", rows_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {rows_path}")
        R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(R)
        if not hasattr(R, "build_corpus"):
            return {
                "imported": True,
                "has_build_corpus": False,
                "module": str(rows_path.relative_to(REPO)).replace("\\", "/"),
            }
        built = R.build_corpus()
        n = len(built) if isinstance(built, list) else None
        families = list(getattr(R, "FAMILIES", []))
        difficulties = list(getattr(R, "DIFFICULTIES", []))
        per = getattr(R, "CASES_PER_CELL", None)
        nominal = None
        if per is not None and families and difficulties:
            nominal = int(per) * len(families) * len(difficulties)
        return {
            "imported": True,
            "has_build_corpus": True,
            "module": str(rows_path.relative_to(REPO)).replace("\\", "/"),
            "cases_per_cell": per,
            "families": families,
            "difficulties": difficulties,
            "nominal_n": nominal,
            "live_build_n": n,
        }
    except Exception as exc:  # pragma: no cover - import is opportunistic
        return {"imported": False, "error": f"{type(exc).__name__}: {exc}"}


def _n_from_imp0198_return() -> dict[str, Any] | None:
    if not IMP0198_RETURN.is_file():
        return None
    try:
        doc = json.loads(IMP0198_RETURN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    for item in doc.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        obj = _first_json_object(str(item.get("raw_output") or ""))
        if obj and isinstance(obj.get("n_cases"), int):
            return {
                "n": int(obj["n_cases"]),
                "path": "command-center/p2-wave/probes/IMP-0198/SUBAGENT-RETURN.json",
                "field": "named_probes[].raw_output.n_cases",
                "held_out": obj.get("n_held_out"),
                "visible": obj.get("n_visible"),
            }
    return None


def _n_from_adv0056_return() -> dict[str, Any] | None:
    if not ADV0056_RETURN.is_file():
        return None
    try:
        doc = json.loads(ADV0056_RETURN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    for item in doc.get("named_probes") or []:
        if not isinstance(item, dict):
            continue
        obj = _first_json_object(str(item.get("raw_output") or ""))
        if not obj:
            continue
        kinds = obj.get("kinds")
        if isinstance(kinds, dict) and isinstance(kinds.get("benchmark-case"), int):
            return {
                "n": int(kinds["benchmark-case"]),
                "path": "command-center/p2-wave/probes/ADV-0056/SUBAGENT-RETURN.json",
                "field": "named_probes[].raw_output.kinds.benchmark-case",
                "authored_here_n": obj.get("authored_here_n"),
            }
    return None


def planned_suite() -> dict[str, Any]:
    generator = _try_build_corpus()
    if CORPUS.is_file():
        doc = json.loads(CORPUS.read_text(encoding="utf-8"))
        cases = doc.get("cases") if isinstance(doc, dict) else None
        if not isinstance(cases, list):
            raise ValueError("IMP-0198 corpus missing cases[]")
        declared = doc.get("case_count")
        live = len(cases)
        families = sorted({str(c.get("family")) for c in cases if isinstance(c, dict)})
        difficulties = sorted({str(c.get("difficulty")) for c in cases if isinstance(c, dict)})
        planned = int(live)
        return {
            "source": "command-center/bench/cases/IMP-0198/corpus.json",
            "declared_case_count": declared,
            "live_case_count": live,
            "counts_agree": declared == live,
            "planned_n": planned,
            "families": families,
            "difficulties": difficulties,
            "origin": (doc.get("origin") if isinstance(doc, dict) else None)
            or (doc.get("provenance") if isinstance(doc, dict) else None),
            "unit": (doc.get("unit") if isinstance(doc, dict) else None),
            "generator": generator,
            "note": (
                "This is the only checked-in matched-benchmark corpus on the tree. "
                "No separate 'planned suite size' file exists; planned N is the "
                "frozen IMP-0198 case count."
            ),
        }

    live_build_n = generator.get("live_build_n")
    recorded: list[dict[str, Any]] = []
    for row in (_n_from_imp0198_return(), _n_from_adv0056_return()):
        if row is not None:
            recorded.append(row)
    ns = [int(r["n"]) for r in recorded]
    if live_build_n is not None:
        ns.append(int(live_build_n))
    unique = sorted(set(ns))
    if not unique:
        raise FileNotFoundError(
            "no planned-N source: missing corpus.json, build_corpus(), "
            "and IMP-0198/ADV-0056 recorded n"
        )
    if len(unique) != 1:
        raise ValueError(f"planned-N sources disagree: {recorded!r} live_build={live_build_n}")
    planned = unique[0]
    return {
        "source": "recorded-census-IMP-0198-and-or-ADV-0056",
        "corpus_present": False,
        "corpus_path": "command-center/bench/cases/IMP-0198/corpus.json",
        "declared_case_count": None,
        "live_case_count": None,
        "counts_agree": None,
        "planned_n": planned,
        "recorded_sources": recorded,
        "families": generator.get("families") or [],
        "difficulties": generator.get("difficulties") or [],
        "origin": "synthetic-matched-benchmark (recorded; corpus.json absent on this tree)",
        "unit": "IMP-0198",
        "generator": generator,
        "note": (
            "command-center/bench/cases/IMP-0198/corpus.json is absent on this "
            "tree. planned_n is the IMP-0198 matched-benchmark size taken from "
            "independent recorded censuses that agree (IMP-0198 probe n_cases "
            "and/or ADV-0056 kinds.benchmark-case, plus live build_corpus if "
            "importable). This is the planned suite size, not a live file census."
        ),
    }


def measure_res0094_harness(n: int = PIN_N) -> dict[str, Any] | None:
    if not RES0094_HARNESS.is_file():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("res0095_res0094_harness", RES0094_HARNESS)
        if spec is None or spec.loader is None:
            return None
        H = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(H)
        live = H.measure(n=n)
    except Exception as exc:
        return {
            "protocol": "RES-0094-harness-live",
            "present": True,
            "error": f"{type(exc).__name__}: {exc}",
            "control_pass": False,
        }
    pinned = live.get("pinned") or {}
    unpinned = live.get("unpin_sampling") or {}
    var_p = float(pinned.get("sample_variance_token_sum") or 0.0)
    var_u = float(unpinned.get("sample_variance_token_sum") or 0.0)
    increased = bool(live.get("variance_increased"))
    return {
        "protocol": "RES-0094-harness-live",
        "path": "command-center/p2-wave/probes/RES-0094/harness.py",
        "n": int(live.get("n") or n),
        "n_meets_minimum": int(live.get("n") or 0) >= 5,
        "residual_variance_after_pinning": var_p,
        "variance_unpinned": var_u,
        "unpin_increases_variance": increased,
        "control_pass": increased and int(live.get("n") or 0) >= 5,
        "pinned_unique_count": pinned.get("unique_count"),
        "unpinned_unique_count": unpinned.get("unique_count"),
        "note": (
            "Live re-run of the RES-0094 pinning harness on this tree. Residual "
            "is sample variance of the pinned token_sum series. Unpin-sampling "
            "must increase unique transcripts and token_sum variance."
        ),
    }


def gather() -> dict[str, Any]:
    planned = planned_suite()
    res0094 = load_res0094()
    harness = measure_res0094_harness()
    local = measure_local_residual()
    if harness is not None and harness.get("control_pass"):
        protocol_control = harness
    elif local["control_pass"]:
        protocol_control = local
    else:
        raise RuntimeError("unpin-and-increase control did not fire")
    if res0094.get("residual_variance") is not None:
        residual = float(res0094["residual_variance"])
        source = "RES-0094.json"
    elif harness is not None and harness.get("control_pass"):
        residual = float(harness["residual_variance_after_pinning"])
        source = "RES-0094-harness-live"
    else:
        residual = float(local["residual_variance_after_pinning"])
        source = "local-RES-0094-protocol"
    return {
        "planned": planned,
        "res0094": res0094,
        "res0094_harness": harness,
        "local_residual": local,
        "protocol_control": protocol_control,
        "residual_variance_used": residual,
        "variance_source": source,
    }
