"""Run extraction + allowlist sandbox over a document set."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from corpus import list_corpus
from extract import extract_file, extract_text, naive_unlabeled_only
from sandbox import ALLOWLIST, execute, other_shell_probe

HERE = Path(__file__).resolve().parent
PLANTED = "echo TST-0111-PLANTED-FENCE"


def classify_row(row: dict[str, Any], result: dict[str, Any]) -> str:
    if result.get("outcome") == "marked-not-executable":
        return "excluded-marked"
    if result.get("outcome") == "unmarked-not-executed":
        return "broken-unmarked-exclusion"
    if result.get("outcome") == "empty-fence":
        return "broken-empty-fence"
    if result.get("executed") and result.get("exit_code") == 0:
        return "ok"
    if result.get("executed"):
        return "broken-nonzero-exit"
    return "broken-unclassified"


def run_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for row in rows:
        result = execute(
            str(row.get("command") or ""),
            marked_not_executable=bool(row.get("marked_not_executable")),
        )
        entry = {
            **row,
            **result,
            "classification": classify_row(row, result),
        }
        table.append(entry)
    return table


def coverage_ok(table: list[dict[str, Any]]) -> bool:
    """Every extracted command was executed or carried an explicit marker."""
    if not table:
        return True
    for row in table:
        executed = bool(row.get("executed"))
        marked = bool(row.get("marked_not_executable"))
        if not executed and not marked:
            return False
    return True


def runner_complete(table: list[dict[str, Any]]) -> bool:
    """Every extracted command has an outcome. Silent skip is a detector failure."""
    allowed_unexecuted = {"unmarked-not-executed", "empty-fence", "marked-not-executable"}
    for row in table:
        if not row.get("classification"):
            return False
        outcome = str(row.get("outcome") or "")
        executed = bool(row.get("executed"))
        marked = bool(row.get("marked_not_executable"))
        if executed:
            if outcome != "executed":
                return False
            continue
        if marked:
            if outcome != "marked-not-executable":
                return False
            continue
        if outcome not in allowed_unexecuted:
            return False
    return True


def summarize(table: list[dict[str, Any]]) -> dict[str, Any]:
    extracted = len(table)
    executed = sum(1 for r in table if r.get("executed"))
    marked = sum(1 for r in table if r.get("marked_not_executable"))
    unmarked_excl = sum(
        1 for r in table if r.get("classification") == "broken-unmarked-exclusion"
    )
    broken = sum(1 for r in table if str(r.get("classification") or "").startswith("broken"))
    ok = sum(1 for r in table if r.get("classification") == "ok")
    return {
        "extracted": extracted,
        "executed": executed,
        "marked_not_executable": marked,
        "unmarked_exclusions": unmarked_excl,
        "ok": ok,
        "broken": broken,
        "coverage_ok": coverage_ok(table),
        "runner_complete": runner_complete(table),
        "computed_not_asserted": True,
    }


def run_path(path: Path, rel: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = extract_file(path, rel)
    table = run_rows(rows)
    return table, summarize(table)


def run_live(repo: Path) -> dict[str, Any]:
    corp = list_corpus(repo)
    table: list[dict[str, Any]] = []
    for rel in corp["files"]:
        path = repo / rel
        rows = extract_file(path, rel)
        table.extend(run_rows(rows))
    return {
        "corpus": corp,
        "table": table,
        "summary": summarize(table),
        "allowlist": sorted(ALLOWLIST),
        "other_shell": other_shell_probe(),
    }


def fixture(name: str) -> Path:
    return HERE / "fixtures" / name


def run_controls() -> dict[str, Any]:
    good_table, good_sum = run_path(
        fixture("coverage-good.md"),
        "command-center/p2-wave/probes/TST-0111/fixtures/coverage-good.md",
    )
    bad_table, bad_sum = run_path(
        fixture("coverage-unmarked-exclusion.md"),
        "command-center/p2-wave/probes/TST-0111/fixtures/coverage-unmarked-exclusion.md",
    )
    planted_path = fixture("planted.md")
    planted_rel = "command-center/p2-wave/probes/TST-0111/fixtures/planted.md"
    planted_text = planted_path.read_text(encoding="utf-8")
    planted_rows = extract_text(planted_text, planted_rel)
    planted_cmds = [r["command"] for r in planted_rows]
    naive = naive_unlabeled_only(planted_text, planted_rel)
    empty_rows = extract_file(
        fixture("empty.md"),
        "command-center/p2-wave/probes/TST-0111/fixtures/empty.md",
    )
    unlabeled_table_rows = extract_file(
        fixture("unlabeled-table.md"),
        "command-center/p2-wave/probes/TST-0111/fixtures/unlabeled-table.md",
    )
    python_mention = any(
        "print" in str(r.get("command") or "") and "PLANTED" in str(r.get("command") or "")
        for r in planted_rows
    )
    sudo_row = next(
        (r for r in good_table if "sudo" in str(r.get("command") or "")),
        None,
    )
    false_row = next(
        (r for r in good_table if str(r.get("command") or "") == "false"),
        None,
    )
    echo_row = next(
        (r for r in good_table if "TST-0111-OK" in str(r.get("command") or "")),
        None,
    )
    return {
        "good": {"table": good_table, "summary": good_sum},
        "unmarked_exclusion": {"table": bad_table, "summary": bad_sum},
        "planted": {
            "commands": planted_cmds,
            "found_plant": PLANTED in planted_cmds,
            "naive_unlabeled_found_plant": any(
                r.get("command") == PLANTED for r in naive
            ),
            "python_print_extracted_as_command": python_mention,
            "empty_doc_count": len(empty_rows),
            "unlabeled_table_count": len(unlabeled_table_rows),
            "row_count": len(planted_rows),
        },
        "sudo_not_executed": bool(
            sudo_row
            and sudo_row.get("executed") is False
            and sudo_row.get("marked_not_executable") is True
        ),
        "false_executed_nonzero": bool(
            false_row
            and false_row.get("executed") is True
            and false_row.get("exit_code") not in (0, None)
        ),
        "echo_ok": bool(
            echo_row and echo_row.get("executed") is True and echo_row.get("exit_code") == 0
        ),
        "good_coverage": bool(good_sum.get("coverage_ok")),
        "bad_coverage": bool(bad_sum.get("coverage_ok")),
    }
