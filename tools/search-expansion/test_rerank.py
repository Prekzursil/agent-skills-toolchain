"""Tests for rerank + eval_rerank — written BEFORE the implementation (TDD red first).

Coverage contract: 100% line + branch for rerank.py (the package's gate); eval_rerank.py is
held to the same bar here so the parent can add it to the gate line without new work.

Nothing here needs onnxruntime, tokenizers, numpy, fastembed or flashrank installed: every
optional backend is FAKED by injecting modules into ``sys.modules`` (a ``None`` entry makes
``import x`` raise ``ModuleNotFoundError``, which is exactly what an absent package does).
The one thing the fakes never do is read the "model" files — they are zero-byte markers
whose only job is to exist where the loader looks.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from types import MappingProxyType, ModuleType, SimpleNamespace
from typing import Any, Iterable, Iterator

import pytest

import eval_rerank
import rerank
from eval_rerank import (
    BM25,
    Candidate,
    EvalQuery,
    build_beir_jsonl,
    candidates_to_fused,
    evaluate,
    load_beir,
    load_eval_set,
    ndcg_at_k,
    recall_at_k,
    summarize_markdown,
)
from rank_fusion import FusedResult, reciprocal_rank_fusion
from rerank import (
    BACKENDS,
    BATCH_SIZE,
    DEFAULT_MODEL,
    DEFAULT_TOP_K,
    ENV_ALLOW_DOWNLOAD,
    ENV_ENABLED,
    ENV_MODEL_DIR,
    MAX_TOKENS,
    BackendUnavailable,
    LoadedBackend,
    RerankResult,
    load_backend,
    rerank as run_rerank,
    reset_backend_cache,
    scoring_text,
)

OPTIONAL_MODULES = (
    "onnxruntime",
    "tokenizers",
    "numpy",
    "fastembed",
    "fastembed.rerank",
    "fastembed.rerank.cross_encoder",
    "flashrank",
)


# --------------------------------------------------------------------------
# fakes
# --------------------------------------------------------------------------


class FakeEncoding:
    def __init__(self, token_id: int) -> None:
        self.ids = [token_id]
        self.attention_mask = [1]
        self.type_ids = [0]


class FakeOnnxWorld:
    """One coherent fake of onnxruntime + tokenizers + numpy.

    The tokenizer registers each passage under an integer token id; the session looks the
    passage back up and returns ``scores[passage]`` (default 0.0) as the logit. Everything
    the loader does is recorded so tests can assert on it.
    """

    def __init__(
        self,
        scores: dict[str, float] | None = None,
        input_names: tuple[str, ...] = (
            "input_ids",
            "attention_mask",
            "token_type_ids",
        ),
    ) -> None:
        self.scores = dict(scores or {})
        self.input_names = input_names
        self.texts: dict[int, str] = {}
        self.sessions: list[Any] = []
        self.tokenizers: list[Any] = []
        self.run_feeds: list[dict[str, Any]] = []

    def modules(self) -> dict[str, ModuleType]:
        world = self

        class FakeTokenizer:
            def __init__(self, path: str) -> None:
                self.path = path
                self.truncation: int | None = None
                self.padding = False
                self.batches: list[list[tuple[str, str]]] = []

            @classmethod
            def from_file(cls, path: str) -> FakeTokenizer:
                tok = cls(path)
                world.tokenizers.append(tok)
                return tok

            def enable_truncation(self, max_length: int) -> None:
                self.truncation = max_length

            def enable_padding(self) -> None:
                self.padding = True

            def encode_batch(self, pairs: list[tuple[str, str]]) -> list[FakeEncoding]:
                pairs = list(pairs)
                self.batches.append(pairs)
                out = []
                for _query, text in pairs:
                    token_id = len(world.texts) + 1
                    world.texts[token_id] = text
                    out.append(FakeEncoding(token_id))
                return out

        class FakeSession:
            def __init__(self, path: str, providers: list[str]) -> None:
                self.path = path
                self.providers = providers
                world.sessions.append(self)

            def get_inputs(self) -> list[Any]:
                return [SimpleNamespace(name=n) for n in world.input_names]

            def run(self, outputs: None, feeds: dict[str, Any]) -> list[Any]:
                assert outputs is None
                world.run_feeds.append(feeds)
                rows = feeds["input_ids"]
                return [[[world.scores.get(world.texts[row[0]], 0.0)] for row in rows]]

        ort = ModuleType("onnxruntime")
        ort.InferenceSession = FakeSession  # type: ignore[attr-defined]
        tokenizers = ModuleType("tokenizers")
        tokenizers.Tokenizer = FakeTokenizer  # type: ignore[attr-defined]
        numpy = ModuleType("numpy")
        numpy.int64 = "int64"  # type: ignore[attr-defined]
        numpy.array = lambda rows, dtype=None: rows  # type: ignore[attr-defined]
        return {"onnxruntime": ort, "tokenizers": tokenizers, "numpy": numpy}


class FakeFastembedWorld:
    def __init__(
        self, scores: dict[str, float] | None = None, *, fail: str = ""
    ) -> None:
        self.scores = dict(scores or {})
        self.fail = fail
        self.encoders: list[Any] = []

    def modules(self) -> dict[str, ModuleType]:
        world = self

        class TextCrossEncoder:
            def __init__(
                self, model_name: str, cache_dir: str, local_files_only: bool
            ) -> None:
                if world.fail:
                    raise ValueError(world.fail)
                self.model_name = model_name
                self.cache_dir = cache_dir
                self.local_files_only = local_files_only
                world.encoders.append(self)

            def rerank(self, query: str, documents: list[str]) -> Iterator[float]:
                # A generator on purpose: the caller must materialise it.
                for doc in documents:
                    yield world.scores.get(doc, 0.0)

        pkg = ModuleType("fastembed")
        sub = ModuleType("fastembed.rerank")
        mod = ModuleType("fastembed.rerank.cross_encoder")
        mod.TextCrossEncoder = TextCrossEncoder  # type: ignore[attr-defined]
        return {
            "fastembed": pkg,
            "fastembed.rerank": sub,
            "fastembed.rerank.cross_encoder": mod,
        }


class FakeFlashrankWorld:
    def __init__(
        self, scores: dict[str, float] | None = None, *, fail: str = ""
    ) -> None:
        self.scores = dict(scores or {})
        self.fail = fail
        self.rankers: list[Any] = []

    def modules(self) -> dict[str, ModuleType]:
        world = self

        class RerankRequest:
            def __init__(self, query: str, passages: list[dict[str, Any]]) -> None:
                self.query = query
                self.passages = passages

        class Ranker:
            def __init__(self, model_name: str, cache_dir: str) -> None:
                if world.fail:
                    raise RuntimeError(world.fail)
                self.model_name = model_name
                self.cache_dir = cache_dir
                world.rankers.append(self)

            def rerank(self, request: RerankRequest) -> list[dict[str, Any]]:
                scored = [
                    {**p, "score": world.scores.get(p["text"], 0.0)}
                    for p in request.passages
                ]
                # flashrank returns passages sorted by score, best first.
                return sorted(scored, key=lambda p: -p["score"])

        mod = ModuleType("flashrank")
        mod.Ranker = Ranker  # type: ignore[attr-defined]
        mod.RerankRequest = RerankRequest  # type: ignore[attr-defined]
        return {"flashrank": mod}


def install(monkeypatch: pytest.MonkeyPatch, modules: dict[str, ModuleType]) -> None:
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def make_model_files(
    model_dir: Path, layout: str = "onnx/model_quantized.onnx"
) -> Path:
    root = model_dir.joinpath(*DEFAULT_MODEL.split("/"))
    target = root.joinpath(*layout.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"")
    (root / "tokenizer.json").write_text("{}", encoding="utf-8")
    return root


def fused(*items: tuple[str, str, str]) -> list[FusedResult]:
    """``(url, title, snippet)`` triples -> descending-RRF FusedResults, like a real fusion."""
    return [
        FusedResult(
            url=url,
            display_url=url,
            title=title,
            score=1.0 / (60 + i),
            sources=("searxng",),
            ranks=MappingProxyType({"searxng": i}),
            snippet=snippet,
        )
        for i, (url, title, snippet) in enumerate(items, start=1)
    ]


FOUR = fused(
    ("https://a.example/1", "Alpha", "first passage"),
    ("https://b.example/2", "Beta", "second passage"),
    ("https://c.example/3", "Gamma", "third passage"),
    ("https://d.example/4", "Delta", "fourth passage"),
)


@pytest.fixture(autouse=True)
def clean_slate(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    for name in (ENV_ENABLED, ENV_MODEL_DIR, ENV_ALLOW_DOWNLOAD):
        monkeypatch.delenv(name, raising=False)
    for name in OPTIONAL_MODULES:
        monkeypatch.setitem(sys.modules, name, None)
    reset_backend_cache()
    yield
    reset_backend_cache()


@pytest.fixture
def onnx_world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> FakeOnnxWorld:
    world = FakeOnnxWorld(
        {
            "Alpha first passage": 0.1,
            "Beta second passage": 0.9,
            "Gamma third passage": 0.5,
            "Delta fourth passage": 0.7,
        }
    )
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    monkeypatch.setenv(ENV_MODEL_DIR, str(tmp_path))
    return world


# --------------------------------------------------------------------------
# constants + small helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module", [rerank, eval_rerank])
def test_public_names_all_resolve(module: ModuleType) -> None:
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert missing == []
    assert len(set(module.__all__)) == len(module.__all__)  # no duplicates


def test_constants_match_the_plan() -> None:
    assert DEFAULT_MODEL == "Xenova/ms-marco-MiniLM-L-6-v2"
    assert DEFAULT_TOP_K == 30
    assert MAX_TOKENS == 512
    assert BACKENDS == ("auto", "onnx", "fastembed", "flashrank", "none")
    assert (ENV_ENABLED, ENV_MODEL_DIR, ENV_ALLOW_DOWNLOAD) == (
        "RERANK_ENABLED",
        "RERANK_MODEL_DIR",
        "RERANK_ALLOW_DOWNLOAD",
    )
    assert BATCH_SIZE >= 1


@pytest.mark.parametrize(
    ("title", "snippet", "expected"),
    [
        ("Alpha", "first passage", "Alpha first passage"),
        ("Alpha", "", "Alpha"),
        ("", "first passage", "first passage"),
        ("", "", ""),
        ("  spaced\ttitle ", "  many   gaps\n here ", "spaced title many gaps here"),
    ],
)
def test_scoring_text_is_title_space_snippet_collapsed(
    title: str, snippet: str, expected: str
) -> None:
    assert scoring_text(fused(("https://x", title, snippet))[0]) == expected


def test_rerank_result_is_frozen_and_pairs_zip_results_with_scores() -> None:
    result = RerankResult(
        results=tuple(FOUR[:2]),
        scores=(0.9, None),
        reranked=True,
        backend="onnx",
        model=DEFAULT_MODEL,
        latency_ms=1.0,
        reason="",
        top_k=30,
        rescored=1,
        skipped=1,
    )
    assert result.pairs() == ((FOUR[0], 0.9), (FOUR[1], None))
    with pytest.raises(AttributeError):
        result.reranked = False  # type: ignore[misc]


def test_loaded_backend_is_frozen() -> None:
    loaded = LoadedBackend(name="onnx", model=DEFAULT_MODEL, score=lambda q, t: [])
    with pytest.raises(AttributeError):
        loaded.name = "x"  # type: ignore[misc]


# --------------------------------------------------------------------------
# rerank(): validation + the identity paths (each with a truthful reason)
# --------------------------------------------------------------------------


def test_top_k_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="top_k"):
        run_rerank(FOUR, "q", top_k=0, enabled=True)


def test_unknown_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="backend"):
        run_rerank(FOUR, "q", backend="gpu", enabled=True)  # type: ignore[arg-type]


def assert_identity(result: RerankResult, source: list[FusedResult]) -> None:
    assert result.reranked is False
    assert result.results == tuple(source)
    assert result.scores == (None,) * len(source)
    assert result.reason  # never silent
    assert result.rescored == 0 and result.skipped == 0
    assert result.latency_ms >= 0.0


def test_default_is_off_env_unset_gives_identity_with_reason() -> None:
    result = run_rerank(FOUR, "q")
    assert_identity(result, FOUR)
    assert ENV_ENABLED in result.reason
    assert result.backend == "none"
    assert result.model == DEFAULT_MODEL
    assert result.top_k == DEFAULT_TOP_K


@pytest.mark.parametrize("value", ["1", "true", "YES", " On "])
def test_env_truthy_spellings_enable_the_stage(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(ENV_ENABLED, value)
    result = run_rerank(FOUR, "q")
    # Enabled, but nothing is installed: the reason must name the missing backends, not the
    # env var, which proves the gate was passed.
    assert result.reranked is False
    assert ENV_ENABLED not in result.reason
    assert "no rerank backend available" in result.reason


@pytest.mark.parametrize("value", ["0", "false", "off", "", "maybe"])
def test_env_other_spellings_keep_it_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(ENV_ENABLED, value)
    result = run_rerank(FOUR, "q")
    assert_identity(result, FOUR)
    assert ENV_ENABLED in result.reason


def test_explicit_enabled_false_beats_env_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ENABLED, "1")
    result = run_rerank(FOUR, "q", enabled=False)
    assert_identity(result, FOUR)
    assert "disabled" in result.reason


def test_backend_none_is_an_explicit_identity() -> None:
    result = run_rerank(FOUR, "q", backend="none", enabled=True)
    assert_identity(result, FOUR)
    assert "none" in result.reason
    assert result.backend == "none"


def test_empty_input_is_identity_without_touching_a_backend(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank([], "q", enabled=True)
    assert_identity(result, [])
    assert "empty" in result.reason
    assert onnx_world.sessions == []


def test_blank_query_is_identity_without_touching_a_backend(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank(FOUR, "   ", enabled=True)
    assert_identity(result, FOUR)
    assert "query" in result.reason
    assert onnx_world.sessions == []


def test_no_backend_installed_lists_every_candidate_reason() -> None:
    result = run_rerank(FOUR, "q", enabled=True)
    assert_identity(result, FOUR)
    for name in ("onnx", "fastembed", "flashrank"):
        assert f"{name}:" in result.reason
    assert "not installed" in result.reason


def test_model_files_absent_and_download_off_says_how_to_fix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install(monkeypatch, FakeOnnxWorld().modules())
    monkeypatch.setenv(ENV_MODEL_DIR, str(tmp_path))
    result = run_rerank(FOUR, "q", backend="onnx", enabled=True)
    assert_identity(result, FOUR)
    assert "not found" in result.reason
    assert str(tmp_path) in result.reason
    assert f"{ENV_ALLOW_DOWNLOAD}=1" in result.reason
    # One explicit backend -> its bare reason, not the "auto" aggregate wrapper.
    assert result.reason.startswith("onnx: ")


def test_top_k_of_one_is_valid_and_rescores_exactly_one(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank(FOUR, "q", enabled=True, backend="onnx", top_k=1)
    assert result.reranked is True and result.top_k == 1
    assert result.rescored == 1 and result.results[1:] == tuple(FOUR[1:])


def test_latency_ms_is_wall_time_in_milliseconds_on_both_paths(
    monkeypatch: pytest.MonkeyPatch, onnx_world: FakeOnnxWorld
) -> None:
    # rerank() reads the clock exactly twice per call: at entry and when it builds the result.
    ticks = iter([10.0, 10.25, 20.0, 20.5])
    monkeypatch.setattr(rerank, "perf_counter", lambda: next(ticks))
    assert run_rerank(FOUR, "q", enabled=False).latency_ms == 250.0  # identity path
    assert run_rerank(FOUR, "q", enabled=True, backend="onnx").latency_ms == 500.0


# --------------------------------------------------------------------------
# rerank(): the onnx backend actually reorders
# --------------------------------------------------------------------------


def test_onnx_backend_reorders_the_head_by_model_score(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank(FOUR, "q", enabled=True, backend="onnx")
    assert result.reranked is True
    assert result.reason == ""
    assert result.backend == "onnx"
    assert result.model == DEFAULT_MODEL
    assert [r.title for r in result.results] == ["Beta", "Delta", "Gamma", "Alpha"]
    assert result.scores == (0.9, 0.7, 0.5, 0.1)
    assert result.rescored == 4 and result.skipped == 0
    assert result.latency_ms >= 0.0
    # Input untouched: FusedResult is frozen and shared, never mutated or copied.
    assert [r.title for r in FOUR] == ["Alpha", "Beta", "Gamma", "Delta"]
    assert all(a is b for a, b in zip(sorted(result.results, key=FOUR.index), FOUR))


def test_auto_picks_onnx_first_when_available(onnx_world: FakeOnnxWorld) -> None:
    result = run_rerank(FOUR, "q", enabled=True)  # backend="auto"
    assert result.reranked is True and result.backend == "onnx"


def test_onnx_scoring_text_is_title_space_snippet_paired_with_query(
    onnx_world: FakeOnnxWorld,
) -> None:
    run_rerank(FOUR, "the query", enabled=True, backend="onnx")
    [tokenizer] = onnx_world.tokenizers
    assert tokenizer.batches == [
        [
            ("the query", "Alpha first passage"),
            ("the query", "Beta second passage"),
            ("the query", "Gamma third passage"),
            ("the query", "Delta fourth passage"),
        ]
    ]


def test_onnx_tokenizer_truncates_to_the_model_budget_and_pads(
    onnx_world: FakeOnnxWorld,
) -> None:
    run_rerank(FOUR, "q", enabled=True, backend="onnx")
    [tokenizer] = onnx_world.tokenizers
    assert tokenizer.truncation == MAX_TOKENS
    assert tokenizer.padding is True
    [session] = onnx_world.sessions
    assert session.providers == ["CPUExecutionProvider"]
    assert session.path.endswith(os.path.join("onnx", "model_quantized.onnx"))
    assert tokenizer.path.endswith("tokenizer.json")


def test_onnx_feeds_only_the_inputs_the_model_declares(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld(
        {"Alpha first passage": 1.0}, input_names=("input_ids", "attention_mask")
    )
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    result = run_rerank(
        FOUR[:1], "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert result.reranked is True
    [feeds] = world.run_feeds
    assert set(feeds) == {"input_ids", "attention_mask"}
    assert feeds["input_ids"] == [[1]] and feeds["attention_mask"] == [[1]]


def test_onnx_model_declaring_an_unknown_input_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld(input_names=("input_ids", "pixel_values"))
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert "pixel_values" in result.reason


def test_onnx_scores_in_batches_of_batch_size(onnx_world: FakeOnnxWorld) -> None:
    many = fused(*[(f"https://x/{i}", f"T{i}", f"p{i}") for i in range(BATCH_SIZE + 1)])
    result = run_rerank(many, "q", enabled=True, backend="onnx", top_k=len(many))
    assert result.reranked is True and result.rescored == BATCH_SIZE + 1
    assert [len(f["input_ids"]) for f in onnx_world.run_feeds] == [BATCH_SIZE, 1]
    # All scores 0.0 (unknown texts) -> ties keep the RRF order.
    assert [r.title for r in result.results] == [r.title for r in many]


@pytest.mark.parametrize(
    "layout",
    [
        "onnx/model_quantized.onnx",
        "model_quantized.onnx",
        "onnx/model.onnx",
        "model.onnx",
    ],
)
def test_onnx_finds_the_model_file_in_any_supported_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, layout: str
) -> None:
    world = FakeOnnxWorld()
    install(monkeypatch, world.modules())
    make_model_files(tmp_path, layout)
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert result.reranked is True
    assert world.sessions[0].path.endswith(os.path.join(*layout.split("/")))


@pytest.mark.parametrize("remove", ["tokenizer.json", "onnx/model_quantized.onnx"])
def test_onnx_needs_both_the_tokenizer_and_a_model_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, remove: str
) -> None:
    install(monkeypatch, FakeOnnxWorld().modules())
    root = make_model_files(tmp_path)
    root.joinpath(*remove.split("/")).unlink()
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert "not found" in result.reason


@pytest.mark.parametrize("missing", ["tokenizers", "numpy"])
def test_onnx_names_the_missing_companion_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing: str
) -> None:
    modules = FakeOnnxWorld().modules()
    modules.pop(missing)
    install(monkeypatch, modules)
    make_model_files(tmp_path)
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert f"onnx: {missing} not installed" in result.reason


# --------------------------------------------------------------------------
# rerank(): top_k window, skipped items, ties
# --------------------------------------------------------------------------


def test_only_the_top_k_are_rescored_and_the_tail_keeps_rrf_order(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank(FOUR, "q", enabled=True, backend="onnx", top_k=2)
    assert [r.title for r in result.results] == ["Beta", "Alpha", "Gamma", "Delta"]
    assert result.scores == (0.9, 0.1, None, None)
    assert result.rescored == 2 and result.top_k == 2
    [tokenizer] = onnx_world.tokenizers
    assert len(tokenizer.batches[0]) == 2


def test_top_k_larger_than_the_list_rescores_everything(
    onnx_world: FakeOnnxWorld,
) -> None:
    result = run_rerank(FOUR, "q", enabled=True, backend="onnx", top_k=100)
    assert result.rescored == 4
    assert None not in result.scores


def test_items_without_title_or_snippet_are_skipped_and_follow_the_rescored_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld({"Alpha": 0.2, "only a snippet": 0.8})
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    items = fused(
        ("https://a/1", "Alpha", ""),  # title only -> scored on the title
        ("https://b/2", "", ""),  # nothing -> skipped, truthfully
        ("https://c/3", "", "only a snippet"),  # snippet only -> scored
        ("https://d/4", "", ""),  # skipped
        ("https://e/5", "Tail", "beyond top_k"),
    )
    result = run_rerank(
        items, "q", enabled=True, backend="onnx", top_k=4, model_dir=str(tmp_path)
    )
    assert result.reranked is True
    assert [r.url for r in result.results] == [
        "https://c/3",
        "https://a/1",
        "https://b/2",
        "https://d/4",
        "https://e/5",
    ]
    assert result.scores == (0.8, 0.2, None, None, None)
    assert result.rescored == 2 and result.skipped == 2
    # The model only ever saw the two scorable texts.
    assert world.tokenizers[0].batches == [[("q", "Alpha"), ("q", "only a snippet")]]


def test_head_with_no_scorable_text_is_identity_but_names_the_loaded_backend(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld()
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    items = fused(("https://a/1", "", ""), ("https://b/2", "", ""))
    result = run_rerank(
        items, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert_identity(result, items)
    assert result.backend == "onnx"
    assert "no title or snippet" in result.reason
    assert world.run_feeds == []  # nothing was sent to the model


def test_equal_scores_keep_the_rrf_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld({scoring_text(r): 0.5 for r in FOUR})
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert result.results == tuple(FOUR)
    assert result.scores == (0.5, 0.5, 0.5, 0.5)


# --------------------------------------------------------------------------
# rerank(): scoring-time failures degrade to identity, never raise
# --------------------------------------------------------------------------


def test_backend_exception_while_scoring_is_identity_with_the_error_in_the_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld()
    install(monkeypatch, world.modules())
    make_model_files(tmp_path)

    def boom(self: Any, outputs: None, feeds: dict[str, Any]) -> list[Any]:
        raise RuntimeError("ORT exploded")

    monkeypatch.setattr(sys.modules["onnxruntime"].InferenceSession, "run", boom)
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert result.backend == "onnx"
    assert "ORT exploded" in result.reason


def test_backend_returning_the_wrong_number_of_scores_is_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def short(query: str, texts: Any) -> list[float]:
        return [1.0]

    loaded = LoadedBackend(name="onnx", model=DEFAULT_MODEL, score=short)
    monkeypatch.setattr(rerank, "load_backend", lambda *a, **k: loaded)
    result = run_rerank(FOUR, "q", enabled=True, backend="onnx")
    assert_identity(result, FOUR)
    assert "1 scores for 4 texts" in result.reason


# --------------------------------------------------------------------------
# process-level backend cache
# --------------------------------------------------------------------------


def test_backend_is_loaded_once_per_process_until_reset(
    onnx_world: FakeOnnxWorld,
) -> None:
    run_rerank(FOUR, "q", enabled=True)
    run_rerank(FOUR, "q2", enabled=True)
    # auto resolved to onnx -> same cache entry
    run_rerank(FOUR, "q3", enabled=True, backend="onnx")
    assert len(onnx_world.sessions) == 1
    assert len(onnx_world.tokenizers) == 1
    reset_backend_cache()
    run_rerank(FOUR, "q", enabled=True)
    assert len(onnx_world.sessions) == 2


def test_cache_is_keyed_by_model_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, onnx_world: FakeOnnxWorld
) -> None:
    other = tmp_path / "other"
    make_model_files(other)
    run_rerank(FOUR, "q", enabled=True, backend="onnx")
    run_rerank(FOUR, "q", enabled=True, backend="onnx", model_dir=str(other))
    assert len(onnx_world.sessions) == 2


def test_load_backend_raises_when_nothing_loads_and_returns_a_loaded_backend_otherwise(
    onnx_world: FakeOnnxWorld,
) -> None:
    with pytest.raises(BackendUnavailable, match="fastembed not installed"):
        load_backend("fastembed", DEFAULT_MODEL)
    loaded = load_backend("auto", DEFAULT_MODEL)
    assert isinstance(loaded, LoadedBackend)
    assert (loaded.name, loaded.model) == ("onnx", DEFAULT_MODEL)
    assert loaded.score("q", ["Beta second passage"]) == [0.9]


def test_load_backend_rejects_none_and_unknown_names() -> None:
    with pytest.raises(ValueError, match="backend"):
        load_backend("none", DEFAULT_MODEL)
    with pytest.raises(ValueError, match="backend"):
        load_backend("tpu", DEFAULT_MODEL)


# --------------------------------------------------------------------------
# onnx model download (only ever with RERANK_ALLOW_DOWNLOAD=1)
# --------------------------------------------------------------------------


def test_download_is_never_attempted_when_not_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install(monkeypatch, FakeOnnxWorld().modules())
    calls: list[str] = []
    monkeypatch.setattr(rerank, "urlopen", lambda url, timeout: calls.append(url))
    result = run_rerank(
        FOUR, "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert result.reranked is False
    assert calls == []


def test_download_fetches_the_two_hub_files_when_allowed_by_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeOnnxWorld({"Alpha first passage": 1.0})
    install(monkeypatch, world.modules())
    calls: list[tuple[str, int]] = []

    def fake_urlopen(url: str, timeout: int) -> io.BytesIO:
        calls.append((url, timeout))
        return io.BytesIO(b"payload")

    monkeypatch.setattr(rerank, "urlopen", fake_urlopen)
    monkeypatch.setenv(ENV_ALLOW_DOWNLOAD, "1")
    result = run_rerank(
        FOUR[:1], "q", enabled=True, backend="onnx", model_dir=str(tmp_path)
    )
    assert result.reranked is True
    assert [url for url, _ in calls] == [
        f"https://huggingface.co/{DEFAULT_MODEL}/resolve/main/onnx/model_quantized.onnx",
        f"https://huggingface.co/{DEFAULT_MODEL}/resolve/main/tokenizer.json",
    ]
    # A 23 MB file on a slow link needs minutes, not urllib's default of "forever".
    assert [timeout for _, timeout in calls] == [120, 120]
    root = tmp_path.joinpath(*DEFAULT_MODEL.split("/"))
    assert (root / "onnx" / "model_quantized.onnx").read_bytes() == b"payload"
    assert (root / "tokenizer.json").read_bytes() == b"payload"
    assert not list(root.rglob("*.part"))  # atomic rename, no partial left behind


def test_download_failure_is_identity_with_the_url_in_the_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install(monkeypatch, FakeOnnxWorld().modules())

    def failing_urlopen(url: str, timeout: int) -> io.BytesIO:
        raise OSError("connection refused")

    monkeypatch.setattr(rerank, "urlopen", failing_urlopen)
    result = run_rerank(
        FOUR,
        "q",
        enabled=True,
        backend="onnx",
        model_dir=str(tmp_path),
        allow_download=True,
    )
    assert_identity(result, FOUR)
    assert "download" in result.reason and "connection refused" in result.reason
    assert "huggingface.co" in result.reason


def test_default_model_dir_is_under_the_user_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/home/someone")
    monkeypatch.setattr(
        os.path, "expanduser", lambda p: p.replace("~", "/home/someone")
    )
    expected = os.path.join("/home/someone", ".cache", "search-expansion", "rerank")
    assert rerank.resolve_model_dir() == expected
    monkeypatch.setenv(ENV_MODEL_DIR, "/models")
    assert rerank.resolve_model_dir() == "/models"
    assert rerank.resolve_model_dir("/explicit") == "/explicit"


# --------------------------------------------------------------------------
# fastembed + flashrank backends, and the auto order
# --------------------------------------------------------------------------


def test_auto_falls_through_to_fastembed_when_onnx_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFastembedWorld({"Alpha first passage": 0.2, "Beta second passage": 0.8})
    install(monkeypatch, world.modules())
    result = run_rerank(FOUR[:2], "q", enabled=True, model_dir=str(tmp_path))
    assert result.reranked is True
    assert result.backend == "fastembed" and result.model == DEFAULT_MODEL
    assert [r.title for r in result.results] == ["Beta", "Alpha"]
    assert result.scores == (0.8, 0.2)
    [encoder] = world.encoders
    assert encoder.model_name == DEFAULT_MODEL
    assert encoder.cache_dir == str(tmp_path)
    assert encoder.local_files_only is True  # downloads stay off unless asked for


def test_fastembed_allows_download_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFastembedWorld()
    install(monkeypatch, world.modules())
    monkeypatch.setenv(ENV_ALLOW_DOWNLOAD, "true")
    run_rerank(FOUR, "q", enabled=True, backend="fastembed", model_dir=str(tmp_path))
    assert world.encoders[0].local_files_only is False


def test_fastembed_constructor_failure_is_a_truthful_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install(monkeypatch, FakeFastembedWorld(fail="model not in cache").modules())
    result = run_rerank(FOUR, "q", enabled=True, backend="fastembed")
    assert_identity(result, FOUR)
    assert "fastembed" in result.reason and "model not in cache" in result.reason


def test_auto_falls_through_to_flashrank_last(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFlashrankWorld({"Alpha first passage": 0.1, "Beta second passage": 0.9})
    install(monkeypatch, world.modules())
    (tmp_path / "ms-marco-MiniLM-L-12-v2").mkdir()
    result = run_rerank(FOUR[:2], "q", enabled=True, model_dir=str(tmp_path))
    assert result.reranked is True
    assert result.backend == "flashrank"
    # flashrank ships no L-6 build; the documented substitute is reported, not hidden.
    assert result.model == "ms-marco-MiniLM-L-12-v2"
    assert [r.title for r in result.results] == ["Beta", "Alpha"]
    # Mapped back by id, not taken in flashrank's (best-first) order.
    assert result.scores == (0.9, 0.1)
    [ranker] = world.rankers
    assert (ranker.model_name, ranker.cache_dir) == (
        "ms-marco-MiniLM-L-12-v2",
        str(tmp_path),
    )


def test_flashrank_passes_an_unmapped_model_name_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFlashrankWorld()
    install(monkeypatch, world.modules())
    (tmp_path / "rank-T5-flan").mkdir()
    result = run_rerank(
        FOUR,
        "q",
        enabled=True,
        backend="flashrank",
        model="rank-T5-flan",
        model_dir=str(tmp_path),
    )
    assert result.reranked is True and result.model == "rank-T5-flan"


def test_flashrank_missing_model_dir_without_download_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFlashrankWorld()
    install(monkeypatch, world.modules())
    result = run_rerank(
        FOUR, "q", enabled=True, backend="flashrank", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert "flashrank" in result.reason and f"{ENV_ALLOW_DOWNLOAD}=1" in result.reason
    assert world.rankers == []  # the constructor (which downloads) was never called


def test_flashrank_missing_model_dir_with_download_constructs_the_ranker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFlashrankWorld()
    install(monkeypatch, world.modules())
    result = run_rerank(
        FOUR,
        "q",
        enabled=True,
        backend="flashrank",
        model_dir=str(tmp_path),
        allow_download=True,
    )
    assert result.reranked is True
    assert len(world.rankers) == 1


def test_flashrank_dropping_a_passage_is_identity_not_a_silent_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    world = FakeFlashrankWorld({"Alpha first passage": 0.1, "Beta second passage": 0.9})
    modules = world.modules()
    ranker_cls = modules["flashrank"].Ranker
    full = ranker_cls.rerank
    ranker_cls.rerank = lambda self, request: full(self, request)[
        :-1
    ]  # loses the worst one
    install(monkeypatch, modules)
    (tmp_path / "ms-marco-MiniLM-L-12-v2").mkdir()
    result = run_rerank(
        FOUR[:2], "q", enabled=True, backend="flashrank", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR[:2])
    assert result.backend == "flashrank" and "scoring failed" in result.reason


def test_flashrank_constructor_failure_is_a_truthful_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install(monkeypatch, FakeFlashrankWorld(fail="corrupt model").modules())
    (tmp_path / "ms-marco-MiniLM-L-12-v2").mkdir()
    result = run_rerank(
        FOUR, "q", enabled=True, backend="flashrank", model_dir=str(tmp_path)
    )
    assert_identity(result, FOUR)
    assert "flashrank" in result.reason and "corrupt model" in result.reason


def test_auto_reason_concatenates_reasons_in_probe_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    install(monkeypatch, FakeFastembedWorld(fail="no cache").modules())
    result = run_rerank(FOUR, "q", enabled=True, model_dir=str(tmp_path))
    onnx_at = result.reason.index("onnx:")
    fastembed_at = result.reason.index("fastembed:")
    flashrank_at = result.reason.index("flashrank:")
    assert onnx_at < fastembed_at < flashrank_at
    assert "no cache" in result.reason


# --------------------------------------------------------------------------
# eval_rerank: metrics, hand-computed
# --------------------------------------------------------------------------


def test_ndcg_at_k_matches_the_textbook_example() -> None:
    # Graded relevance in ranked order (the Wikipedia DCG worked example):
    # DCG = 3 + 2/log2(3) + 3/log2(4) + 0 + 1/log2(6) + 2/log2(7) = 6.8611
    # IDCG over [3, 3, 2, 2, 1, 0] = 7.1410  ->  nDCG = 0.9608
    assert ndcg_at_k([3, 2, 3, 0, 1, 2], k=6) == pytest.approx(0.9608, abs=1e-4)


def test_ndcg_at_k_cuts_at_k_for_both_dcg_and_idcg() -> None:
    # @1: DCG = 3 (rel of the top item); IDCG = 3 -> 1.0
    assert ndcg_at_k([3, 2, 3], k=1) == pytest.approx(1.0)
    # @2: DCG = 0 + 1/log2(3); IDCG = 1 -> 0.6309
    assert ndcg_at_k([0, 1, 0], k=2) == pytest.approx(1 / 1.58496, abs=1e-4)


def test_ndcg_uses_the_ideal_grades_when_given() -> None:
    # Pool holds one of two relevant docs; the qrels-based ideal makes it 1 / (1 + 1/log2 3).
    assert ndcg_at_k([1, 0, 0], k=10, ideal=[1, 1]) == pytest.approx(
        1 / 1.63093, abs=1e-4
    )
    # An ideal with no positive grade is treated like an empty one.
    assert ndcg_at_k([1, 0], k=10, ideal=[0, 0]) is None


def test_ndcg_is_none_when_nothing_is_relevant() -> None:
    assert ndcg_at_k([0, 0, 0], k=10) is None
    assert ndcg_at_k([], k=10) is None


def test_recall_at_k_hand_computed() -> None:
    # Relevant at ranks 2, 5, 6 -> top-5 catches 2 of 3.
    assert recall_at_k([0, 1, 0, 0, 1, 1, 0], k=5) == pytest.approx(2 / 3)
    # Denominator from the qrels when given: 2 caught out of 4 judged relevant.
    assert recall_at_k([1, 1, 0], k=5, total_relevant=4) == pytest.approx(0.5)


def test_recall_at_k_is_none_when_nothing_is_relevant() -> None:
    assert recall_at_k([0, 0], k=5) is None
    assert recall_at_k([1, 0], k=5, total_relevant=0) is None


# --------------------------------------------------------------------------
# eval_rerank: loading + adapting the eval set
# --------------------------------------------------------------------------


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


SMOKE_ROWS: list[dict[str, Any]] = [
    {
        "qid": "q1",
        "query": "alpha",
        "candidates": [
            {
                "url": "https://a/1",
                "title": "Alpha",
                "snippet": "first passage",
                "rel": 0,
            },
            {
                "url": "https://b/2",
                "title": "Beta",
                "snippet": "second passage",
                "rel": 1,
            },
            {
                "url": "https://c/3",
                "title": "Gamma",
                "snippet": "third passage",
                "rel": 0,
            },
        ],
    },
    {
        "query": "beta",
        "ideal_rels": [2, 1],
        "candidates": [
            {"url": "https://a/1", "title": "Alpha", "rel": 2},
            {"url": "https://b/2", "snippet": "second passage", "rel": 0},
        ],
    },
    {
        "qid": "q3",
        "query": "no relevant here",
        "candidates": [
            {"url": "https://a/1", "title": "Alpha", "snippet": "x", "rel": 0}
        ],
    },
]


def test_load_eval_set_parses_jsonl_with_defaults_and_skips_blank_lines(
    tmp_path: Path,
) -> None:
    path = tmp_path / "set.jsonl"
    text = "".join(json.dumps(r) + "\n" for r in SMOKE_ROWS)
    # One blank line inside the file.
    path.write_text(text.replace("\n", "\n\n", 1), encoding="utf-8")
    queries = load_eval_set(str(path))
    # Missing qid -> the 1-based FILE line number (the blank line pushed row 2 onto line 3).
    assert [q.qid for q in queries] == ["q1", "3", "q3"]
    assert queries[0].query == "alpha"
    assert queries[0].ideal_rels is None
    assert queries[1].ideal_rels == (2, 1)
    assert queries[1].candidates[0] == Candidate("https://a/1", "Alpha", "", 2)
    assert queries[1].candidates[1] == Candidate("https://b/2", "", "second passage", 0)
    assert isinstance(queries[0].candidates, tuple)


def test_load_eval_set_reads_a_gzipped_set_transparently(tmp_path: Path) -> None:
    text = "".join(json.dumps(r) + "\n" for r in SMOKE_ROWS)
    path = tmp_path / "set.jsonl.gz"
    path.write_bytes(gzip.compress(text.encode("utf-8")))
    queries = load_eval_set(str(path))
    assert [q.qid for q in queries] == ["q1", "2", "q3"]


def test_write_text_gzips_by_extension_with_reproducible_bytes(tmp_path: Path) -> None:
    plain = tmp_path / "a.jsonl"
    eval_rerank._write_text(str(plain), "row\n")
    assert plain.read_text(encoding="utf-8") == "row\n"
    first, second = tmp_path / "b.jsonl.gz", tmp_path / "c.jsonl.gz"
    eval_rerank._write_text(str(first), "row\n")
    eval_rerank._write_text(str(second), "row\n")
    assert gzip.decompress(first.read_bytes()) == b"row\n"
    # Same rows -> same bytes (mtime pinned to 0, no embedded name): a rebuilt committed set
    # shows up as unchanged in git when the data did not change.
    assert first.read_bytes() == second.read_bytes()
    # RFC 1952 header: MTIME is bytes 4..8 and 0 means "no time stamp available"; anything
    # else would stamp the build time into the committed bytes.
    assert first.read_bytes()[4:8] == b"\x00\x00\x00\x00"


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("[]", "object"),
        ('{"candidates": []}', "query"),
        ('{"query": "q"}', "candidates"),
        (
            '{"query": "q", "candidates": ["https://u"]}',
            "candidate 1: expected an object",
        ),
        ('{"query": "q", "candidates": [{"title": "t", "rel": 0}]}', "url"),
        ('{"query": "q", "candidates": [{"url": "u"}]}', "rel"),
        ('{"query": "q", "candidates": [{"url": "u", "rel": "high"}]}', "rel"),
        ('{"query": "q", "candidates": [{"url": "u", "rel": true}]}', "rel"),
        ('{"query": "q", "candidates": [], "ideal_rels": "1"}', "ideal_rels"),
    ],
)
def test_load_eval_set_rejects_malformed_rows_with_the_line_number(
    tmp_path: Path, row: str, message: str
) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(SMOKE_ROWS[0]) + "\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"line 2.*{message}"):
        load_eval_set(str(path))


def test_candidates_to_fused_builds_a_descending_rrf_shaped_list() -> None:
    cands = (
        Candidate("https://a/1", "Alpha", "p1", 1),
        Candidate("https://b/2", "", "", 0),
    )
    out = candidates_to_fused(cands)
    assert [type(r) for r in out] == [FusedResult, FusedResult]
    assert [(r.url, r.display_url, r.title, r.snippet) for r in out] == [
        ("https://a/1", "https://a/1", "Alpha", "p1"),
        ("https://b/2", "https://b/2", "", ""),
    ]
    assert out[0].score > out[1].score > 0
    assert out[0].sources == ("eval",) and dict(out[0].ranks) == {"eval": 1}
    assert dict(out[1].ranks) == {"eval": 2}
    # "RRF-shaped" means the scores are exactly what the real fuser gives one provider's
    # list at the default k, so the reranker sees the same numbers it would in production.
    real = reciprocal_rank_fusion(
        {
            "eval": [
                {"url": c.url, "title": c.title, "snippet": c.snippet} for c in cands
            ]
        }
    )
    assert [r.score for r in out] == [r.score for r in real]


# --------------------------------------------------------------------------
# eval_rerank: evaluate() with an injected rerank function
# --------------------------------------------------------------------------


def smoke_queries() -> list[EvalQuery]:
    return [
        EvalQuery(
            qid=str(row.get("qid", i)),
            query=row["query"],
            candidates=tuple(
                Candidate(c["url"], c.get("title", ""), c.get("snippet", ""), c["rel"])
                for c in row["candidates"]
            ),
            ideal_rels=tuple(row["ideal_rels"]) if "ideal_rels" in row else None,
        )
        for i, row in enumerate(SMOKE_ROWS, start=1)
    ]


def reversing_rerank(fused: Any, query: str, **kwargs: Any) -> RerankResult:
    items = tuple(reversed(list(fused)))
    return RerankResult(
        results=items,
        scores=tuple(float(len(items) - i) for i in range(len(items))),
        reranked=True,
        backend=kwargs["backend"],
        model="fake-model",
        latency_ms=2.0,
        reason="",
        top_k=kwargs["top_k"],
        rescored=len(items),
        skipped=0,
    )


def unavailable_rerank(fused: Any, query: str, **kwargs: Any) -> RerankResult:
    items = tuple(fused)
    return RerankResult(
        results=items,
        scores=(None,) * len(items),
        reranked=False,
        backend="none",
        model=kwargs["model"],
        latency_ms=0.5,
        reason="no rerank backend available: onnx: onnxruntime not installed",
        top_k=kwargs["top_k"],
        rescored=0,
        skipped=0,
    )


def test_evaluate_reports_before_and_after_metrics_per_backend() -> None:
    report = evaluate(
        smoke_queries(), backends=["onnx"], top_k=3, rerank_fn=reversing_rerank
    )
    assert report["n_queries"] == 3
    # q3 has no relevant document anywhere -> excluded from the means.
    assert report["n_scored"] == 2
    assert report["top_k"] == 3
    # Baseline: q1 rel at rank 2 -> nDCG 1/log2(3) = 0.6309, recall@5 = 1.
    #           q2 rel at rank 1 grade 2, ideal [2,1] -> DCG 2, IDCG 2 + 1/log2(3) = 2.6309 -> 0.7602
    #           recall@5 for q2: 1 of 2 judged relevant -> 0.5
    base = report["baseline"]
    assert base["ndcg@10"] == pytest.approx((0.63093 + 0.76022) / 2, abs=1e-4)
    assert base["recall@5"] == pytest.approx((1.0 + 0.5) / 2)
    after = report["backends"]["onnx"]
    assert after["available"] is True and after["reason"] == ""
    assert after["model"] == "fake-model"
    assert after["reranked_queries"] == 3
    # Reversed: q1 rel moves to rank 2 (of 3) -> unchanged 0.6309; q2 rel moves to rank 2 ->
    # DCG 2/log2(3) = 1.2619 / 2.6309 = 0.4796
    assert after["ndcg@10"] == pytest.approx((0.63093 + 0.47963) / 2, abs=1e-4)
    assert after["recall@5"] == pytest.approx((1.0 + 0.5) / 2)
    assert after["lift_ndcg@10"] == pytest.approx(after["ndcg@10"] - base["ndcg@10"])
    assert after["lift_recall@5"] == pytest.approx(0.0)
    assert after["improved"] == 0 and after["worsened"] == 1 and after["unchanged"] == 1
    assert after["latency_ms"] == {"mean": 2.0, "p50": 2.0, "max": 2.0}
    assert after["recommendation"].startswith("leave off")
    assert after["per_query"] == [
        ["q1", pytest.approx(0.63093, abs=1e-4), pytest.approx(0.63093, abs=1e-4)],
        ["2", pytest.approx(0.76022, abs=1e-4), pytest.approx(0.47963, abs=1e-4)],
    ]
    assert report["decision_rule"].startswith("RERANK_ENABLED=1 only if")


def test_evaluate_cuts_ndcg_at_10_and_recall_at_5_exactly() -> None:
    # 12 candidates, relevant at ranks 6 and 11 (pool ideal [1, 1] -> IDCG = 1 + 1/log2 3).
    cands = tuple(
        Candidate(f"https://x/{i}", f"T{i}", "s", 1 if i in (6, 11) else 0)
        for i in range(1, 13)
    )
    query = EvalQuery("q", "q", cands)
    report = evaluate(
        [query], backends=["none"], top_k=12, rerank_fn=unavailable_rerank
    )
    base = report["baseline"]
    # nDCG@10 sees rank 6 only: (1/log2 7) / 1.63093 = 0.21841 (rank 11 would add 1/log2 12).
    assert base["ndcg@10"] == pytest.approx(0.21841, abs=1e-5)
    # recall@5 sees neither (rank 6 is just outside the window).
    assert base["recall@5"] == 0.0


def test_evaluate_rounds_per_query_to_6_places_and_latency_to_3() -> None:
    def slow(fused: Any, query: str, **kwargs: Any) -> RerankResult:
        out = unavailable_rerank(fused, query, **kwargs)
        return RerankResult(**{**out.__dict__, "latency_ms": 1.23456})

    report = evaluate(smoke_queries()[:1], backends=["onnx"], top_k=3, rerank_fn=slow)
    after = report["backends"]["onnx"]
    assert after["per_query"] == [["q1", 0.63093, 0.63093]]  # 1/log2 3 = 0.6309297...
    assert after["latency_ms"] == {"mean": 1.235, "p50": 1.235, "max": 1.235}


def test_evaluate_counts_improved_worsened_unchanged_with_a_tolerance() -> None:
    # Three scored queries: q1 unchanged, q2 worsened, q3 unchanged -> 0 / 1 / 2 (not 0 / 2 / 1).
    extra = EvalQuery(
        "q4",
        "extra",
        (Candidate("https://a/1", "A", "s", 1), Candidate("https://b/2", "B", "s", 0)),
    )

    def worsen_q2_only(fused: Any, query: str, **kwargs: Any) -> RerankResult:
        if query == "beta":
            return reversing_rerank(fused, query, **kwargs)
        return unavailable_rerank(fused, query, **kwargs)

    report = evaluate(
        [*smoke_queries(), extra], backends=["x"], top_k=3, rerank_fn=worsen_q2_only
    )
    after = report["backends"]["x"]
    assert (after["improved"], after["worsened"], after["unchanged"]) == (0, 1, 2)


def test_evaluate_with_an_unavailable_backend_is_honest() -> None:
    report = evaluate(
        smoke_queries(), backends=["onnx"], top_k=3, rerank_fn=unavailable_rerank
    )
    after = report["backends"]["onnx"]
    assert after["available"] is False
    assert "onnxruntime not installed" in after["reason"]
    assert after["reranked_queries"] == 0
    assert after["ndcg@10"] == pytest.approx(report["baseline"]["ndcg@10"])
    assert after["lift_ndcg@10"] == pytest.approx(0.0)
    assert (
        after["recommendation"] == "leave off (backend unavailable, nothing measured)"
    )


def test_evaluate_recommends_enabling_only_at_or_above_the_threshold() -> None:
    def improving(fused: Any, query: str, **kwargs: Any) -> RerankResult:
        # Put the relevant candidate first for every query.
        items = tuple(sorted(fused, key=lambda r: 0 if r.url == "https://b/2" else 1))
        if query == "beta":
            items = tuple(fused)  # already ideal
        return RerankResult(
            items, (1.0,) * len(items), True, "x", "m", 1.0, "", 3, 3, 0
        )

    report = evaluate(smoke_queries(), backends=["x"], top_k=3, rerank_fn=improving)
    after = report["backends"]["x"]
    assert after["lift_ndcg@10"] == pytest.approx((1.0 - 0.63093) / 2, abs=1e-4)
    assert after["improved"] == 1
    assert after["recommendation"].startswith("RERANK_ENABLED=1")


def test_evaluate_with_no_scorable_query_reports_none_not_a_crash() -> None:
    report = evaluate(
        smoke_queries()[2:], backends=["onnx"], top_k=3, rerank_fn=reversing_rerank
    )
    assert report["n_scored"] == 0
    assert report["baseline"] == {"ndcg@10": None, "recall@5": None}
    after = report["backends"]["onnx"]
    assert after["ndcg@10"] is None and after["lift_ndcg@10"] is None
    assert after["latency_ms"] == {"mean": 2.0, "p50": 2.0, "max": 2.0}
    assert (
        after["recommendation"]
        == "leave off (no query with a judged relevant document)"
    )


def test_evaluate_passes_backend_top_k_and_forces_enabled() -> None:
    seen: list[dict[str, Any]] = []

    def spy(fused: Any, query: str, **kwargs: Any) -> RerankResult:
        seen.append(kwargs)
        return unavailable_rerank(fused, query, **kwargs)

    evaluate(
        smoke_queries()[:1], backends=["flashrank"], top_k=7, rerank_fn=spy, model="m"
    )
    assert seen == [{"backend": "flashrank", "top_k": 7, "enabled": True, "model": "m"}]


def test_summarize_markdown_has_one_row_per_backend_and_the_verdict() -> None:
    report = evaluate(
        smoke_queries(),
        backends=["onnx", "flashrank"],
        top_k=3,
        rerank_fn=reversing_rerank,
    )
    report["eval_set"] = "eval/smoke.jsonl"
    text = summarize_markdown(report)
    assert "eval/smoke.jsonl" in text
    assert "| baseline (RRF order) |" in text
    assert "| onnx |" in text and "| flashrank |" in text
    assert "leave off" in text
    assert "3 queries" in text and "2 with a judged relevant document" in text
    # The lift column is signed to four places, exactly as the JSON's recommendation quotes it.
    lift = report["backends"]["onnx"]["lift_ndcg@10"]
    assert f"| {lift:+.4f} |" in text


def test_summarize_markdown_renders_none_metrics_as_dashes() -> None:
    report = evaluate(
        smoke_queries()[2:], backends=["onnx"], top_k=3, rerank_fn=reversing_rerank
    )
    text = summarize_markdown(report)
    assert "| baseline (RRF order) | - | - |" in text
    # Metrics AND lift render as dashes, never as "None".
    assert "| onnx | - | - | - |" in text


# --------------------------------------------------------------------------
# eval_rerank: BM25 + BEIR conversion (the first-stage stand-in for SearXNG)
# --------------------------------------------------------------------------


def test_bm25_ranks_the_matching_document_first_and_ignores_unknown_terms() -> None:
    index = BM25({"d1": "cats purr", "d2": "dogs bark loudly", "d3": "cats and dogs"})
    assert [d for d, _ in index.search("purr", top=3)] == ["d1"]
    assert index.search("zebra", top=3) == []
    ranked = index.search("cats dogs", top=2)
    assert [d for d, _ in ranked] == [
        "d3",
        "d1",
    ]  # both terms beat one, then ties by id
    assert ranked[0][1] > ranked[1][1] > 0


def test_bm25_length_normalisation_prefers_the_shorter_document_on_equal_tf() -> None:
    index = BM25({"long": "cats " + "filler " * 20, "short": "cats filler"})
    assert [d for d, _ in index.search("cats", top=2)] == ["short", "long"]


def test_bm25_scores_match_the_okapi_formula_by_hand() -> None:
    # d1 = "a b" (len 2), d2 = "a a c" (len 3): N = 2, avgdl = 2.5, k1 = 0.9, b = 0.4.
    index = BM25({"d1": "a b", "d2": "a a c"})
    assert index.avgdl == 2.5
    # "c": df 1 -> idf = ln(1 + 1.5/1.5) = ln 2; norm(d2) = 0.6 + 0.4 * 3/2.5 = 1.08;
    # score = ln 2 * 1 * 1.9 / (1 + 0.9 * 1.08) = 0.693147 * 1.9 / 1.972 = 0.667840
    [(doc, score)] = index.search("c", top=5)
    assert doc == "d2" and score == pytest.approx(0.667840, abs=1e-6)
    # "a": df 2 -> idf = ln(1 + 0.5/2.5) = ln 1.2 = 0.182322
    #   d1: norm = 0.6 + 0.4 * 2/2.5 = 0.92; 0.182322 * 1.9 / (1 + 0.828) = 0.189503
    #   d2: tf 2; 0.182322 * 2 * 1.9 / (2 + 0.972) = 0.233116
    ranked = index.search("a", top=5)
    assert [d for d, _ in ranked] == ["d2", "d1"]
    assert ranked[0][1] == pytest.approx(0.233116, abs=1e-6)
    assert ranked[1][1] == pytest.approx(0.189503, abs=1e-6)


def test_bm25_over_an_empty_corpus_returns_nothing() -> None:
    empty = BM25({})
    assert empty.search("anything", top=5) == []
    # No documents, no average length (and no division by zero).
    assert empty.avgdl == 0.0


def test_bm25_top_cut_and_deterministic_tie_break() -> None:
    index = BM25({"b": "x", "a": "x", "c": "x"})
    assert [d for d, _ in index.search("x", top=2)] == ["a", "b"]


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        # under the limit: whitespace-collapsed only
        ("short  text\nhere", 300, "short text here"),
        # 0 = no cut (full abstracts); 1 is a real limit
        ("a full abstract", 0, "a full abstract"),
        ("abc", 1, "a"),
        # cut lands on the space after "two": kept whole
        ("one two three", 7, "one two"),
        # cut lands inside "three": the partial word is dropped
        ("one two three", 9, "one two"),
        # no boundary to fall back to: hard cut
        ("supercalifragilistic", 5, "super"),
    ],
)
def test_clip_text_cuts_on_word_boundaries(
    text: str, limit: int, expected: str
) -> None:
    assert eval_rerank.clip_text(text, limit) == expected


def make_beir_dir(root: Path) -> Path:
    data = root / "mini"
    (data / "qrels").mkdir(parents=True)
    corpus = [
        {"_id": "d1", "title": "Cats purr", "text": "Cats purr when content. " * 30},
        {
            "_id": "d2",
            "title": "Dogs bark loudly",
            "text": "Dogs bark loudly at night.",
        },
        # Non-ASCII on purpose, on a document q1 retrieves: the emitted JSONL must stay
        # ASCII (\\uXXXX escapes) and the CLI test checks the bytes.
        {
            "_id": "d3",
            "title": "Birds sing \u2014 cats listen",
            "text": "Birds sing at dawn, cats listen.",
        },
    ]
    queries = [
        {"_id": "q1", "text": "why do cats purr"},
        {"_id": "q2", "text": "dogs barking"},
        {"_id": "q3", "text": "no judgements for this one"},
        {"_id": "q4", "text": "birds"},
    ]
    write_jsonl(data / "corpus.jsonl", corpus)
    write_jsonl(data / "queries.jsonl", queries)
    # q2 has two judgements with different grades (ideal must come out descending). q5 is
    # judged but only with grade 0 (nothing relevant exists for it); q9 is judged but has no
    # query text. All are real BEIR shapes (TREC-COVID has explicit 0s); q5/q9 must be
    # skipped, not crash or emit a row with an empty ideal.
    (data / "qrels" / "test.tsv").write_text(
        "query-id\tcorpus-id\tscore\n"
        "q1\td1\t1\nq2\td3\t1\nq2\td2\t2\nq4\td2\t1\nq5\td1\t0\nq9\td1\t1\n",
        encoding="utf-8",
    )
    return data


def test_load_beir_reads_corpus_queries_and_graded_qrels(tmp_path: Path) -> None:
    corpus, queries, qrels = load_beir(str(make_beir_dir(tmp_path)), split="test")
    assert corpus["d3"] == (
        "Birds sing \u2014 cats listen",
        "Birds sing at dawn, cats listen.",
    )
    assert queries["q3"] == "no judgements for this one"
    assert qrels == {
        "q1": {"d1": 1},
        "q2": {"d3": 1, "d2": 2},
        "q4": {"d2": 1},
        "q5": {"d1": 0},
        "q9": {"d1": 1},
    }


def test_build_beir_jsonl_emits_bm25_top_n_with_rel_and_ideal_grades(
    tmp_path: Path,
) -> None:
    corpus, queries, qrels = load_beir(str(make_beir_dir(tmp_path)))
    rows = build_beir_jsonl(
        corpus, queries, qrels, top=2, snippet_chars=40, url_prefix="beir://mini/"
    )
    # Only judged queries with a positive grade AND a query text, in sorted qid order: q3 has
    # no qrels, q5 has only a grade-0 judgement, q9 has no query text -> all three skipped.
    assert [r["qid"] for r in rows] == ["q1", "q2", "q4"]
    first = rows[0]
    assert first["query"] == "why do cats purr"
    assert first["ideal_rels"] == [1]
    assert [c["url"] for c in first["candidates"]] == [
        "beir://mini/d1",
        "beir://mini/d3",
    ]
    assert [c["rel"] for c in first["candidates"]] == [1, 0]
    assert first["candidates"][0]["title"] == "Cats purr"
    assert len(first["candidates"][0]["snippet"]) <= 40
    # Cut on a word boundary and rstripped.
    assert first["candidates"][0]["snippet"] == "Cats purr when content. Cats purr when"
    # q2: two judgements -> ideal grades descending, whatever order the qrels file had.
    assert rows[1]["ideal_rels"] == [2, 1]
    # q4: BM25 for "birds" retrieves d3 only; the judged d2 is a first-stage miss -> rel 0 absent.
    q4 = rows[2]
    assert [c["url"] for c in q4["candidates"]] == ["beir://mini/d3"]
    assert q4["ideal_rels"] == [1]


def test_build_beir_jsonl_only_hits_drops_first_stage_misses_and_max_queries_cuts(
    tmp_path: Path,
) -> None:
    corpus, queries, qrels = load_beir(str(make_beir_dir(tmp_path)))
    rows = build_beir_jsonl(
        corpus, queries, qrels, top=2, snippet_chars=40, only_hits=True
    )
    assert [r["qid"] for r in rows] == ["q1", "q2"]
    rows = build_beir_jsonl(
        corpus, queries, qrels, top=2, snippet_chars=40, max_queries=1
    )
    assert [r["qid"] for r in rows] == ["q1"]
    assert rows[0]["candidates"][0]["url"] == "beir://scifact/d1"  # default prefix


def zip_beir_dir(data: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w") as zf:
        for file in data.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=str(Path(data.name) / file.relative_to(data)))


def test_fetch_beir_downloads_the_zip_once_and_extracts_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = make_beir_dir(tmp_path / "src")
    zip_bytes = tmp_path / "mini.zip"
    zip_beir_dir(src, zip_bytes)
    workdir = tmp_path / "work"
    calls: list[tuple[str, int]] = []

    def fake_urlopen(url: str, timeout: int) -> io.BytesIO:
        calls.append((url, timeout))
        return io.BytesIO(zip_bytes.read_bytes())

    monkeypatch.setattr(eval_rerank, "urlopen", fake_urlopen)
    root = eval_rerank.fetch_beir(
        "mini", str(workdir), zip_url="https://example.test/mini.zip"
    )
    assert root == os.path.join(str(workdir), "mini")
    assert (workdir / "mini" / "corpus.jsonl").is_file()
    # A 2.8 MB zip from a university mirror: a bounded timeout, and a generous one.
    assert calls == [("https://example.test/mini.zip", 300)]
    # Second call: zip present, directory present -> no download, no re-extract.
    eval_rerank.fetch_beir(
        "mini", str(workdir), zip_url="https://example.test/mini.zip"
    )
    assert len(calls) == 1


def test_fetch_beir_extracts_a_pre_placed_zip_without_downloading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    src = make_beir_dir(tmp_path / "src")
    workdir = tmp_path / "work"
    workdir.mkdir()
    zip_beir_dir(src, workdir / "mini.zip")
    # Any download attempt would TypeError.
    monkeypatch.setattr(eval_rerank, "urlopen", None)
    root = eval_rerank.fetch_beir("mini", str(workdir))
    assert (Path(root) / "queries.jsonl").is_file()


def test_default_beir_zip_url_points_at_the_ukp_mirror() -> None:
    assert eval_rerank.beir_zip_url("scifact").startswith(
        "https://public.ukp.informatik.tu-darmstadt.de/"
    )
    assert eval_rerank.beir_zip_url("scifact").endswith("/scifact.zip")


# --------------------------------------------------------------------------
# eval_rerank: CLI
# --------------------------------------------------------------------------


def test_cli_run_writes_results_json_and_markdown_with_the_given_date(
    tmp_path: Path, onnx_world: FakeOnnxWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    eval_set = write_jsonl(tmp_path / "smoke.jsonl", SMOKE_ROWS)
    out_dir = tmp_path / "out"
    code = eval_rerank.main(
        [
            "run",
            str(eval_set),
            "--backend",
            "onnx,none",
            "--out-dir",
            str(out_dir),
            "--date",
            "2026-09-02",
            "--top-k",
            "3",
        ]
    )
    assert code == 0
    raw = (out_dir / "results-2026-09-02.json").read_text(encoding="utf-8")
    # indent=2 with a trailing newline: the committed results files are written this way,
    # so a re-run diffs clean against them instead of rewriting every line.
    assert raw.splitlines()[1].startswith('  "') and raw.endswith("}\n")
    payload = json.loads(raw)
    assert payload["eval_set"] == str(eval_set)
    assert payload["n_queries"] == 3 and payload["top_k"] == 3
    assert payload["backends"]["onnx"]["available"] is True
    assert payload["backends"]["onnx"]["model"] == DEFAULT_MODEL
    assert payload["backends"]["none"]["available"] is False
    assert "backend 'none'" in payload["backends"]["none"]["reason"]
    assert payload["date"] == "2026-09-02"
    markdown = (out_dir / "results-2026-09-02.md").read_text(encoding="utf-8")
    assert "| onnx |" in markdown
    assert markdown == capsys.readouterr().out


def test_cli_run_defaults_to_today_auto_backend_and_default_top_k(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eval_set = write_jsonl(tmp_path / "smoke.jsonl", SMOKE_ROWS)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(eval_rerank, "today", lambda: "2031-01-01")
    assert eval_rerank.main(["run", str(eval_set)]) == 0
    payload = json.loads(
        (tmp_path / "eval" / "results-2031-01-01.json").read_text(encoding="utf-8")
    )
    assert list(payload["backends"]) == ["auto"]
    assert payload["backends"]["auto"]["available"] is False  # nothing installed here
    assert payload["top_k"] == DEFAULT_TOP_K


def test_cli_run_label_suffixes_the_result_files(tmp_path: Path) -> None:
    eval_set = write_jsonl(tmp_path / "smoke.jsonl", SMOKE_ROWS)
    code = eval_rerank.main(
        [
            "run",
            str(eval_set),
            "--out-dir",
            str(tmp_path),
            "--date",
            "2026-09-02",
            "--label",
            "full",
        ]
    )
    assert code == 0
    assert (tmp_path / "results-2026-09-02-full.json").is_file()
    assert (tmp_path / "results-2026-09-02-full.md").is_file()


def test_today_is_an_iso_utc_date() -> None:
    value = eval_rerank.today()
    assert len(value) == 10 and value[4] == "-" and value[7] == "-"


def test_cli_build_beir_writes_the_jsonl_from_a_local_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src = make_beir_dir(tmp_path / "src")
    workdir = tmp_path / "work"
    workdir.mkdir()
    zip_beir_dir(src, workdir / "mini.zip")
    monkeypatch.setattr(eval_rerank, "urlopen", None)
    # The committed set is gzipped; the CLI does it by extension.
    out = tmp_path / "mini.jsonl.gz"
    code = eval_rerank.main(
        [
            "build-beir",
            "--dataset",
            "mini",
            "--workdir",
            str(workdir),
            "--out",
            str(out),
            "--top",
            "2",
            "--snippet-chars",
            "40",
            "--only-hits",
            "--max-queries",
            "1",
        ]
    )
    assert code == 0
    text = gzip.decompress(out.read_bytes()).decode("utf-8")
    rows = [json.loads(line) for line in text.splitlines()]
    assert [r["qid"] for r in rows] == ["q1"]
    assert rows[0]["candidates"][0]["url"] == "beir://mini/d1"
    # The committed set is ASCII on disk (non-ASCII escaped, here d2's em dash), so it is
    # greppable and diffable in any locale; the escape round-trips through json.loads.
    assert text.isascii() and "\\u2014" in text
    assert any("\u2014" in c["title"] for c in rows[0]["candidates"])
    assert "1 queries" in capsys.readouterr().out
    # ...and `run` reads it straight back.
    assert (
        eval_rerank.main(
            ["run", str(out), "--backend", "none", "--out-dir", str(tmp_path)]
        )
        == 0
    )
    assert "1 queries" in capsys.readouterr().out


def test_cli_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit) as excinfo:
        eval_rerank.main([])
    assert excinfo.value.code == 2


def test_cli_build_beir_requires_out(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without --out argparse exits before fetch_beir could touch the network.
    monkeypatch.setattr(eval_rerank, "urlopen", None)
    with pytest.raises(SystemExit) as excinfo:
        eval_rerank.main(["build-beir"])
    assert excinfo.value.code == 2


def test_cli_defaults_match_the_committed_recipe_and_the_stage_defaults() -> None:
    # eval/README.md documents the committed set as "SciFact test split, BM25 top-30,
    # 300-char snippets, under /tmp/beir"; these defaults ARE that recipe.
    build = eval_rerank._build_parser().parse_args(["build-beir", "--out", "x.jsonl"])
    assert (build.dataset, build.split, build.workdir) == (
        "scifact",
        "test",
        os.path.join("/tmp", "beir"),
    )
    assert (build.top, build.snippet_chars) == (30, 300)
    assert build.max_queries is None and build.only_hits is False
    assert build.zip_url is None
    run = eval_rerank._build_parser().parse_args(["run", "set.jsonl"])
    assert (run.backend, run.top_k, run.model) == ("auto", DEFAULT_TOP_K, DEFAULT_MODEL)
    assert (run.out_dir, run.date, run.label) == ("eval", None, None)
