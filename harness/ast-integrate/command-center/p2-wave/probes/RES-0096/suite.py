"""Faithful replay of tools/command-center/tests/test_close.py without pytest.

pytest is not installed on this worktree. Assertions, item ids, NOW timestamp,
and close.main argv match the committed test file. Catalog load is the live
WORK-UNIT-CATALOG.json; work_units are dropped only at save time because the
close tests never read them and a 5.4 MiB pretty-print per test blows the
180s probe budget.
"""
from __future__ import annotations

import copy
import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Callable

import catalog as cat
import close
import validate as val

NOW = "2026-08-09T12:00:00+00:00"
_CACHED: dict[str, Any] | None = None


def _catalog() -> dict[str, Any]:
    global _CACHED
    if _CACHED is None:
        _CACHED = cat.load()
    data = copy.deepcopy(_CACHED)
    data.pop("work_units", None)
    data.pop("work_units_meta", None)
    return data


def workspace(tmp: Path) -> tuple[Path, Path, Path]:
    catalog = _catalog()
    catalog_file = tmp / "WORK-UNIT-CATALOG.json"
    graph_file = tmp / "DEPENDENCY-GRAPH.json"
    events_file = tmp / "events" / "EVENTS.jsonl"
    cat.save(catalog, catalog_file)
    cat.save(cat.build_graph(catalog), graph_file)
    return catalog_file, graph_file, events_file


def run_close(ws: tuple[Path, Path, Path], *argv: str) -> tuple[int, str]:
    catalog_file, graph_file, events_file = ws
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = close.main(
            [
                *argv,
                "--catalog",
                str(catalog_file),
                "--graph",
                str(graph_file),
                "--events",
                str(events_file),
                "--now",
                NOW,
            ]
        )
    return code, buf.getvalue()


def read_cat(ws: tuple[Path, Path, Path]) -> dict[str, Any]:
    return cat.load(ws[0])


def item_of(catalog: dict[str, Any], item_id: str) -> dict[str, Any]:
    return cat.by_id(catalog)[item_id]


