"""Optional cross-encoder rerank stage over a fused ranking — DEFAULT OFF, identity when it
cannot run, and it always says why.

WHAT IT DOES
------------
RRF (``rank_fusion``) orders documents by cross-provider *agreement*; it never reads the
text. A cross-encoder reads ``query`` and ``title + " " + snippet`` together and emits one
relevance logit per pair — the strongest cheap signal a search stack can add after fusion,
and the one the plan gates behind an eval (``docs/plans/2026-09-02-search-research-tools-
gemhunt.md``, inventory C). Only the top ``top_k`` (default 30) fused results are rescored;
the tail keeps its RRF order, so the cost is bounded regardless of how many results fused.

WHAT IT REFUSES TO DO
---------------------
* **Run by default.** ``enabled=None`` reads ``RERANK_ENABLED``; anything but a truthy
  spelling (``1``/``true``/``yes``/``on``) is off, and the stage returns the input unchanged
  with ``reranked=False`` and a ``reason``.
* **Import at module load.** ``onnxruntime``/``tokenizers``/``numpy``, ``fastembed`` and
  ``flashrank`` are all optional and imported lazily inside the loader that needs them. With
  none installed this module is pure stdlib and the stage is an identity pass that reports
  ``reranked: false`` and which backends were missing.
* **Download inside a search.** The model (~23 MB int8) is looked up under
  ``RERANK_MODEL_DIR``; it is fetched only when ``RERANK_ALLOW_DOWNLOAD=1`` (or
  ``allow_download=True``). An absent model is identity + reason, never a surprise network
  call in the middle of a query.
* **Take the search down.** Any exception while scoring degrades to identity with the
  error in ``reason``. A reranker that can fail a query is worse than none.
* **Mutate ``FusedResult``.** It is frozen and shared; the model scores travel in a
  parallel ``scores`` tuple on :class:`RerankResult`.

BACKENDS (``backend="auto"`` tries them in this order)
------------------------------------------------------
``onnx``      bare ``onnxruntime`` + ``tokenizers`` over the HF export
              ``Xenova/ms-marco-MiniLM-L-6-v2`` (``onnx/model_quantized.onnx`` +
              ``tokenizer.json``). Smallest footprint; what the eval measured.
``fastembed`` ``fastembed.rerank.cross_encoder.TextCrossEncoder`` (same model name, its own
              cache layout, ``local_files_only`` unless downloads are allowed).
``flashrank`` ``flashrank.Ranker``. It ships no L-6 build, so the default model maps to
              ``ms-marco-MiniLM-L-12-v2`` and :attr:`RerankResult.model` reports the
              substitute, not the requested name.
``none``      explicit identity.

Text fed to the model is ``title + " " + snippet`` (whitespace-collapsed). The tokenizer is
asked to truncate the *pair* to :data:`MAX_TOKENS` = 512 (longest-first, i.e. the passage
loses tokens before the short query does) — the BERT position budget of MiniLM. With RRF's
500-char snippet cap that limit is rarely reached; a full-page ``snippet`` from a caller
that bypassed ``rank_fusion`` is cut, not rejected. Items with neither title nor snippet
have nothing to score: they are skipped (score ``None``) and follow the rescored head in
their original order, and ``skipped`` counts them.

Measured basis: the 2026-09-02 eval in ``eval/`` (BEIR SciFact test queries, stdlib BM25
first stage, 300-char snippets vs full abstracts) — see the README section "Rerank stage".
"""

from __future__ import annotations

import importlib
import os
import shutil
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Sequence
from urllib.request import urlopen

from rank_fusion import FusedResult

__all__ = [
    "BACKENDS",
    "BATCH_SIZE",
    "DEFAULT_MODEL",
    "DEFAULT_TOP_K",
    "ENV_ALLOW_DOWNLOAD",
    "ENV_ENABLED",
    "ENV_MODEL_DIR",
    "MAX_TOKENS",
    "BackendUnavailable",
    "LoadedBackend",
    "RerankResult",
    "load_backend",
    "rerank",
    "reset_backend_cache",
    "resolve_model_dir",
    "scoring_text",
]

