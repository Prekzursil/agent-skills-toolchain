#!/usr/bin/env python3
"""Probe 2: guard is silent on a live-only scratch write.

Known-good arm, plus two mechanically different silence controls:
(1) same live prefix as the deployed file but no provenance row;
(2) provenance row removed — the deployed path itself goes silent.
Independent of probe 1's workspace. Re-checks the receipt.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import estate as E  # noqa: E402

ART = REPO / E.ARTIFACT_REL
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact(scratch: dict, removed: dict, prefix: dict) -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0087-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0087-probe2 unparseable {exc}")
        return 1
    if E.SENTINEL not in text:
        print("FAILED:TST-0087-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0087-probe2 self-declared:{st}")
        return 1
    good = (doc.get("both_states") or {}).get("known_good") or {}
    if good.get("silent") is not True:
        print("FAILED:TST-0087-probe2 receipt known_good.silent is not true")
        return 1
    if good.get("path") != scratch["scratch_rel"]:
        print("FAILED:TST-0087-probe2 receipt scratch path drift", good.get("path"))
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_guard_is_silent_on_a_live_only_scratch_path")
    if not row or row.get("result") != "PASS":
        print("FAILED:TST-0087-probe2 catalog test row missing or not PASS")
        return 1
    nc = doc.get("negative_control") or {}
    if nc.get("fired_after_provenance_removed") is True:
        print("FAILED:TST-0087-probe2 receipt claims fire after provenance removed")
        return 1
    if removed.get("pass") is not True or prefix.get("pass") is not True:
        print("FAILED:TST-0087-probe2 live silence controls did not pass")
        return 1
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0087-p2-") as tmp:
        root = Path(tmp)
        scratch = E.run_scratch_silent(root / "scratch")
        prefix = E.run_prefix_only_silent(root / "prefix")
        removed = E.run_provenance_removed(root / "removed")
        repo_ok = E.run_repo_source_silent(root / "repo")
    payload = {
        "probe": "probe2-scratch-silent",
        "unit_id": E.UNIT,
        "scratch_silent": bool(scratch.get("pass")),
        "prefix_only_silent": bool(prefix.get("pass")),
        "provenance_removed_silent": bool(removed.get("pass")),
        "repo_source_silent": bool(repo_ok.get("pass")),
        "scratch_rel": scratch.get("scratch_rel"),
        "scratch_write_path": scratch.get("live_write_path"),
        "pass": bool(
            scratch.get("pass")
            and prefix.get("pass")
            and removed.get("pass")
            and repo_ok.get("pass")
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0087-probe2 silence controls")
        print(json.dumps({"scratch": scratch, "prefix": prefix, "removed": removed, "repo": repo_ok}, indent=2, default=str)[:4000])
        return 1
    if _check_artifact(scratch, removed, prefix) != 0:
        return 1
    print(
        f"scratch_silent={payload['scratch_silent']} "
        f"prefix_only_silent={payload['prefix_only_silent']} "
        f"provenance_removed_silent={payload['provenance_removed_silent']}"
    )
    print("SUCCESS:TST-0087-probe2 silent on live-only scratch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
