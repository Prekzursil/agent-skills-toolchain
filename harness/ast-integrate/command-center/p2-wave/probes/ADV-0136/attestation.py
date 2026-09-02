"""Response-side independence attestation. Request labels are never the tuple."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
EVENTS = FIXTURES / "events"
LOGS = FIXTURES / "logs"
PROMPTS = FIXTURES / "prompts"

COUNCILS = (
    "planted-collusion",
    "planted-driver-confound",
    "planted-declared-only",
    "known-good",
)

TUPLE_FIELDS = ("vendor", "model", "context_digest")


def sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _as_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else {}


def materialize(event: dict, repo: Path = REPO) -> dict:
    """Fill response-side digests from files. Never invent a vendor."""
    out = json.loads(json.dumps(event))
    response = _as_dict(out.get("response"))
    prompt_rel = out.get("prompt_file") or response.get("prompt_file")
    ctx_rel = out.get("context_bundle_file") or prompt_rel
    if prompt_rel:
        p = repo / str(prompt_rel)
        if p.is_file():
            response["prompt_file_digest"] = sha256_file(p)
            response["prompt_file"] = str(prompt_rel).replace("\\", "/")
    if ctx_rel:
        p = repo / str(ctx_rel)
        if p.is_file():
            response["context_digest"] = sha256_file(p)
            response["context_bundle_file"] = str(ctx_rel).replace("\\", "/")
    out["response"] = response
    return out


def load_events_file(path: Path, repo: Path = REPO) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        rows = list(raw.get("events") or [])
    else:
        rows = list(raw)
    return [materialize(e, repo) for e in rows if isinstance(e, dict)]


def dump_jsonl(events: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(e, sort_keys=True, separators=(",", ":")) for e in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def write_runtime_logs(repo: Path = REPO) -> dict[str, Path]:
    written: dict[str, Path] = {}
    for name in COUNCILS:
        src = EVENTS / f"{name}.json"
        dst = LOGS / f"{name}.jsonl"
        events = load_events_file(src, repo)
        dump_jsonl(events, dst)
        written[name] = dst
    return written


def load_runtime_logs(repo: Path = REPO, materialize_first: bool = True) -> list[dict]:
    if materialize_first:
        write_runtime_logs(repo)
    rows: list[dict] = []
    for name in COUNCILS:
        rows.extend(load_jsonl(LOGS / f"{name}.jsonl"))
    return rows


def independence_group(event: dict) -> str:
    return str(
        event.get("council_id")
        or event.get("comparison_id")
        or event.get("independence_group")
        or "ungrouped"
    )


def declared_independence(event: dict) -> str:
    raw = str(event.get("declared_independence") or "").upper().replace("_", "-")
    if raw in {"CROSS-VENDOR", "CROSSVENDOR"}:
        return "CROSS-VENDOR"
    return "INDEPENDENT"


def response_vendor(event: dict) -> str | None:
    vendor = _as_dict(event.get("response")).get("vendor")
    if vendor is None:
        return None
    text = str(vendor).strip()
    return text or None


def response_tuple(event: dict) -> tuple[str, str, str] | None:
    response = _as_dict(event.get("response"))
    vendor = response_vendor(event)
    model = str(response.get("model") or "").strip()
    ctx = str(response.get("context_digest") or "").strip()
    if not vendor or not model or not ctx:
        return None
    return (vendor, model, ctx)


def attestation_attempts(event: dict) -> int:
    n = event.get("attestation_attempts")
    if isinstance(n, int):
        return n
    attempts = event.get("attempts")
    if isinstance(attempts, list):
        return len(attempts)
    return 0


def seat_coverage(event: dict) -> str:
    """RESPONSE-ATTESTED, DECLARED-ONLY, or UNMEASURED (adverse-inference)."""
    declared = declared_independence(event)
    vendor = response_vendor(event)
    tup = response_tuple(event)
    attempts = attestation_attempts(event)
    if tup is not None:
        return "RESPONSE-ATTESTED"
    if vendor is None and declared in {"CROSS-VENDOR", "INDEPENDENT"}:
        if _as_dict(event.get("response")) or attempts >= 3:
            return "DECLARED-ONLY"
    if attempts >= 3:
        return "DECLARED-ONLY"
    return "UNMEASURED"


def classify_runtime(events: list[dict]) -> dict:
    """Compute the three violation kinds from response-side records only."""
    same_tuple: list[dict] = []
    declared_only: list[dict] = []
    driver_confound: list[dict] = []
    seats: list[dict] = []

    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        grouped[independence_group(event)].append(event)

    for group, members in grouped.items():
        attested_by_tuple: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        drivers: dict[str, set[str]] = defaultdict(set)
        for event in members:
            seat_id = str(event.get("seat_id") or "")
            declared = declared_independence(event)
            coverage = seat_coverage(event)
            response = _as_dict(event.get("response"))
            request = _as_dict(event.get("request"))
            driver = str(_as_dict(event.get("driver")).get("model") or "").strip()
            comparison = str(event.get("comparison_id") or group)
            tup = response_tuple(event)
            rec = {
                "seat_id": seat_id,
                "council_id": group,
                "comparison_id": comparison,
                "declared_independence": declared,
                "declared_role": str(event.get("declared_role") or request.get("label") or ""),
                "coverage": "DECLARED-ONLY"
                if coverage == "UNMEASURED" and declared
                else coverage,
                "transport": response.get("transport"),
                "vendor_endpoint": response.get("vendor_endpoint"),
                "vendor": response.get("vendor"),
                "model": response.get("model"),
                "context_digest": response.get("context_digest"),
                "prompt_file_digest": response.get("prompt_file_digest"),
                "seed": response.get("seed"),
                "driver_model": driver or None,
                "request_side_not_used": {
                    "requested_vendor": request.get("requested_vendor"),
                    "requested_model": request.get("requested_model"),
                    "label": request.get("label") or event.get("declared_role"),
                },
                "attestation_attempts": attestation_attempts(event),
                "source": "runtime-log",
            }
            if coverage == "UNMEASURED":
                rec["coverage"] = "RESPONSE-ATTESTED" if tup else "DECLARED-ONLY"
                rec["adverse_inference"] = "SAME-TUPLE"
                same_tuple.append(
                    {
                        "group": group,
                        "seats": [seat_id],
                        "tuple": None,
                        "reason": "adverse-inference:absent-attestation-treated-as-SAME-TUPLE-until-measured",
                    }
                )
            elif coverage == "DECLARED-ONLY":
                rec["coverage"] = "DECLARED-ONLY"
                declared_only.append(
                    {
                        "group": group,
                        "seat_id": seat_id,
                        "reason": "cross-vendor-or-independent-slot-with-no-response-side-vendor",
                    }
                )
            elif tup is not None:
                rec["coverage"] = "RESPONSE-ATTESTED"
                rec["tuple"] = {
                    "vendor": tup[0],
                    "model": tup[1],
                    "context_digest": tup[2],
                }
                attested_by_tuple[tup].append(event)
            if driver:
                drivers[comparison].add(driver)
            seats.append(rec)

        for tup, hits in attested_by_tuple.items():
            independent_hits = [
                h
                for h in hits
                if declared_independence(h) in {"INDEPENDENT", "CROSS-VENDOR"}
            ]
            if len(independent_hits) >= 2:
                same_tuple.append(
                    {
                        "group": group,
                        "seats": sorted(str(h.get("seat_id") or "") for h in independent_hits),
                        "tuple": {
                            "vendor": tup[0],
                            "model": tup[1],
                            "context_digest": tup[2],
                        },
                        "reason": "allegedly-independent-seats-share-response-vendor-model-context",
                    }
                )

        for comparison, models in drivers.items():
            if len(models) >= 2:
                arms = []
                for event in members:
                    if str(event.get("comparison_id") or group) != comparison:
                        continue
                    arms.append(
                        {
                            "seat_id": event.get("seat_id"),
                            "driver_model": _as_dict(event.get("driver")).get("model"),
                            "response_vendor": _as_dict(event.get("response")).get("vendor"),
                            "response_model": _as_dict(event.get("response")).get("model"),
                        }
                    )
                driver_confound.append(
                    {
                        "comparison_id": comparison,
                        "group": group,
                        "drivers": sorted(models),
                        "arms": arms,
                        "reason": "dispatching-agent-model-differs-across-comparison-arms",
                    }
                )

    return {
        "seats": seats,
        "violations": {
            "SAME-TUPLE": same_tuple,
            "DECLARED-ONLY": declared_only,
            "DRIVER-CONFOUND": driver_confound,
        },
    }


def naive_same_tuple_by_label(events: list[dict]) -> list[dict]:
    """Incorrect checker: only collides seats that also share declared_role.

    Planted collusion uses two role labels for one response tuple; this checker
    is SILENT on that state. The real checker reads the tuple, not the label.
    """
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for event in events:
        tup = response_tuple(event)
        if tup is None:
            continue
        role = str(event.get("declared_role") or _as_dict(event.get("request")).get("label") or "")
        grouped[(independence_group(event), role, tup)].append(event)
    hits = []
    for (group, role, tup), members in grouped.items():
        if len(members) >= 2:
            hits.append(
                {
                    "group": group,
                    "declared_role": role,
                    "seats": sorted(str(m.get("seat_id") or "") for m in members),
                    "tuple": {
                        "vendor": tup[0],
                        "model": tup[1],
                        "context_digest": tup[2],
                    },
                }
            )
    return hits


def violation_fingerprint(violations: dict) -> dict:
    same = []
    for row in violations.get("SAME-TUPLE") or []:
        same.append(
            (
                str(row.get("group") or ""),
                tuple(sorted(row.get("seats") or [])),
                str((row.get("tuple") or {}).get("vendor") or ""),
                str((row.get("tuple") or {}).get("model") or ""),
            )
        )
    declared = []
    for row in violations.get("DECLARED-ONLY") or []:
        declared.append((str(row.get("group") or ""), str(row.get("seat_id") or "")))
    driver = []
    for row in violations.get("DRIVER-CONFOUND") or []:
        driver.append(
            (
                str(row.get("comparison_id") or row.get("group") or ""),
                tuple(sorted(row.get("drivers") or [])),
            )
        )
    return {
        "SAME-TUPLE": sorted(same),
        "DECLARED-ONLY": sorted(declared),
        "DRIVER-CONFOUND": sorted(driver),
    }


def ledger_payload(doc: dict) -> dict:
    """Domain payload lives under report when kind is attestation-ledger."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if str(report.get("kind") or "") == "attestation-ledger":
        return report
    return doc


def council_events(all_events: list[dict], council_id: str) -> list[dict]:
    return [e for e in all_events if independence_group(e) == council_id]


def control_fired(events: list[dict], kind: str) -> bool:
    v = classify_runtime(events)["violations"]
    return bool(v.get(kind))