def t_close_sets_a_terminal_disposition_with_evidence(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(
        ws,
        "R-M08",
        "--evidence",
        "renamed to monitor.retired-20260718; Test-Path old=False",
    )
    assert code == 0, out
    closed = item_of(read_cat(ws), "R-M08")
    assert closed["disposition"] == "DONE-VERIFIED"
    assert closed["section"] == "SETTLED"
    assert "monitor.retired" in closed["disposition_evidence"]
    assert closed["history"][-1]["action"] == "close"
    assert "SUCCESS:cc-close close R-M08" in out


def t_close_without_evidence_is_refused(tmp: Path) -> None:
    ws = workspace(tmp)
    c1, o1 = run_close(ws, "R-M08")
    c2, o2 = run_close(ws, "R-M08", "--evidence", "   ")
    assert c1 == 1 and c2 == 1, o1 + o2
    assert "FAILED:cc-close" in (o1 + o2)
    assert cat.is_open(item_of(read_cat(ws), "R-M08"))


def t_defer_keeps_the_item_open_and_never_deletes(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(
        ws, "R-M14", "--defer", "owner flagged highest-risk", "--days", "14"
    )
    assert code == 0, out
    deferred = item_of(read_cat(ws), "R-M14")
    assert cat.is_open(deferred)
    assert deferred["defer"]["reason"] == "owner flagged highest-risk"
    assert deferred["defer"]["until"].startswith("2026-08-23")


def t_supersede_requires_a_real_replacement(tmp: Path) -> None:
    ws = workspace(tmp)
    c1, o1 = run_close(ws, "R-M03", "--superseded-by", "R-NOPE")
    assert c1 == 1
    assert "unknown item" in o1
    c2, o2 = run_close(
        ws,
        "R-M03",
        "--superseded-by",
        "R-M01",
        "--evidence",
        "R-M01 subsumes the stanza work",
    )
    assert c2 == 0, o2
    assert item_of(read_cat(ws), "R-M03")["disposition"] == "SUPERSEDED"


def t_drop_records_the_owner_decision(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(
        ws,
        "R-M14",
        "--dropped",
        "owner decision GRILL-DECISIONS:22 additive only",
    )
    assert code == 0, out
    dropped = item_of(read_cat(ws), "R-M14")
    assert dropped["disposition"] == "DROPPED-BY-OWNER"
    assert "GRILL-DECISIONS" in dropped["disposition_evidence"]


def t_note_records_progress_without_closing(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(
        ws,
        "R-A02",
        "--note",
        "13-file ledger half landed",
        "--action",
        "residual = clean-room baseline",
    )
    assert code == 0, out
    noted = item_of(read_cat(ws), "R-A02")
    assert cat.is_open(noted)
    assert noted["history"][-1]["action"] == "note"
    assert noted["next_smallest_action"] == "residual = clean-room baseline"


def t_open_allocates_the_next_free_id_in_that_program(tmp: Path) -> None:
    ws = workspace(tmp)
    c1, o1 = run_close(
        ws,
        "--open",
        "wire the cockpit health probe",
        "--program",
        "MONITOR",
        "--action",
        "add probe",
    )
    assert c1 == 0, o1
    catalog = read_cat(ws)
    assert "R-M20" in cat.by_id(catalog)
    assert item_of(catalog, "R-M20")["program"] == "MONITOR"
    c2, o2 = run_close(
        ws,
        "--open",
        "second monitor item",
        "--program",
        "MONITOR",
        "--action",
        "x",
    )
    assert c2 == 0, o2
    assert "R-M21" in cat.by_id(read_cat(ws))


def t_open_without_a_program_is_refused(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(ws, "--open", "orphan")
    assert code == 1, out
    assert "needs --program" in out


def t_unknown_item_is_refused(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(ws, "R-ZZ99", "--evidence", "x")
    assert code == 1, out
    assert "no such item" in out


def t_no_verb_is_refused(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(ws)
    assert code == 1, out
    assert "nothing to do" in out


def t_every_mutation_regenerates_the_graph_and_logs_an_event(tmp: Path) -> None:
    ws = workspace(tmp)
    catalog_file, graph_file, events_file = ws
    code, out = run_close(
        ws, "R-M08", "--evidence", "done; ls shows monitor.retired-20260718"
    )
    assert code == 0, out
    catalog = cat.load(catalog_file)
    assert json.loads(graph_file.read_text(encoding="utf-8")) == cat.build_graph(
        catalog
    )
    events = [
        json.loads(line)
        for line in events_file.read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["verb"] == "close"
    assert events[-1]["id"] == "R-M08"


def t_the_event_log_is_append_only(tmp: Path) -> None:
    ws = workspace(tmp)
    _, _, events_file = ws
    run_close(ws, "R-M08", "--evidence", "a b")
    run_close(ws, "R-M09", "--evidence", "c d")
    lines = events_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["id"] for line in lines] == ["R-M08", "R-M09"]


def t_a_close_that_would_break_reachability_is_refused(tmp: Path) -> None:
    ws = workspace(tmp)
    code, out = run_close(ws, "R-M17", "--evidence", "GitHubActionsSource shipped")
    assert code == 1, out
    assert "REACH-1" in out and "still-open R-M13" in out
    assert cat.is_open(item_of(read_cat(ws), "R-M17"))


def t_a_preexisting_violation_elsewhere_does_not_block_an_unrelated_close(
    tmp: Path,
) -> None:
    ws = workspace(tmp)
    catalog_file, graph_file, _ = ws
    broken = cat.load(catalog_file)
    cat.by_id(broken)["R-A21"]["dependencies"] = ["R-GHOST"]
    cat.save(broken, catalog_file)
    cat.save(cat.build_graph(broken), graph_file)
    assert val.validate(cat.load(catalog_file))[0], (
        "precondition: the catalog is already dirty"
    )
    code, out = run_close(
        ws,
        "R-M08",
        "--evidence",
        "quarantined; ls shows monitor.retired-20260718",
    )
    assert code == 0, out
    assert item_of(read_cat(ws), "R-M08")["disposition"] == "DONE-VERIFIED"


def t_dry_run_writes_nothing(tmp: Path) -> None:
    ws = workspace(tmp)
    catalog_file, _, events_file = ws
    before = catalog_file.read_bytes()
    code, out = run_close(ws, "R-M08", "--evidence", "x y", "--dry-run")
    assert code == 0, out
    assert catalog_file.read_bytes() == before
    assert not events_file.exists()


def t_close_is_one_command_like_open(tmp: Path) -> None:
    ws = workspace(tmp)
    c1, o1 = run_close(
        ws,
        "--open",
        "a new thing",
        "--program",
        "HARNESS",
        "--action",
        "start it",
    )
    assert c1 == 0, o1
    new_id = sorted(i for i in cat.by_id(read_cat(ws)) if i.startswith("R-H"))[-1]
    c2, o2 = run_close(ws, new_id, "--evidence", "shipped at tools/x.py:1")
    assert c2 == 0, o2
    assert item_of(read_cat(ws), new_id)["disposition"] == "DONE-VERIFIED"


def t_list_filters_by_program_and_openness(tmp: Path) -> None:
    ws = workspace(tmp)
    c1, o1 = run_close(ws, "--list", "--program", "B-workflow_design", "--only-open")
    assert c1 == 0, o1
    assert "R-B08" in o1 and "R-A01" not in o1
    c2, o2 = run_close(ws, "--list")
    assert c2 == 0, o2
    assert "R-A01" in o2


def t_unreadable_catalog_fails_closed(tmp: Path) -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = close.main(["--list", "--catalog", str(tmp / "missing.json")])
    out = buf.getvalue()
    assert code == 1, out
    assert "FAILED:cc-close" in out


def t_next_id_rejects_an_unknown_program(tmp: Path) -> None:
    del tmp
    try:
        close.next_id(cat.load(), "NOT-A-PROGRAM")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def t_now_defaults_to_wall_clock_utc(tmp: Path) -> None:
    del tmp
    assert close._now().tzinfo is not None
    assert close._now(NOW).isoformat() == NOW


def t_closing_every_open_item_leaves_a_valid_catalog(tmp: Path) -> None:
    ws = workspace(tmp)
    catalog = read_cat(ws)
    order, residual = cat.topological_order(catalog)
    assert residual == []
    for item_id in order:
        entry = cat.by_id(catalog)[item_id]
        if cat.is_open(entry):
            entry["disposition"] = "DONE-VERIFIED"
            entry["status"] = "DONE-VERIFIED"
            entry["section"] = "SETTLED"
            entry["disposition_evidence"] = f"simulated close of {item_id}"
    violations, stats = val.validate(catalog, graph=cat.build_graph(catalog))
    assert violations == [], [str(entry) for entry in violations]
    assert stats["open"] == 0


TESTS: list[tuple[str, Callable[[Path], None]]] = [
    ("test_close_sets_a_terminal_disposition_with_evidence", t_close_sets_a_terminal_disposition_with_evidence),
    ("test_close_without_evidence_is_refused", t_close_without_evidence_is_refused),
    ("test_defer_keeps_the_item_open_and_never_deletes", t_defer_keeps_the_item_open_and_never_deletes),
    ("test_supersede_requires_a_real_replacement", t_supersede_requires_a_real_replacement),
    ("test_drop_records_the_owner_decision", t_drop_records_the_owner_decision),
    ("test_note_records_progress_without_closing", t_note_records_progress_without_closing),
    ("test_open_allocates_the_next_free_id_in_that_program", t_open_allocates_the_next_free_id_in_that_program),
    ("test_open_without_a_program_is_refused", t_open_without_a_program_is_refused),
    ("test_unknown_item_is_refused", t_unknown_item_is_refused),
    ("test_no_verb_is_refused", t_no_verb_is_refused),
    ("test_every_mutation_regenerates_the_graph_and_logs_an_event", t_every_mutation_regenerates_the_graph_and_logs_an_event),
    ("test_the_event_log_is_append_only", t_the_event_log_is_append_only),
    ("test_a_close_that_would_break_reachability_is_refused", t_a_close_that_would_break_reachability_is_refused),
    ("test_a_preexisting_violation_elsewhere_does_not_block_an_unrelated_close", t_a_preexisting_violation_elsewhere_does_not_block_an_unrelated_close),
    ("test_dry_run_writes_nothing", t_dry_run_writes_nothing),
    ("test_close_is_one_command_like_open", t_close_is_one_command_like_open),
    ("test_list_filters_by_program_and_openness", t_list_filters_by_program_and_openness),
    ("test_unreadable_catalog_fails_closed", t_unreadable_catalog_fails_closed),
    ("test_next_id_rejects_an_unknown_program", t_next_id_rejects_an_unknown_program),
    ("test_now_defaults_to_wall_clock_utc", t_now_defaults_to_wall_clock_utc),
    ("test_closing_every_open_item_leaves_a_valid_catalog", t_closing_every_open_item_leaves_a_valid_catalog),
]


def run_all(tmp_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for name, fn in TESTS:
        case_dir = tmp_root / name
        case_dir.mkdir(parents=True, exist_ok=True)
        try:
            fn(case_dir)
            rows.append({"name": name, "ok": True, "error": ""})
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - record any assertion/runtime miss
            err = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc(limit=4)
            rows.append({"name": name, "ok": False, "error": err, "traceback": tb[-1200:]})
            print(f"FAIL {name} {err}")
    passed = sum(1 for r in rows if r["ok"])
    failed = [r["name"] for r in rows if not r["ok"]]
    doc = {
        "suite": "tools/command-center/tests/test_close.py",
        "replay": "in-process-without-pytest",
        "n": len(rows),
        "passed": passed,
        "failed": failed,
        "ok": not failed,
        "tests": rows,
        "close_file": getattr(close, "__file__", ""),
        "validate_file": getattr(val, "__file__", ""),
    }
    print(json.dumps({"ok": doc["ok"], "passed": passed, "n": doc["n"], "failed": failed}))
    return doc


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="res0096-suite-") as tmp:
        doc = run_all(Path(tmp))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
