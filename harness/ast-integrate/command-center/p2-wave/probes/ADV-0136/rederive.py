"""Independent re-derivation from raw transport JSONL. Does not import classify_runtime."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _group(event: dict) -> str:
    return str(event.get("council_id") or event.get("comparison_id") or "")


def _declared(event: dict) -> str:
    raw = str(event.get("declared_independence") or "").upper().replace("_", "-")
    return "CROSS-VENDOR" if raw.startswith("CROSS") else "INDEPENDENT"


def _response(event: dict) -> dict:
    r = event.get("response")
    return r if isinstance(r, dict) else {}


def _vendor(event: dict) -> str:
    v = _response(event).get("vendor")
    return str(v).strip() if v is not None else ""


def rederive_from_logs(paths: list[Path]) -> dict:
    """Return the three violation lists using only JSONL response fields."""
    events: list[dict] = []
    for path in paths:
        events.extend(_load_jsonl(path))

    same: list[dict] = []
    declared_only: list[dict] = []
    confound: list[dict] = []

    by_group: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_group[_group(event)].append(event)

    for group, members in by_group.items():
        buckets: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        drivers_by_cmp: dict[str, set[str]] = defaultdict(set)
        arms_by_cmp: dict[str, list[dict]] = defaultdict(list)
        for event in members:
            seat = str(event.get("seat_id") or "")
            resp = _response(event)
            vendor = _vendor(event)
            model = str(resp.get("model") or "").strip()
            ctx = str(resp.get("context_digest") or "").strip()
            if not vendor:
                if _declared(event) in {"CROSS-VENDOR", "INDEPENDENT"}:
                    declared_only.append(
                        {
                            "group": group,
                            "seat_id": seat,
                            "reason": "cross-vendor-or-independent-slot-with-no-response-side-vendor",
                        }
                    )
            elif model and ctx:
                buckets[(vendor, model, ctx)].append(seat)
            driver = str((event.get("driver") or {}).get("model") or "").strip()
            cmp_id = str(event.get("comparison_id") or group)
            if driver:
                drivers_by_cmp[cmp_id].add(driver)
                arms_by_cmp[cmp_id].append(
                    {
                        "seat_id": seat,
                        "driver_model": driver,
                        "response_vendor": vendor or None,
                        "response_model": model or None,
                    }
                )
        for (vendor, model, ctx), seats in buckets.items():
            uniq = sorted(set(seats))
            if len(uniq) >= 2:
                same.append(
                    {
                        "group": group,
                        "seats": uniq,
                        "tuple": {
                            "vendor": vendor,
                            "model": model,
                            "context_digest": ctx,
                        },
                        "reason": "allegedly-independent-seats-share-response-vendor-model-context",
                    }
                )
        for cmp_id, models in drivers_by_cmp.items():
            if len(models) >= 2:
                confound.append(
                    {
                        "comparison_id": cmp_id,
                        "group": group,
                        "drivers": sorted(models),
                        "arms": arms_by_cmp[cmp_id],
                        "reason": "dispatching-agent-model-differs-across-comparison-arms",
                    }
                )

    return {
        "SAME-TUPLE": same,
        "DECLARED-ONLY": declared_only,
        "DRIVER-CONFOUND": confound,
    }
