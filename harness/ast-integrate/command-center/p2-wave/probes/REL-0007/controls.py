"""Run REL-0007 required tests and reviewer mutation re-runs on disposable profiles."""
from __future__ import annotations

import tempfile
from pathlib import Path

import overclaim as O
import profile as P
import sweep as S
from surfaces import CHECKED_SURFACE_IDS, PACKAGE_HOOK_ID, REQUIRED_IDS


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="rel0007-"))


def test_plant_orphan_hook() -> dict:
    root = _tmp()
    P.seed_preexisting(root)
    P.install(root)
    P.uninstall_leave_hook(root)
    report = S.sweep(root)
    fired = PACKAGE_HOOK_ID in report["orphan_ids"]
    return {
        "id": "plant-orphan-hook",
        "result": "PASS" if fired else "FAIL",
        "detail": f"orphans={report['orphan_ids']} payload_present={report['payload_present']}",
        "expected": "FIRED",
        "observed": "FIRED" if fired else "SILENT",
    }


def test_detector_control() -> dict:
    root = _tmp()
    P.seed_preexisting(root)
    P.install(root)
    P.uninstall_clean(root)
    P.plant_detector_hook(root)
    try:
        seen = S.sweep(root, require_detector=True)
        found = True
        err = ""
    except S.DetectorBlind as exc:
        found = False
        err = str(exc)
        seen = {}
    P.unplant_detector_hook(root)
    refused = False
    try:
        S.sweep(root, require_detector=True)
    except S.DetectorBlind:
        refused = True
    ok = found and refused
    return {
        "id": "detector-control",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            f"found={found} refuses_zero_when_absent={refused} "
            f"err={err} seen={seen.get('orphan_ids')}"
        ),
        "expected": "FIRED",
        "observed": "FIRED" if found else "SILENT",
    }


def test_clean_uninstall_zero() -> dict:
    root = _tmp()
    P.seed_preexisting(root)
    before = P.snapshot_owner(root)
    P.install(root)
    P.uninstall_clean(root)
    after = P.snapshot_owner(root)
    report = S.trusted_zero_sweep(root, P)
    owner_intact = before == after
    zero = report["orphan_count"] == 0 and report["zero_orphans_on_checked_surfaces"]
    ids_ok = set(report["checked_surface_ids"]) == set(CHECKED_SURFACE_IDS)
    det = (report.get("detector_control") or {}).get("found_before_zero") is True
    ok = owner_intact and zero and ids_ok and det
    return {
        "id": "clean-uninstall-zero",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            f"owner_intact={owner_intact} zero={zero} ids_ok={ids_ok} det={det} "
            f"orphans={report['orphan_ids']} hash_delta={_delta(before, after)}"
        ),
        "report": report,
        "expected": "SILENT",
        "observed": "SILENT" if zero else "FIRED",
    }


def test_unqueryable_not_checked() -> dict:
    root = _tmp()
    P.seed_preexisting(root)
    P.install(root)
    P.uninstall_clean(root)
    report = S.sweep(root)
    enumerated_ids = [r["id"] for r in report["enumerated"]]
    missing = [i for i in REQUIRED_IDS if i not in enumerated_ids]
    nc = [r for r in report["enumerated"] if r["status"] == "NOT-CHECKED"]
    (root / "settings.json").write_text("{not json", encoding="utf-8")
    corrupted = S.sweep(root)
    settings_row = next(r for r in corrupted["enumerated"] if r["id"] == "settings")
    induced = settings_row["status"] == "NOT-CHECKED"
    ok = not missing and len(nc) >= 1 and induced
    return {
        "id": "unqueryable-not-checked",
        "result": "PASS" if ok else "FAIL",
        "detail": f"missing={missing} not_checked={len(nc)} induced_settings={settings_row['status']}",
        "expected": "NOT-CHECKED",
        "observed": "NOT-CHECKED" if ok else "OMITTED-OR-ZERO",
        "enumerated": report["enumerated"],
        "not_checked": report["not_checked"],
    }


def test_payload_only_still_orphans() -> dict:
    root = _tmp()
    P.seed_preexisting(root)
    P.install(root)
    P.uninstall_payload_only(root)
    honest = S.sweep(root)
    lie = S.liar_payload_dir_as_zero(root)
    ok = honest["orphan_count"] > 0 and lie["orphan_count"] == 0 and not honest["payload_present"]
    return {
        "id": "payload-dir-is-not-the-verdict",
        "result": "PASS" if ok else "FAIL",
        "detail": (
            f"honest={honest['orphan_count']} liar={lie['orphan_count']} "
            f"payload={honest['payload_present']}"
        ),
        "expected": "FIRED",
        "observed": "FIRED" if honest["orphan_count"] > 0 else "SILENT",
    }


def _delta(a: dict, b: dict) -> dict:
    return {k: (a.get(k), b.get(k)) for k in set(a) | set(b) if a.get(k) != b.get(k)}


def reviewer_mutations(clean_doc: dict) -> list[dict]:
    rows = []
    for name, mutant in (
        ("omit-not-checked", O.mutant_omit_not_checked(clean_doc)),
        ("zero-without-detector", O.mutant_zero_without_detector(clean_doc)),
        ("payload-as-verdict", O.mutant_payload_as_verdict(clean_doc)),
    ):
        ok, why = O.check_receipt(mutant)
        red = not ok
        rows.append(
            {
                "id": name,
                "gate_red": red,
                "why": why,
                "result": "PASS" if red else "FAIL",
            }
        )
    plant = test_plant_orphan_hook()
    rows.append(
        {
            "id": "leave-hook-live",
            "gate_red": plant["observed"] == "FIRED",
            "why": plant["detail"],
            "result": "PASS" if plant["observed"] == "FIRED" else "FAIL",
        }
    )
    return rows


def run_all() -> dict:
    tests = [
        test_plant_orphan_hook(),
        test_detector_control(),
        test_clean_uninstall_zero(),
        test_unqueryable_not_checked(),
        test_payload_only_still_orphans(),
    ]
    return {"tests": tests}
