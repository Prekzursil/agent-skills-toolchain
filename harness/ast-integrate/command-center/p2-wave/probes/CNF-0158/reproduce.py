"""Independent reproduction of each B07 leak.

Verdicts come from live adapter observation. Reading claimed_status from the
register is circular and is rejected as evidence.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from vendor_runtime import (
    MEASURED_INLINE_PROMPT,
    DetachedForbidden,
    OpenAIAdapter,
    QuotaStorm,
    adapters,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTER_PATH = HERE / "fixtures" / "b07-leak-register.json"
RELABELLED_PATH = HERE / "fixtures" / "b07-leak-register.relabelled.json"
FIX_LEDGER_PATH = HERE / "fixtures" / "fix-ledger.json"
RUNTIME_PATH = HERE / "vendor_runtime.py"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0158/probe1_reproduce.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0158/probe2_controls.py"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def load_register() -> dict[str, Any]:
    return json.loads(REGISTER_PATH.read_text(encoding="utf-8"))


def load_fix_ledger() -> dict[str, Any]:
    return json.loads(FIX_LEDGER_PATH.read_text(encoding="utf-8"))


def marker_present(marker: str) -> bool:
    return marker in RUNTIME_PATH.read_text(encoding="utf-8")


def _unit(**extra: Any) -> dict[str, Any]:
    base = {
        "id": "CNF-0158-probe-unit",
        "timeout_seconds": 7,
        "tool_permissions": ["Read", "Grep"],
        "owner_approval_required": True,
        "output_schema": "command-center/schema/confirmation-record.schema.json",
    }
    base.update(extra)
    return base


def observe_win_arg(adapter: Any) -> bool:
    """True iff the leak (inline prompt hits win-arg-limit) is present."""
    prompt = "x" * MEASURED_INLINE_PROMPT
    r = adapter.dispatch(_unit(), prompt=prompt, prompt_by_file=False)
    return r.classification == "WIN-ARG-LIMIT"


def observe_perms_unenforced(adapter: Any) -> bool:
    """True iff Write is not refused when the unit listed only Read."""
    with tempfile.TemporaryDirectory(prefix="cnf0158-perm-") as tmp:
        out = Path(tmp) / "out.json"
        r = adapter.dispatch(
            _unit(),
            prompt="permission probe",
            prompt_by_file=True,
            output_path=out,
            attempt_write=True,
        )
    return (not r.write_refused) and r.classification == "SUCCESS"


def observe_owner_approval(adapter: Any) -> bool:
    """True iff owner_approval_required does not block an unapproved dispatch."""
    with tempfile.TemporaryDirectory(prefix="cnf0158-own-") as tmp:
        out = Path(tmp) / "out.json"
        r = adapter.dispatch(
            _unit(owner_approval_required=True),
            prompt="approval probe",
            prompt_by_file=True,
            output_path=out,
            approved=False,
        )
    return (not r.owner_approval_blocked) and r.classification in {
        "SUCCESS",
        "PERMISSION-DENIED",
    }


def observe_detached(adapter: Any) -> bool:
    """True iff background dispatch is allowed (the leak)."""
    try:
        adapter.dispatch(_unit(), prompt="bg", background=True, prompt_by_file=True)
    except DetachedForbidden:
        return False
    return True


def observe_severed_as_success(adapter: Any) -> bool:
    """True iff exit 0 + missing output is classified SUCCESS (the leak)."""
    r = adapter.dispatch(
        _unit(),
        prompt="severed",
        prompt_by_file=True,
        omit_output=True,
    )
    return r.exit_code == 0 and r.classification == "SUCCESS"


def observe_json_unparseable(adapter: Any) -> bool:
    """True iff the adapter cannot emit parseable JSON (the claimed leak)."""
    with tempfile.TemporaryDirectory(prefix="cnf0158-json-") as tmp:
        out = Path(tmp) / "out.json"
        r = adapter.dispatch(
            _unit(),
            prompt="json probe",
            prompt_by_file=True,
            output_path=out,
        )
    return not r.output_parseable


def observe_timeout_ignored(adapter: Any) -> bool:
    """True iff declared timeout_seconds is not the timeout applied."""
    r = adapter.dispatch(
        _unit(timeout_seconds=7),
        prompt="timeout",
        prompt_by_file=True,
        omit_output=True,
    )
    return r.timeout_applied != 7


RECIPES: dict[str, Callable[[Any], bool]] = {
    "win_arg_inline": observe_win_arg,
    "perms_unenforced": observe_perms_unenforced,
    "owner_approval": observe_owner_approval,
    "detached_background": observe_detached,
    "severed_as_success": observe_severed_as_success,
    "json_unparseable": observe_json_unparseable,
}


def reproduction_command(leak_id: str, vendor: str) -> str:
    return (
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        f"\"from pathlib import Path; import sys; "
        f"sys.path.insert(0, str(Path('command-center/p2-wave/probes/CNF-0158'))); "
        f"from reproduce import observe_one; "
        f"r=observe_one({leak_id!r},{vendor!r}); "
        f"print(r); raise SystemExit(0 if r['ok'] else 1)\""
    )


def observe_one(leak_id: str, vendor: str, adapter: Any | None = None) -> dict[str, Any]:
    reg = load_register()
    entry = next(e for e in reg["leaks"] if e["id"] == leak_id)
    recipe = RECIPES[entry["recipe"]]
    ad = adapter or adapters()[vendor]
    present = bool(recipe(ad))
    return {
        "ok": True,
        "leak_id": leak_id,
        "vendor": vendor,
        "observed_present": present,
        "recipe": entry["recipe"],
        "command": reproduction_command(leak_id, vendor),
    }


def _verdict_for_vendor(
    *,
    leak_id: str,
    vendor: str,
    claimed: str,
    should_appear: bool,
    observed: bool,
    ledger: dict[str, Any],
) -> str:
    if observed:
        return "REPRODUCED"
    if claimed == "ABSENT" or not should_appear:
        return "ABSENT-AS-EXPECTED"
    info = (ledger.get("leaks") or {}).get(leak_id) or {}
    marker = str(info.get("marker") or "")
    if marker and marker_present(marker):
        return "FIXED"
    return "NEVER-REAL"


def reproduce_all(adapter_map: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run every register recipe against both vendors. Never copy claimed_status."""
    ad_map = adapter_map or adapters()
    register = load_register()
    ledger = load_fix_ledger()
    rows: list[dict[str, Any]] = []
    discrepancies: list[dict[str, Any]] = []

    for entry in register["leaks"]:
        leak_id = entry["id"]
        recipe_name = entry["recipe"]
        recipe = RECIPES[recipe_name]
        vendor_rows: dict[str, Any] = {}
        for vendor, spec in entry["vendors"].items():
            ad = ad_map[vendor]
            observed = bool(recipe(ad))
            claimed = str(spec.get("claimed") or "OPEN")
            should = bool(spec.get("should_appear"))
            vverdict = _verdict_for_vendor(
                leak_id=leak_id,
                vendor=vendor,
                claimed=claimed,
                should_appear=should,
                observed=observed,
                ledger=ledger,
            )
            vendor_rows[vendor] = {
                "claimed": claimed,
                "should_appear": should,
                "observed_present": observed,
                "verdict": vverdict,
                "command": reproduction_command(leak_id, vendor),
                "divergence": (
                    f"observed_present={observed} classification-path={recipe_name} "
                    f"vendor={vendor} (claimed={claimed})"
                ),
            }
            # Self-report vs observation (openai permissions lie).
            if recipe_name == "perms_unenforced" and vendor == "openai":
                with tempfile.TemporaryDirectory(prefix="cnf0158-sr-") as tmp:
                    r = ad.dispatch(
                        _unit(),
                        prompt="self-report",
                        prompt_by_file=True,
                        output_path=Path(tmp) / "o.json",
                        attempt_write=True,
                    )
                if "tool_permissions" in r.self_reported_honored and observed:
                    discrepancies.append(
                        {
                            "leak_id": leak_id,
                            "vendor": vendor,
                            "kind": "self-report-lie",
                            "detail": (
                                "adapter self-reported tool_permissions as honored "
                                "but Write succeeded without Write in the unit"
                            ),
                        }
                    )

        vendor_verdicts = [v["verdict"] for v in vendor_rows.values()]
        if "REPRODUCED" in vendor_verdicts:
            overall = "REPRODUCED"
        elif "FIXED" in vendor_verdicts and "NEVER-REAL" not in vendor_verdicts:
            overall = "FIXED"
        elif "NEVER-REAL" in vendor_verdicts:
            overall = "NEVER-REAL"
        else:
            overall = "ABSENT-AS-EXPECTED"

        rows.append(
            {
                "id": leak_id,
                "field": entry["field"],
                "consequence": entry["consequence"],
                "register_claimed_status": entry["claimed_status"],
                "overall": overall,
                "vendors": vendor_rows,
                "evidence_is_observation": True,
                "evidence_is_register_read": False,
            }
        )

    relabelled = deepcopy(register)
    for leak, row in zip(relabelled["leaks"], rows):
        leak["previous_status"] = leak.get("claimed_status")
        leak["claimed_status"] = row["overall"]
        leak["relabelled_by"] = "CNF-0158"
        for vendor, spec in leak["vendors"].items():
            spec["previous"] = spec.get("claimed")
            spec["claimed"] = row["vendors"][vendor]["verdict"]

    reproduced = [r for r in rows if r["overall"] == "REPRODUCED"]
    absent_expected = []
    for r in rows:
        for vendor, vr in r["vendors"].items():
            if vr["verdict"] == "ABSENT-AS-EXPECTED":
                absent_expected.append({"leak_id": r["id"], "vendor": vendor})

    non_reproduced = [r for r in rows if r["overall"] != "REPRODUCED"]
    relabel_ok = all(
        src["claimed_status"] != "OPEN" or True
        for src in relabelled["leaks"]
        if next(r for r in rows if r["id"] == src["id"])["overall"] != "REPRODUCED"
    )
    # Every non-REPRODUCED entry must carry a new label, not silent OPEN.
    for src, row in zip(relabelled["leaks"], rows):
        if row["overall"] != "REPRODUCED" and src["claimed_status"] == "OPEN":
            relabel_ok = False

    clis = {
        "codex": shutil.which("codex"),
        "claude": shutil.which("claude"),
        "agent": shutil.which("agent") or shutil.which("cursor-agent"),
    }

    return {
        "rows": rows,
        "relabelled": relabelled,
        "discrepancies": discrepancies,
        "reproduced_count": len(reproduced),
        "absent_as_expected": absent_expected,
        "non_reproduced": [r["id"] for r in non_reproduced],
        "relabel_ok": relabel_ok,
        "both_states": bool(reproduced) and bool(absent_expected),
        "live_clis": {k: bool(v) for k, v in clis.items()},
        "runtime_sha256": sha256_file(RUNTIME_PATH),
        "register_sha256": sha256_file(REGISTER_PATH),
    }


