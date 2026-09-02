"""Structural checks for command-center/receipts/TST-0111.json."""
from __future__ import annotations

from typing import Any

SENTINEL = "SUCCESS:TST-0111"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def check_artifact(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    if str(doc.get("unit_id") or "") != "TST-0111":
        return False, "unit_id"
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return False, f"self-declared:{doc.get('state')}"
    if str(doc.get("state") or "") != "SUCCESS":
        return False, "state-not-SUCCESS"
    text_fields = " ".join(
        str(doc.get(k) or "") for k in ("sentinel", "answer", "title", "question")
    )
    if SENTINEL not in text_fields and SENTINEL not in str(doc.get("sentinel") or ""):
        return False, "sentinel"
    if SENTINEL not in str(doc.get("sentinel") or ""):
        return False, "sentinel-field"
    table = doc.get("execution_table")
    if not isinstance(table, list):
        return False, "execution_table"
    summary = doc.get("summary") or {}
    if not isinstance(summary, dict):
        return False, "summary"
    if summary.get("computed_not_asserted") is not True:
        return False, "computed_not_asserted"
    if "extracted" not in summary or int(summary["extracted"]) != len(table):
        return False, "extracted-ne-table"
    broken = sum(
        1 for r in table if str((r or {}).get("classification") or "").startswith("broken")
    )
    if "broken" not in summary or int(summary["broken"]) != broken:
        return False, "broken-mismatch"
    allow = doc.get("allowlist")
    if not isinstance(allow, list) or "echo" not in allow or "false" not in allow:
        return False, "allowlist"
    tests = doc.get("tests") or []
    if not isinstance(tests, list) or len(tests) < 2:
        return False, "tests"
    ids = {str(t.get("id")) for t in tests if isinstance(t, dict)}
    if "test_every_fenced_command_is_executed_or_explicitly_marked" not in ids:
        return False, "missing-coverage-test"
    if "test_extractor_finds_a_planted_command" not in ids:
        return False, "missing-planted-test"
    if any(str(t.get("result")) != "PASS" for t in tests if isinstance(t, dict)):
        return False, "test-not-pass"
    controls = doc.get("controls") or {}
    if controls.get("planted", {}).get("found_plant") is not True:
        return False, "plant-not-found"
    if controls.get("planted", {}).get("naive_unlabeled_found_plant") is not False:
        return False, "naive-extractor-not-blind"
    if controls.get("good_coverage") is not True:
        return False, "good-fixture-coverage"
    if controls.get("bad_coverage") is not False:
        return False, "unmarked-exclusion-not-caught"
    if controls.get("sudo_not_executed") is not True:
        return False, "sudo-was-executed"
    corpus = doc.get("corpus") or {}
    if corpus.get("computed_not_asserted") is not True:
        return False, "corpus-not-computed"
    files = corpus.get("files")
    if not isinstance(files, list) or len(files) < 1:
        return False, "live-corpus-empty"
    if summary.get("runner_complete") is not True:
        return False, "runner-incomplete"
    evid = doc.get("evidence") or []
    if not isinstance(evid, list) or len(evid) < 2:
        return False, "evidence"
    return True, "ok"
