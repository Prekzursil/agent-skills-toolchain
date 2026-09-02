"""Tests for hub.ledger: daily JSONL files, the no-prompt-text guard, cost sums."""

from __future__ import annotations

import json
import re
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub import ledger as ledger_mod  # noqa: E402
from hub.ledger import Ledger, prompt_digest, resolve_ledger_root  # noqa: E402
from tests import conftest_hub as helpers  # noqa: E402

ledger = helpers.ledger

DAY_SECONDS = 86400.0
T0 = 1_788_400_000.0  # 2026-09-03T01:46:40Z


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "endpoint": "hf-router",
        "model": "glm-5.3",
        "remote_id": "zai-org/GLM-5.3:zai-org",
        "caller": "codex",
        "prompt_sha256_16": "0" * 16,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "latency_ms": 120,
        "status": "ok",
        "error_class": None,
        "cost_usd": 0.5,
        "cost_basis": "table_estimate",
        "tags": ["hosted"],
    }
    base.update(overrides)
    return base


def test_prompt_digest_is_canonical_sha256_prefix() -> None:
    one = prompt_digest([{"role": "user", "content": "hi"}])
    same = prompt_digest([{"content": "hi", "role": "user"}])
    other = prompt_digest([{"role": "user", "content": "hi!"}])
    assert re.fullmatch(r"[0-9a-f]{16}", one)
    assert one == same
    assert one != other
    assert Ledger.prompt_digest([]) == prompt_digest([])


def test_resolve_ledger_root_precedence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    policy = {"hub": {"ledgerPath": "custom/ledger"}}
    absolute = tmp_path / "abs-ledger"
    env_abs = {ledger_mod.LEDGER_ENV: str(absolute)}
    assert resolve_ledger_root(policy, env_abs, repo) == absolute
    env_rel = {ledger_mod.LEDGER_ENV: "rel/ledger"}
    assert resolve_ledger_root(policy, env_rel, repo) == repo / "rel" / "ledger"
    assert resolve_ledger_root(policy, {}, repo) == repo / "custom" / "ledger"
    assert resolve_ledger_root({"hub": {}}, {}, repo) == repo / "state" / (
        "inference-ledger"
    )
    assert resolve_ledger_root({}, {}, repo) == repo / "state" / "inference-ledger"
    assert resolve_ledger_root(None, {}, repo) == repo / "state" / "inference-ledger"
    assert resolve_ledger_root(policy, {ledger_mod.LEDGER_ENV: ""}, repo) == (
        repo / "custom" / "ledger"
    )


def test_ledger_root_resolution_in_constructor(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    from_env = Ledger(environ={ledger_mod.LEDGER_ENV: str(tmp_path / "e")})
    assert from_env.root == tmp_path / "e"
    from_policy = Ledger(
        policy={"hub": {"ledgerPath": "p"}}, environ={}, repo_root=repo
    )
    assert from_policy.root == repo / "p"
    from_default = Ledger(environ={})
    assert from_default.root == helpers.REPO_ROOT / "state" / "inference-ledger"
    assert Ledger(str(tmp_path / "s")).root == tmp_path / "s"


def test_ledger_constructor_fails_without_repo_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ledger_mod, "find_repo_root", lambda: None)
    with pytest.raises(ValueError, match="no repo root"):
        Ledger(environ={})


def test_two_records_same_day_share_one_file(tmp_path: Path) -> None:
    clock = FakeClock(T0)
    book = Ledger(tmp_path / "ledger", clock=clock)
    first = book.record(entry())
    clock.now += 3600
    second = book.record(entry(cost_usd=None, cost_basis="quota", tags=[]))
    files = sorted(p.name for p in book.root.iterdir())
    assert files == ["2026-09-03.jsonl"]
    lines = (book.root / files[0]).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert [row["ledger_id"] for row in rows] == [first, second]
    assert first != second
    assert re.fullmatch(r"[0-9a-f]{16}", first)
    assert rows[0]["ts"] == "2026-09-03T01:46:40.000Z"
    assert rows[1]["ts"] == "2026-09-03T02:46:40.000Z"
    assert tuple(rows[0]) == ledger_mod.LEDGER_FIELDS
    assert rows[1]["cost_usd"] is None
    assert rows[1]["tags"] == []


