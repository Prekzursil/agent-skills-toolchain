"""Required controls for CNF-0162.

  * known-broken: a receipt naming a nonexistent path fails condition 2
    even if artifacts[].exists is true
  * known-broken: a 0-byte and a 1-byte artifact both fail the size floor
  * default-exercised mutation: raising DEFAULT_MIN_BYTES reddens a test
    that does not pass min_bytes explicitly
  * both-states: a healthy receipt set passes with no false positives
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

import verifier as V

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
HEALTHY_DIR = FIX / "healthy"
BROKEN_MISSING = FIX / "broken" / "missing-cited.json"
FIXTURE_SCHEMA_PATH = FIX / "receipt.schema.json"
FIXTURE_SCHEMA = json.loads(FIXTURE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _eval_fixture(path: Path) -> dict:
    return V.evaluate_receipt(
        path,
        schema_override=FIXTURE_SCHEMA,
        schema_path=FIXTURE_SCHEMA_PATH.relative_to(V.REPO).as_posix(),
    )


def known_broken_missing_path() -> dict:
    row = _eval_fixture(BROKEN_MISSING)
    cited = row.get("cited_artifacts") or []
    claimed_true = any(c.get("claimed_exists") is True for c in cited)
    missing = [c for c in cited if c.get("exists") is False]
    ok = (
        row["verdict"] == "FAIL"
        and row["conditions"]["2"]["pass"] is False
        and claimed_true
        and len(missing) >= 1
    )
    return {
        "id": "known-broken-missing-path",
        "pass": ok,
        "verdict": row["verdict"],
        "condition_2_pass": row["conditions"]["2"]["pass"],
        "claimed_exists_was_true": claimed_true,
        "claimed_exists_trusted": False,
        "missing_cited": [c["path"] for c in missing],
        "detail": row["conditions"]["2"]["detail"],
    }


def known_broken_size_floor() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf0162-size-") as tmp:
        root = Path(tmp)
        zero = root / "zero.bin"
        one = root / "one.bin"
        zero.write_bytes(b"")
        one.write_bytes(b"x")
        rz = _eval_fixture(zero)
        ro = _eval_fixture(one)
        ok = (
            rz["bytes"] == 0
            and ro["bytes"] == 1
            and rz["conditions"]["3"]["pass"] is False
            and ro["conditions"]["3"]["pass"] is False
            and rz["verdict"] == "FAIL"
            and ro["verdict"] == "FAIL"
        )
        return {
            "id": "known-broken-size-floor",
            "pass": ok,
            "zero_bytes": rz["bytes"],
            "one_bytes": ro["bytes"],
            "zero_c3": rz["conditions"]["3"]["pass"],
            "one_c3": ro["conditions"]["3"]["pass"],
            "floor": V.DEFAULT_MIN_BYTES,
        }


def both_states_healthy() -> dict:
    files = sorted(HEALTHY_DIR.glob("ok-*.json"))
    rows = [_eval_fixture(p) for p in files]
    false_pos = [r["path"] for r in rows if r["verdict"] != "PASS"]
    ok = len(rows) >= 2 and not false_pos
    return {
        "id": "both-states-healthy",
        "pass": ok,
        "n": len(rows),
        "false_positives": false_pos,
        "verdicts": [r["verdict"] for r in rows],
        "paths": [r["path"] for r in rows],
    }


def default_exercised_mutation() -> dict:
    """Mutate DEFAULT_MIN_BYTES; a no-arg check_size call must go red.

    An explicit min_bytes=old_floor call must stay green — that is the
    estate defect the mutation is meant to catch.
    """
    healthy = HEALTHY_DIR / "payload.json"
    ok_default, n = V.check_size(healthy)
    old = V.DEFAULT_MIN_BYTES
    V.DEFAULT_MIN_BYTES = n + 1
    try:
        ok_mutated, _ = V.check_size(healthy)
        ok_explicit, _ = V.check_size(healthy, min_bytes=old)
        row_mutated = _eval_fixture(HEALTHY_DIR / "ok-a.json")
        reddened = ok_default is True and ok_mutated is False and ok_explicit is True
        evaluate_red = row_mutated["conditions"]["3"]["pass"] is False
    finally:
        V.DEFAULT_MIN_BYTES = old
    restored_ok, _ = V.check_size(healthy)
    ast_live = evaluate_receipt_omits_min_bytes()
    ok = reddened and evaluate_red and restored_ok and ast_live and ok_default
    return {
        "id": "default-exercised-mutation",
        "pass": ok,
        "healthy_bytes": n,
        "old_floor": old,
        "mutated_floor": n + 1,
        "no_arg_went_red": ok_mutated is False,
        "explicit_old_floor_stayed_green": ok_explicit is True,
        "evaluate_receipt_went_red": evaluate_red,
        "evaluate_receipt_omits_min_bytes": ast_live,
        "restored": restored_ok,
    }


def evaluate_receipt_omits_min_bytes() -> bool:
    """AST-level proof that evaluate_receipt does not pass min_bytes."""
    src = (HERE / "verifier.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    saw = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "evaluate_receipt":
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            name = ast.unparse(call.func) if hasattr(ast, "unparse") else ""
            if isinstance(call.func, ast.Name):
                name = call.func.id
            elif isinstance(call.func, ast.Attribute):
                name = call.func.attr
            if name != "check_size":
                continue
            kws = {k.arg for k in call.keywords if k.arg}
            if "min_bytes" in kws or len(call.args) >= 2:
                return False
            saw = True
    return saw


def reviewer_plants_two() -> dict:
    """Independent reviewer: plant two broken receipts and confirm both fail."""
    with tempfile.TemporaryDirectory(prefix="cnf0162-reviewer-") as tmp:
        root = Path(tmp)
        missing_cited = root / "no-such.json"
        planted_missing = root / "planted-missing.json"
        planted_missing.write_text(
            json.dumps(
                {
                    "unit_id": "REV-0162-MISSING",
                    "state": "SUCCESS",
                    "sentinel": "SUCCESS:REV-0162-MISSING",
                    "artifacts": [
                        {
                            "path": str(missing_cited),
                            "exists": True,
                            "role": "phantom",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        tiny = root / "one-byte.json"
        tiny.write_bytes(b"{")
        r_missing = _eval_fixture(planted_missing)
        r_tiny = _eval_fixture(tiny)
        caught_missing = (
            r_missing["verdict"] == "FAIL"
            and r_missing["conditions"]["2"]["pass"] is False
        )
        caught_tiny = (
            r_tiny["verdict"] == "FAIL" and r_tiny["conditions"]["3"]["pass"] is False
        )
        ok = caught_missing and caught_tiny and r_tiny["bytes"] == 1
        return {
            "id": "reviewer-plants-two",
            "pass": ok,
            "caught_missing_path": caught_missing,
            "caught_one_byte": caught_tiny,
            "one_byte_size": r_tiny["bytes"],
            "reviewer_id": "CNF-0162-probe2-reviewer-plants-two",
        }


def run_all() -> dict:
    missing = known_broken_missing_path()
    size = known_broken_size_floor()
    healthy = both_states_healthy()
    mutation = default_exercised_mutation()
    reviewer = reviewer_plants_two()
    ok = all(x["pass"] for x in (missing, size, healthy, mutation, reviewer))
    return {
        "pass": ok,
        "known_broken_missing_path": missing,
        "known_broken_size_floor": size,
        "both_states_healthy": healthy,
        "default_exercised_mutation": mutation,
        "reviewer_plants_two": reviewer,
    }