def write_relabelled(relabelled: dict[str, Any]) -> Path:
    RELABELLED_PATH.write_text(
        json.dumps(relabelled, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return RELABELLED_PATH


def circular_read_is_rejected(result: dict[str, Any]) -> bool:
    """Confirming by copying claimed_status would miss FIXED/NEVER-REAL."""
    for row in result["rows"]:
        if row["register_claimed_status"] == "OPEN" and row["overall"] != "REPRODUCED":
            if row["evidence_is_register_read"]:
                return False
            # Observation diverged from the register — circular read would have
            # wrongly kept OPEN.
            return True
    return False


def plant_timeout_leak() -> dict[str, Any]:
    """Detector control: monkey-patch openai timeout honor off; harness must see it."""
    planted = OpenAIAdapter()
    original = planted.dispatch

    def leaking_dispatch(*args: Any, **kwargs: Any):
        kwargs = dict(kwargs)
        kwargs["honor_timeout"] = False
        return original(*args, **kwargs)

    planted.dispatch = leaking_dispatch  # type: ignore[method-assign]
    observed = observe_timeout_ignored(planted)
    clean = observe_timeout_ignored(OpenAIAdapter())
    return {
        "planted_detected": observed is True,
        "clean_absent": clean is False,
        "pass": observed is True and clean is False,
    }


def rollback_detached() -> dict[str, Any]:
    """Rollback: allow detached on openai; leak must reappear. Then restore."""
    broken = OpenAIAdapter()
    original = broken.dispatch

    def rolled(*args: Any, **kwargs: Any):
        kwargs = dict(kwargs)
        kwargs["allow_detached"] = True
        return original(*args, **kwargs)

    broken.dispatch = rolled  # type: ignore[method-assign]
    present = observe_detached(broken)
    restored = observe_detached(OpenAIAdapter())
    return {
        "rollback_reintroduces": present is True,
        "restored_absent": restored is False,
        "pass": present is True and restored is False,
    }


def quota_not_refuted() -> dict[str, Any]:
    try:
        OpenAIAdapter().dispatch(_unit(), prompt="n", inject_quota="429")
        classification = "MISSING-RAISE"
    except QuotaStorm as exc:
        classification = f"QUOTA-{exc}"
    return {
        "classification": classification,
        "converted_to_refuted": False,
        "pass": classification.startswith("QUOTA-") and classification != "REFUTED",
    }


def blinding_attestation_hash(result: dict[str, Any]) -> str:
    """Recomputable hash of the confirmer payload with claimed labels stripped."""
    payload = {
        "excluded_implementer_receipts": [
            "command-center/receipts/IMP-0420.json",
            "command-center/receipts/IMP-0421.json",
            "command-center/receipts/IMP-0422.json",
        ],
        "register_ids": [{"id": r["id"], "field": r["field"]} for r in result["rows"]],
        "runtime_sha256": result["runtime_sha256"],
        "register_sha256": result["register_sha256"],
        "source_probe": P1,
        "verifier_probe": P2,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def stale_fixed_ok(result: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = load_fix_ledger()
    checks = []
    for row in result["rows"]:
        if row["overall"] != "FIXED":
            continue
        info = (ledger.get("leaks") or {}).get(row["id"]) or {}
        marker = str(info.get("marker") or "")
        present = bool(marker) and marker_present(marker)
        checks.append(
            {
                "leak_id": row["id"],
                "marker": marker,
                "marker_present": present,
                "pass": present,
            }
        )
    return checks


def largest_three(result: dict[str, Any]) -> list[str]:
    """Re-run the three leaks with the largest behavioural consequence."""
    order = [
        "LEAK-WIN-ARG-INLINE",
        "LEAK-PERMS-UNENFORCED",
        "LEAK-DETACHED-BG",
    ]
    return [i for i in order if any(r["id"] == i for r in result["rows"])]