def test_record_fills_missing_fields_and_keeps_given_id(tmp_path: Path) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    ledger_id = book.record({"endpoint": "ollama", "ledger_id": "given-id-0001"})
    assert ledger_id == "given-id-0001"
    (row,) = book.today_entries()
    assert row["endpoint"] == "ollama"
    assert row["model"] is None
    assert row["tags"] == []
    assert row["ts"].endswith("Z")
    given_ts = "2026-09-03T00:00:00.000Z"
    book.record({"endpoint": "ollama", "ts": given_ts})
    assert book.today_entries()[1]["ts"] == given_ts


def test_day_rollover_creates_new_file(tmp_path: Path) -> None:
    clock = FakeClock(T0)
    book = Ledger(tmp_path / "ledger", clock=clock)
    book.record(entry())
    clock.now += DAY_SECONDS
    book.record(entry(cost_usd=0.25))
    files = sorted(p.name for p in book.root.iterdir())
    assert files == ["2026-09-03.jsonl", "2026-09-04.jsonl"]
    assert book.day_file().name == "2026-09-04.jsonl"
    assert book.day_file(T0).name == "2026-09-03.jsonl"
    assert [row["cost_usd"] for row in book.today_entries()] == [0.25]
    assert book.sum_cost_today() == 0.25


@pytest.mark.parametrize(
    "bad",
    [
        {"content": "prompt text"},
        {"text": "prompt text"},
        {"messages": []},
        {"tags": [{"content": "nested prompt"}]},
        {"caller": "x" * 257},
        {"tags": ["y" * 300]},
        {"unexpected": 1},
        {"cost_usd": "1.0"},
        {"cost_usd": True},
        {"tags": "not-a-list"},
    ],
)
def test_guard_rejects_prompt_text_and_malformed_entries(
    tmp_path: Path, bad: dict[str, Any]
) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    with pytest.raises(ValueError):
        book.record(entry(**bad))
    assert not book.root.exists() or not any(book.root.iterdir())


def test_guard_accepts_boundary_string_and_null_cost(tmp_path: Path) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    book.record(entry(caller="x" * 256, cost_usd=None))
    book.record(entry(cost_usd=2))
    assert book.sum_cost_today() == 2.0


def test_today_entries_filters_and_skips_corrupt_lines(tmp_path: Path) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    assert book.today_entries() == []
    book.record(entry(endpoint="hf-router", cost_usd=0.1))
    book.record(entry(endpoint="ollama", cost_usd=0.0, cost_basis="local_zero"))
    with book.day_file().open("a", encoding="utf-8") as handle:
        handle.write("{not json}\n")
        handle.write("\n")
        handle.write(json.dumps(["a", "list"]) + "\n")
    assert len(book.today_entries()) == 2
    assert [row["endpoint"] for row in book.today_entries("ollama")] == ["ollama"]
    assert book.today_entries("missing") == []


def test_sum_cost_today_none_when_every_row_is_null(tmp_path: Path) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    assert book.sum_cost_today() is None
    book.record(entry(endpoint="cursor-auth2api", cost_usd=None, cost_basis="quota"))
    assert book.sum_cost_today() is None
    assert book.sum_cost_today("cursor-auth2api") is None
    book.record(entry(endpoint="hf-router", cost_usd=0.75))
    book.record(entry(endpoint="hf-router", cost_usd=1.0))
    book.record(entry(endpoint="openrouter", cost_usd=0.5))
    assert book.sum_cost_today("hf-router") == 1.75
    assert book.sum_cost_today("cursor-auth2api") is None
    assert book.sum_cost_today() == 2.25


def test_concurrent_records_are_whole_lines(tmp_path: Path) -> None:
    book = Ledger(tmp_path / "ledger", clock=FakeClock(T0))
    ids: list[str] = []
    lock = threading.Lock()

    def worker(n: int) -> None:
        for i in range(5):
            ledger_id = book.record(entry(caller=f"t{n}-{i}"))
            with lock:
                ids.append(ledger_id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    lines = book.day_file().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 100
    assert len(set(ids)) == 100
    assert {json.loads(line)["ledger_id"] for line in lines} == set(ids)