#: The HF export the eval measured: MS MARCO cross-encoder, 6 layers, int8 ONNX (~23 MB).
DEFAULT_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
#: How many fused results are rescored; the tail keeps its RRF order.
DEFAULT_TOP_K = 30
#: BERT/MiniLM position budget for the (query, passage) pair, enforced by the tokenizer.
MAX_TOKENS = 512
#: Pairs per ONNX session run. Bounds memory; 30 results is two runs.
BATCH_SIZE = 16
BACKENDS = ("auto", "onnx", "fastembed", "flashrank", "none")
ENV_ENABLED = "RERANK_ENABLED"
ENV_MODEL_DIR = "RERANK_MODEL_DIR"
ENV_ALLOW_DOWNLOAD = "RERANK_ALLOW_DOWNLOAD"

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_AUTO_ORDER = ("onnx", "fastembed", "flashrank")
_HF_FILES = ("onnx/model_quantized.onnx", "tokenizer.json")
_ONNX_MODEL_LAYOUTS = (
    "onnx/model_quantized.onnx",
    "model_quantized.onnx",
    "onnx/model.onnx",
    "model.onnx",
)
#: ONNX input name -> ``tokenizers.Encoding`` attribute that fills it.
_ONNX_INPUTS = {
    "input_ids": "ids",
    "attention_mask": "attention_mask",
    "token_type_ids": "type_ids",
}
#: flashrank has no L-6 build of this cross-encoder; the 12-layer sibling is the substitute.
_FLASHRANK_MODELS = {DEFAULT_MODEL: "ms-marco-MiniLM-L-12-v2"}

Scorer = Callable[[str, Sequence[str]], Sequence[float]]


class BackendUnavailable(RuntimeError):
    """A backend cannot produce a scorer; ``str(exc)`` is the reason the caller reports."""


@dataclass(frozen=True)
class LoadedBackend:
    """A ready scorer plus the names to report for it."""

    name: str
    """Backend that loaded: ``onnx`` / ``fastembed`` / ``flashrank``."""

    model: str
    """Model actually in use (flashrank may substitute; see :data:`_FLASHRANK_MODELS`)."""

    score: Scorer
    """``(query, texts) -> one float per text``, higher = more relevant."""


@dataclass(frozen=True)
class RerankResult:
    """The re-ordered ranking plus everything needed to trust (or distrust) it."""

    results: tuple[FusedResult, ...]
    """Rescored head (best model score first) then skipped head items then the tail."""

    scores: tuple[float | None, ...]
    """Parallel to ``results``: the model logit, or ``None`` for skipped/tail items."""

    reranked: bool
    """``True`` only when a model scored at least one item and the order is its order."""

    backend: str
    """Backend used, or ``"none"`` when nothing ran."""

    model: str
    """Model used (or requested, when nothing ran)."""

    latency_ms: float
    """Wall time of the call; the first call per process includes loading the model."""

    reason: str
    """Why the stage did not rerank; ``""`` when it did."""

    top_k: int
    rescored: int = 0
    skipped: int = 0

    def pairs(self) -> tuple[tuple[FusedResult, float | None], ...]:
        """``(result, score)`` tuples in ranked order."""
        return tuple(zip(self.results, self.scores))


_CACHE: dict[tuple[str, str, str], LoadedBackend] = {}


def reset_backend_cache() -> None:
    """Drop every loaded backend (tests; or after installing a package in-process)."""
    _CACHE.clear()


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def resolve_model_dir(explicit: str | None = None) -> str:
    """Resolve the model directory: argument, else ``RERANK_MODEL_DIR``, else the user cache."""
    if explicit is not None:
        return explicit
    from_env = os.environ.get(ENV_MODEL_DIR)
    if from_env:
        return from_env
    return os.path.join(os.path.expanduser("~"), ".cache", "search-expansion", "rerank")


def scoring_text(result: FusedResult) -> str:
    """``title + " " + snippet``, whitespace-collapsed; ``""`` when there is nothing to score."""
    return " ".join(f"{result.title} {result.snippet}".split())


