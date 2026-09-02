"""Cross-vendor participant adapter boundary and loud degradation.

Spec line cited by the catalog: _USER-PROMPTS.md:10983 — do not pretend full
interchangeability; degrade loudly and preserve the work artifact.

Live vendor probing is READ-ONLY: env-name presence only. Credential values
are never printed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

KIND_LOUD = "LOUD_DEGRADATION"
KIND_CAPABLE = "CAPABLE"
KIND_SUB = "SILENT_SUBSTITUTION_ATTEMPT"
KIND_RESEAT = "LOUD_RESEAT"

ENV_NAMES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "CURSOR_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GOOGLE_API_KEY",
)

SPEC_CITE = "_USER-PROMPTS.md:10983"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def env_presence() -> dict[str, str]:
    return {n: ("PRESENT" if os.environ.get(n) else "ABSENT") for n in ENV_NAMES}


def owner_decisions_present(repo: Path) -> bool:
    return (repo / "command-center" / "OWNER-DECISIONS.md").is_file()


def owner_signed_cnl0126(repo: Path) -> bool:
    path = repo / "command-center" / "OWNER-DECISIONS.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return "CNL-0126" in text


def seat_id(seat: dict) -> tuple[str, str]:
    return (str(seat.get("vendor_id") or ""), str(seat.get("model_id") or ""))


def compute_gaps(assumed: dict, advertised: dict) -> list[str]:
    gaps: list[str] = []
    if assumed.get("tool_access") and not advertised.get("tool_access"):
        gaps.append("tool_access")
    if int(advertised.get("context_length") or 0) < int(assumed.get("context_length") or 0):
        gaps.append("context_length")
    if assumed.get("structured_output") and not advertised.get("structured_output"):
        gaps.append("structured_output")
    return gaps


def persist_partial(workdir: Path, body: bytes) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "partial-artifact.bin"
    path.write_bytes(body)
    live = path.read_bytes()
    return {
        "path": str(path),
        "bytes": len(live),
        "sha256": digest_bytes(live),
        "present": live == body,
    }


def negotiate(spec: dict, seat: dict, work: bytes, workdir: Path) -> dict:
    assumed = spec["assumed"]
    advertised = seat["advertised"]
    gaps = compute_gaps(assumed, advertised)
    partial = persist_partial(workdir, work)
    if not gaps:
        rec = {
            "kind": KIND_CAPABLE,
            "user_visible": True,
            "seat": list(seat_id(seat)),
            "capability_lost": [],
        }
        return {
            "verdict": "SUCCESS",
            "gaps": [],
            "degradation": None,
            "partial": partial,
            "audit": [rec],
            "seat": seat,
            "interchangeability_claimed": False,
        }
    rec = {
        "kind": KIND_LOUD,
        "user_visible": True,
        "verdict": "DEGRADED",
        "capability_lost": gaps,
        "assumed": assumed,
        "advertised": advertised,
        "interchangeability_claimed": False,
        "partial_artifact": partial,
        "spec_cite": SPEC_CITE,
        "text": (
            f"LOUD: participant {seat['vendor_id']}:{seat['model_id']} lacks "
            f"{','.join(gaps)}; work artifact preserved sha256={partial['sha256']}; "
            "not interchangeable"
        ),
    }
    return {
        "verdict": "DEGRADED",
        "gaps": gaps,
        "degradation": rec,
        "partial": partial,
        "audit": [rec],
        "seat": seat,
        "interchangeability_claimed": False,
    }


def dispatch(
    spec: dict,
    intended: dict,
    actual: dict,
    work: bytes,
    workdir: Path,
    *,
    silent_swap: bool = False,
) -> dict:
    """Boundary: identity mismatch never becomes SUCCESS; gaps never become SUCCESS."""
    swapped = seat_id(intended) != seat_id(actual)
    if swapped:
        event = {
            "kind": KIND_SUB if silent_swap else KIND_RESEAT,
            "user_visible": True,
            "detected": True,
            "blocked": True,
            "from_vendor": intended.get("vendor_id"),
            "from_model": intended.get("model_id"),
            "to_vendor": actual.get("vendor_id"),
            "to_model": actual.get("model_id"),
            "verdict": "REFUSED",
            "spec_cite": SPEC_CITE,
        }
        if silent_swap:
            partial = persist_partial(workdir, work)
            return {
                "verdict": "REFUSED",
                "gaps": compute_gaps(spec["assumed"], actual["advertised"]),
                "degradation": event,
                "partial": partial,
                "audit": [event],
                "seat": actual,
                "intended": intended,
                "interchangeability_claimed": False,
            }
        inner = negotiate(spec, actual, work, workdir)
        inner["audit"] = [event] + inner["audit"]
        inner["intended"] = intended
        if inner["verdict"] == "SUCCESS":
            inner["verdict"] = "DEGRADED"
        inner["interchangeability_claimed"] = False
        return inner
    inner = negotiate(spec, actual, work, workdir)
    inner["intended"] = intended
    return inner


def buggy_silent_success(intended: dict, substitute: dict) -> dict:
    """Anti-pattern the detector must catch: SUCCESS after an unrecorded reseat."""
    return {
        "verdict": "SUCCESS",
        "gaps": [],
        "degradation": None,
        "partial": None,
        "audit": [],
        "seat": substitute,
        "intended": intended,
        "interchangeability_claimed": True,
        "work_discarded": True,
    }


def mutant_discard(spec: dict, seat: dict) -> dict:
    """Anti-pattern: named degradation but the partial is gone."""
    gaps = compute_gaps(spec["assumed"], seat["advertised"])
    rec = {
        "kind": KIND_LOUD,
        "user_visible": True,
        "capability_lost": gaps,
        "verdict": "DEGRADED",
    }
    return {
        "verdict": "DEGRADED",
        "gaps": gaps,
        "degradation": rec,
        "partial": None,
        "audit": [rec],
        "seat": seat,
        "interchangeability_claimed": False,
    }


def silent_substitution_fires(result: dict, intended: dict) -> dict:
    seat = result.get("seat") or {}
    swapped = seat_id(seat) != seat_id(intended)
    audit = result.get("audit") or []
    has_record = any(
        e.get("kind") in {KIND_SUB, KIND_RESEAT, KIND_LOUD} for e in audit
    )
    success_after_swap = swapped and result.get("verdict") == "SUCCESS"
    missing_audit = swapped and not has_record
    claimed = result.get("interchangeability_claimed") is True
    fires = bool(success_after_swap or missing_audit or claimed)
    reason = "no-substitution"
    if success_after_swap:
        reason = "silent-substitution-success"
    elif claimed:
        reason = "interchangeability-claimed"
    elif missing_audit:
        reason = "swap-without-audit"
    return {
        "fires": fires,
        "swapped": swapped,
        "success_after_swap": success_after_swap,
        "missing_audit": missing_audit,
        "reason": reason,
    }


def preservation_ok(result: dict, original: bytes) -> bool:
    p = result.get("partial") or {}
    path_s = p.get("path")
    if not path_s:
        return False
    path = Path(path_s)
    if not path.is_file():
        return False
    body = path.read_bytes()
    return (
        body == original
        and p.get("sha256") == digest_bytes(original)
        and p.get("present") is True
        and int(p.get("bytes") or 0) == len(original)
    )


def is_loud_gap(result: dict) -> bool:
    if result.get("verdict") != "DEGRADED":
        return False
    if result.get("interchangeability_claimed") is True:
        return False
    rec = result.get("degradation") or {}
    if rec.get("kind") == KIND_LOUD and rec.get("user_visible") is True:
        return True
    return any(
        e.get("kind") == KIND_LOUD and e.get("user_visible") is True
        for e in (result.get("audit") or [])
    )


def lpi(gap_rows: list[dict], silent_sub: bool) -> float:
    if silent_sub:
        return 0.0
    if not gap_rows:
        return 1.0
    n = float(len(gap_rows))
    loud_frac = sum(1 for r in gap_rows if r.get("loud")) / n
    pres_frac = sum(1 for r in gap_rows if r.get("preserved")) / n
    return loud_frac * pres_frac
