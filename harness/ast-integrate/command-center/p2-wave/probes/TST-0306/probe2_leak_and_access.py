#!/usr/bin/env python3
"""Probe 2: leak audit + redraw + access control.

Catalog tests_required / evidence:
  * Leak audit: grep the program corpus, prompts and fixtures for shadow-case
    ids; any hit invalidates the split and forces a re-draw.
  * Access control: who or what could have seen the shadow split, evidenced
    by file permissions and the access log.

Independent of probe 1 (fresh session, different seed). Does not print
shadow-case ids.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.shadow_split import (  # noqa: E402
    FORBIDDEN_PURPOSES,
    VAULT_REL,
    ShadowSplitError,
    access_control_rejects_open_vault,
    audit_and_redraw_if_leaked,
    contains_any_id,
    draw_session,
    leak_audit,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0306-probe2 {msg}")
    return 1


def live_tree_audit() -> dict:
    vault = REPO / VAULT_REL / "split.json"
    if not vault.is_file():
        return {"present": False, "ok": True, "skipped": True, "hit_count": 0}
    payload = json.loads(vault.read_text(encoding="utf-8"))
    ids = [str(c["id"]) for c in payload.get("shadow_cases") or []]
    hits = leak_audit(REPO, ids)
    mode = vault.stat().st_mode & 0o777
    log_path = vault.parent / "ACCESS.log"
    log_rows = 0
    if log_path.is_file():
        log_rows = sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "present": True,
        "skipped": False,
        "ok": len(hits) == 0 and (mode & 0o044) == 0,
        "hit_count": len(hits),
        "hits": hits,
        "mode_octal": format(mode, "o").zfill(3),
        "access_log_rows": log_rows,
    }


def receipt_has_no_live_ids() -> dict:
    receipt = REPO / "command-center" / "receipts" / "TST-0306.json"
    vault = REPO / VAULT_REL / "split.json"
    if not receipt.is_file() or not vault.is_file():
        return {"present": False, "ok": True, "skipped": True}
    ids = [
        str(c["id"])
        for c in json.loads(vault.read_text(encoding="utf-8")).get("shadow_cases") or []
    ]
    text = receipt.read_text(encoding="utf-8")
    leaked = contains_any_id(text, ids)
    return {"present": True, "ok": not leaked, "skipped": False, "leaked": leaked}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tst0306-p2-"))
    session = draw_session(tmp, seed="tst-0306-probe2-v1")

    clean = audit_and_redraw_if_leaked(session)
    payload_ids = session.open_vault("detector", "leak-audit")
    ids = [str(c["id"]) for c in payload_ids["shadow_cases"]]
    planted = tmp / "prompts" / "system.md"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_text(f"fixture special-case {ids[0]} in the prompt\n", encoding="utf-8")
    fixtures = tmp / "fixtures" / "notes.json"
    fixtures.parent.mkdir(parents=True, exist_ok=True)
    fixtures.write_text("{}\n", encoding="utf-8")

    leaked = audit_and_redraw_if_leaked(session)
    after_ids_doc = session.open_vault("detector", "leak-audit")
    after_ids = [str(c["id"]) for c in after_ids_doc["shadow_cases"]]
    old_id_still_shadow = ids[0] in after_ids
    planted_still_matches_new = contains_any_id(
        planted.read_text(encoding="utf-8"), after_ids
    )

    impl_text = session.implementer_visible_text()
    impl_leaks = contains_any_id(impl_text, after_ids)

    tune_denied = False
    try:
        session.open_vault("implementer", "tune")
    except ShadowSplitError:
        tune_denied = True
    train_denied = False
    try:
        session.open_vault("implementer", "train")
    except ShadowSplitError:
        train_denied = True

    world = access_control_rejects_open_vault(session)
    ac = session.access_control_report()
    log_rows = session.read_access_log()
    actors = sorted({r.get("actor") for r in log_rows if r.get("actor")})
    purposes = sorted({r.get("purpose") for r in log_rows if r.get("purpose")})

    live = live_tree_audit()
    receipt_clean = receipt_has_no_live_ids()

    checks = {
        "clean_tree_silent": clean["invalidated"] is False and clean["hit_count"] == 0,
        "planted_prompt_invalidates": leaked["invalidated"] is True,
        "planted_hit_count": leaked["hit_count"] >= 1,
        "redraw_forced": leaked["redraws"] >= 1,
        "redraw_changed_idset": leaked["idset_before"] != leaked["idset_after"],
        "redraw_clears_new_ids_from_planted_prompt": leaked["clean_after_redraw"] is True
        and planted_still_matches_new is False,
        "retired_id_not_in_new_shadow": old_id_still_shadow is False,
        "implementer_manifest_has_no_shadow_ids": impl_leaks is False,
        "tune_purpose_denied": tune_denied,
        "train_purpose_denied": train_denied,
        "forbidden_includes_tune": "tune" in FORBIDDEN_PURPOSES,
        "world_readable_vault_denied": world["ok"] is True,
        "vault_mode_owner_only": ac["ok"] is True and ac["world_or_group_readable"] is False,
        "access_log_nonempty": len(log_rows) >= 1,
        "access_log_records_actor": "detector" in actors or "harness" in actors,
        "live_tree_ok": live["ok"] is True,
        "receipt_ok": receipt_clean["ok"] is True,
    }
    payload = {
        "probe": "probe2-leak-audit-and-access",
        "unit_id": "TST-0306",
        "pass": all(checks.values()),
        "checks": checks,
        "clean_tree": {
            "invalidated": clean["invalidated"],
            "hit_count": clean["hit_count"],
        },
        "planted_leak": {
            "invalidated": leaked["invalidated"],
            "hit_count": leaked["hit_count"],
            "hits": leaked["hits"],
            "redraws": leaked["redraws"],
            "clean_after_redraw": leaked["clean_after_redraw"],
            "idset_changed": leaked["idset_before"] != leaked["idset_after"],
        },
        "access_control": {
            "mode_octal": ac["mode_octal"],
            "owner": ac["owner"],
            "uid": ac["uid"],
            "who_could_have_seen": ac["who_could_have_seen"],
            "world_or_group_readable": ac["world_or_group_readable"],
            "ok": ac["ok"],
            "world_readable_control": world,
            "tune_denied": tune_denied,
            "train_denied": train_denied,
            "access_log_rows": len(log_rows),
            "actors": actors,
            "purposes": purposes,
        },
        "live_tree": live,
        "receipt_id_leak": receipt_clean,
        "idset_sha256": session.shadow_idset_sha256(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        failed = [k for k, v in checks.items() if not v]
        return fail(f"checks failed: {failed}")
    print(
        "SUCCESS:TST-0306-probe2 leak-audit redraws on planted prompt; "
        f"vault mode={ac['mode_octal']}; live_tree_hits={live['hit_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