def _import(name: str, backend: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise BackendUnavailable(
            f"{backend}: {name.split('.')[0]} not installed"
        ) from exc


# --------------------------------------------------------------------------
# onnx backend
# --------------------------------------------------------------------------


def _find_onnx_files(root: str) -> tuple[str, str] | None:
    tokenizer = os.path.join(root, "tokenizer.json")
    if not os.path.isfile(tokenizer):
        return None
    for layout in _ONNX_MODEL_LAYOUTS:
        candidate = os.path.join(root, *layout.split("/"))
        if os.path.isfile(candidate):
            return candidate, tokenizer
    return None


def _download_onnx_files(model: str, root: str) -> None:
    """Fetch the two hub files into ``root``, mirroring the repo layout; atomic per file."""
    for rel in _HF_FILES:
        url = f"https://huggingface.co/{model}/resolve/main/{rel}"
        dest = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            with (
                urlopen(url, timeout=120) as response,
                open(f"{dest}.part", "wb") as out,
            ):
                shutil.copyfileobj(response, out)
        except (OSError, ValueError) as exc:
            raise BackendUnavailable(f"onnx: download of {url} failed: {exc}") from exc
        os.replace(f"{dest}.part", dest)


def _load_onnx(model: str, directory: str, allow_download: bool) -> LoadedBackend:
    ort = _import("onnxruntime", "onnx")
    tokenizers = _import("tokenizers", "onnx")
    np = _import("numpy", "onnx")

    root = os.path.join(directory, *model.split("/"))
    files = _find_onnx_files(root)
    if files is None and allow_download:
        _download_onnx_files(model, root)
        files = _find_onnx_files(root)
    if files is None:
        raise BackendUnavailable(
            f"onnx: model files for {model} not found under {directory} "
            f"(expected tokenizer.json + onnx/model_quantized.onnx; set {ENV_ALLOW_DOWNLOAD}=1 "
            "to fetch them once)"
        )
    model_path, tokenizer_path = files

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_names = [node.name for node in session.get_inputs()]
    for name in input_names:
        if name not in _ONNX_INPUTS:
            raise BackendUnavailable(f"onnx: model declares unsupported input {name!r}")
    tokenizer = tokenizers.Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(MAX_TOKENS)
    tokenizer.enable_padding()

    def score(query: str, texts: Sequence[str]) -> list[float]:
        out: list[float] = []
        for start in range(0, len(texts), BATCH_SIZE):
            encodings = tokenizer.encode_batch(
                [(query, text) for text in texts[start : start + BATCH_SIZE]]
            )
            feeds = {
                name: np.array(
                    [getattr(enc, _ONNX_INPUTS[name]) for enc in encodings],
                    dtype=np.int64,
                )
                for name in input_names
            }
            logits = session.run(None, feeds)[0]
            out.extend(float(row[0]) for row in logits)
        return out

    return LoadedBackend(name="onnx", model=model, score=score)


# --------------------------------------------------------------------------
# fastembed backend
# --------------------------------------------------------------------------


def _load_fastembed(model: str, directory: str, allow_download: bool) -> LoadedBackend:
    module = _import("fastembed.rerank.cross_encoder", "fastembed")
    try:
        encoder = module.TextCrossEncoder(
            model_name=model, cache_dir=directory, local_files_only=not allow_download
        )
    except (
        Exception
    ) as exc:  # third-party constructor: ValueError, OSError, its own types
        raise BackendUnavailable(f"fastembed: could not load {model}: {exc}") from exc

    def score(query: str, texts: Sequence[str]) -> list[float]:
        return [float(value) for value in encoder.rerank(query, list(texts))]

    return LoadedBackend(name="fastembed", model=model, score=score)


# --------------------------------------------------------------------------
# flashrank backend
# --------------------------------------------------------------------------


def _load_flashrank(model: str, directory: str, allow_download: bool) -> LoadedBackend:
    module = _import("flashrank", "flashrank")
    name = _FLASHRANK_MODELS.get(model, model)
    # flashrank downloads inside Ranker() whenever <cache_dir>/<model> is absent, so the
    # download gate has to be enforced here, before the constructor runs.
    if not allow_download and not os.path.isdir(os.path.join(directory, name)):
        raise BackendUnavailable(
            f"flashrank: model {name!r} not found under {directory} "
            f"(set {ENV_ALLOW_DOWNLOAD}=1 to fetch it once)"
        )
    try:
        ranker = module.Ranker(model_name=name, cache_dir=directory)
    except Exception as exc:  # third-party constructor
        raise BackendUnavailable(f"flashrank: could not load {name}: {exc}") from exc

    def score(query: str, texts: Sequence[str]) -> list[float]:
        request = module.RerankRequest(
            query=query,
            passages=[{"id": i, "text": text} for i, text in enumerate(texts)],
        )
        # flashrank returns the passages best-first; map back by id. A passage it dropped
        # raises KeyError here, which rerank() turns into identity + reason.
        by_id = {int(p["id"]): float(p["score"]) for p in ranker.rerank(request)}
        return [by_id[i] for i in range(len(texts))]

    return LoadedBackend(name="flashrank", model=name, score=score)


_LOADERS: dict[str, Callable[[str, str, bool], LoadedBackend]] = {
    "onnx": _load_onnx,
    "fastembed": _load_fastembed,
    "flashrank": _load_flashrank,
}
_LOADABLE = ("auto",) + _AUTO_ORDER


def load_backend(
    backend: str,
    model: str,
    *,
    model_dir: str | None = None,
    allow_download: bool | None = None,
) -> LoadedBackend:
    """Load (or fetch from the process cache) a scorer for ``backend``.

    ``"auto"`` probes ``onnx``, ``fastembed``, ``flashrank`` in that order and returns the
    first that loads. Raises :class:`BackendUnavailable` whose message concatenates every
    candidate's reason when none does; raises ``ValueError`` for ``"none"`` or an unknown
    name (those are ``rerank()``'s to handle, not a loader's).
    """
    if backend not in _LOADABLE:
        raise ValueError(f"backend must be one of {_LOADABLE}, got {backend!r}")
    directory = resolve_model_dir(model_dir)
    download = (
        _env_flag(ENV_ALLOW_DOWNLOAD) if allow_download is None else allow_download
    )
    candidates = _AUTO_ORDER if backend == "auto" else (backend,)
    reasons: list[str] = []
    for name in candidates:
        key = (name, model, directory)
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
        try:
            loaded = _LOADERS[name](model, directory, download)
        except BackendUnavailable as exc:
            reasons.append(str(exc))
            continue
        _CACHE[key] = loaded
        return loaded
    if len(reasons) == 1:
        raise BackendUnavailable(reasons[0])
    raise BackendUnavailable("no rerank backend available: " + "; ".join(reasons))


def rerank(
    fused: Sequence[FusedResult],
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    model: str = DEFAULT_MODEL,
    backend: str = "auto",
    enabled: bool | None = None,
    model_dir: str | None = None,
    allow_download: bool | None = None,
) -> RerankResult:
    """Rescore the top ``top_k`` of ``fused`` with a cross-encoder; identity when it cannot.

    Never raises for a runtime condition (missing package, missing model, backend error):
    those all return the input order with ``reranked=False`` and a ``reason``. Only caller
    mistakes raise: ``top_k < 1`` or a ``backend`` outside :data:`BACKENDS`.

    Ordering when it does run: head items the model scored, best first (ties keep RRF
    order); then head items with no title and no snippet, in RRF order; then the tail
    beyond ``top_k``, untouched.
    """
    started = perf_counter()
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1, got {top_k}")
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}, got {backend!r}")
    results = tuple(fused)

    def identity(
        reason: str, used: str = "none", used_model: str = model
    ) -> RerankResult:
        return RerankResult(
            results=results,
            scores=(None,) * len(results),
            reranked=False,
            backend=used,
            model=used_model,
            latency_ms=(perf_counter() - started) * 1000.0,
            reason=reason,
            top_k=top_k,
        )

    if enabled is None:
        if not _env_flag(ENV_ENABLED):
            return identity(
                f"disabled: {ENV_ENABLED} is not set to 1 (default off; set it or pass enabled=True)"
            )
    elif not enabled:
        return identity("disabled: enabled=False passed by the caller")
    if backend == "none":
        return identity("backend 'none' requested: explicit identity pass")
    if not results:
        return identity("nothing to rerank: empty input")
    if not query.strip():
        return identity("nothing to rerank: empty query")

    try:
        loaded = load_backend(
            backend, model, model_dir=model_dir, allow_download=allow_download
        )
    except BackendUnavailable as exc:
        return identity(str(exc))

    head, tail = results[:top_k], results[top_k:]
    texts = [scoring_text(result) for result in head]
    scorable = [i for i, text in enumerate(texts) if text]
    if not scorable:
        return identity(
            f"no title or snippet to score in the top {len(head)}",
            loaded.name,
            loaded.model,
        )

    try:
        raw = list(loaded.score(query, [texts[i] for i in scorable]))
        if len(raw) != len(scorable):
            raise RuntimeError(
                f"backend returned {len(raw)} scores for {len(scorable)} texts"
            )
    except Exception as exc:  # a reranker must never fail the search it decorates
        return identity(
            f"{loaded.name} scoring failed: {exc}", loaded.name, loaded.model
        )

    scored = {i: float(value) for i, value in zip(scorable, raw)}
    order = sorted(scored, key=lambda i: (-scored[i], i))
    order += [i for i in range(len(head)) if i not in scored]
    return RerankResult(
        results=tuple(head[i] for i in order) + tail,
        scores=tuple(scored.get(i) for i in order) + (None,) * len(tail),
        reranked=True,
        backend=loaded.name,
        model=loaded.model,
        latency_ms=(perf_counter() - started) * 1000.0,
        reason="",
        top_k=top_k,
        rescored=len(scorable),
        skipped=len(head) - len(scorable),
    )
