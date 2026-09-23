"""Eval harness for the rerank stage: does the cross-encoder LIFT a fused ranking, measured.

The plan (``docs/plans/2026-09-02-search-research-tools-gemhunt.md``, inventory C / Wave 2)
admits the ONNX MiniLM rerank only "gated behind a 30-50 query eval; ships only if it
lifts". This module is that gate. It reads a JSONL eval set, scores the INPUT order and the
RERANKED order with nDCG@10 and recall@5 per backend, and writes ``results-<date>.json`` +
a markdown summary that ends in the decision rule's verdict.

Eval-set line shape (one query per line)::

    {"qid": "q1", "query": "...", "ideal_rels": [1, 1],
     "candidates": [{"url": "...", "title": "...", "snippet": "...", "rel": 0|1|2}, ...]}

``candidates`` are in first-stage order (what RRF would hand the reranker). ``rel`` is the
graded judgement (0 = not relevant). ``ideal_rels`` is optional: the grades of EVERY judged
relevant document for the query, so nDCG's ideal and recall's denominator come from the
qrels rather than from the candidate pool — that is what makes the absolute numbers
comparable to BEIR's (pool-relative nDCG would flatter a first stage that missed things).
Queries with no relevant document anywhere (no positive ``rel`` and no positive
``ideal_rels``) have undefined metrics and are excluded from the means; ``n_scored`` says
how many remained.

``build-beir`` turns a BEIR dataset (SciFact by default: 5,183 abstracts, 300 test claims)
into that JSONL using a stdlib BM25 as the first stage. That is a stand-in: the estate's
SearXNG cannot be reached from the cloud VM that ran the eval, and a reranker eval needs a
fixed candidate pool anyway. Documents are truncated to ``--snippet-chars`` (300 by default)
so the committed set looks like SERP snippets, which is the input the stage will actually
see; ``--snippet-chars 0`` keeps full abstracts for an upper-bound run.

Everything here that computes is a pure function; the two I/O edges are :func:`fetch_beir`
(download + unzip under a work dir, never inside the repo) and :func:`main` (files + stdout).
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
import shutil
import statistics
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import IO, Any, Callable, Mapping, Sequence
from urllib.request import urlopen

from rank_fusion import DEFAULT_K, FusedResult
from rerank import DEFAULT_MODEL, DEFAULT_TOP_K, RerankResult, rerank

__all__ = [
    "BM25",
    "DECISION_RULE",
    "LIFT_THRESHOLD",
    "Candidate",
    "EvalQuery",
    "beir_zip_url",
    "build_beir_jsonl",
    "candidates_to_fused",
    "clip_text",
    "evaluate",
    "fetch_beir",
    "load_beir",
    "load_eval_set",
    "main",
    "ndcg_at_k",
    "recall_at_k",
    "summarize_markdown",
    "today",
]

#: The plan's bar: switch the stage on only if nDCG@10 improves by at least this much.
LIFT_THRESHOLD = 0.02
DECISION_RULE = (
    "RERANK_ENABLED=1 only if nDCG@10 lift >= +0.02 on the eval set; otherwise leave off "
    "(plan doc 2026-09-02-search-research-tools-gemhunt.md, Wave 2)"
)
_BEIR_BASE = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"
_TOKEN_RE = re.compile(r"[a-z0-9]+")

RerankFn = Callable[..., RerankResult]


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    snippet: str
    rel: int


@dataclass(frozen=True)
class EvalQuery:
    qid: str
    query: str
    candidates: tuple[Candidate, ...]
    ideal_rels: tuple[int, ...] | None = None


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------


def _dcg(grades: Sequence[float], k: int) -> float:
    return sum(grade / math.log2(i + 2) for i, grade in enumerate(grades[:k]))


def ndcg_at_k(
    rels: Sequence[int], k: int = 10, ideal: Sequence[int] | None = None
) -> float | None:
    """nDCG@k over graded relevance in ranked order (log2 discount, gain = grade).

    The ideal ranking is ``ideal`` sorted descending when given (qrels-based, BEIR's
    convention), else the candidate pool's own grades. ``None`` when the ideal DCG is zero,
    i.e. nothing relevant exists to rank.
    """
    ideal_grades = sorted(rels if ideal is None else ideal, reverse=True)
    idcg = _dcg(ideal_grades, k)
    if idcg <= 0:
        return None
    return _dcg(rels, k) / idcg


def recall_at_k(
    rels: Sequence[int], k: int = 5, total_relevant: int | None = None
) -> float | None:
    """Share of relevant documents (grade > 0) found in the top ``k``.

    Denominator is ``total_relevant`` when given (all judged relevant docs, BEIR's
    convention), else the relevant count in the pool. ``None`` when that is zero.
    """
    total = sum(1 for g in rels if g > 0) if total_relevant is None else total_relevant
    if total <= 0:
        return None
    return sum(1 for g in rels[:k] if g > 0) / total


# --------------------------------------------------------------------------
# eval set I/O + adaptation to the rerank stage's input type
# --------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_row(
    row: Any,
) -> tuple[str | None, str, tuple[Candidate, ...], tuple[int, ...] | None]:
    if not isinstance(row, dict):
        raise ValueError("expected a JSON object")
    query = row.get("query")
    if not isinstance(query, str):
        raise ValueError("missing or non-string 'query'")
    raw_candidates = row.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("'candidates' must be a list")
    candidates: list[Candidate] = []
    for i, cand in enumerate(raw_candidates, start=1):
        if not isinstance(cand, dict):
            raise ValueError(f"candidate {i}: expected an object")
        url = cand.get("url")
        if not isinstance(url, str):
            raise ValueError(f"candidate {i}: missing or non-string 'url'")
        rel = cand.get("rel")
        if not _is_int(rel):
            raise ValueError(f"candidate {i}: 'rel' must be an integer")
        title = str(cand.get("title") or "")
        snippet = str(cand.get("snippet") or "")
        candidates.append(Candidate(url, title, snippet, rel))
    ideal: tuple[int, ...] | None = None
    if "ideal_rels" in row:
        raw_ideal = row["ideal_rels"]
        if not isinstance(raw_ideal, list) or not all(_is_int(g) for g in raw_ideal):
            raise ValueError("'ideal_rels' must be a list of integers")
        ideal = tuple(raw_ideal)
    qid = row.get("qid")
    return (None if qid is None else str(qid)), query, tuple(candidates), ideal


def _open_text(path: str) -> IO[str]:
    """Read handle for ``path``; ``*.gz`` is gunzipped on the fly (the committed set is one)."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _write_text(path: str, text: str) -> None:
    """Write ``text`` to ``path``; ``*.gz`` is gzipped with ``mtime=0`` and no embedded name,
    so identical rows give identical bytes and a rebuilt committed set diffs clean."""
    if path.endswith(".gz"):
        with open(path, "wb") as handle:
            handle.write(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def load_eval_set(path: str) -> list[EvalQuery]:
    """Read a JSONL (or ``.jsonl.gz``) eval set; blank lines are skipped; a bad line raises
    with its number."""
    queries: list[EvalQuery] = []
    with _open_text(path) as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                qid, query, candidates, ideal = _parse_row(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path} line {number}: {exc}") from exc
            queries.append(EvalQuery(qid or str(number), query, candidates, ideal))
    return queries


def candidates_to_fused(candidates: Sequence[Candidate]) -> list[FusedResult]:
    """Dress candidates as a one-provider fused ranking (descending RRF-shaped scores)."""
    return [
        FusedResult(
            url=cand.url,
            display_url=cand.url,
            title=cand.title,
            score=1.0 / (DEFAULT_K + rank),
            sources=("eval",),
            ranks=MappingProxyType({"eval": rank}),
            snippet=cand.snippet,
        )
        for rank, cand in enumerate(candidates, start=1)
    ]


# --------------------------------------------------------------------------
# evaluate
# --------------------------------------------------------------------------


def _metrics(
    query: EvalQuery, order: Sequence[FusedResult]
) -> tuple[float, float] | None:
    """(nDCG@10, recall@5) of ``order`` for ``query``; ``None`` when undefined."""
    rel_by_url = {cand.url: cand.rel for cand in query.candidates}
    grades = [rel_by_url[result.url] for result in order]
    ideal = query.ideal_rels
    total = None if ideal is None else sum(1 for g in ideal if g > 0)
    ndcg = ndcg_at_k(grades, 10, ideal=ideal)
    recall = recall_at_k(grades, 5, total_relevant=total)
    if ndcg is None or recall is None:
        return None
    return ndcg, recall


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _recommendation(available: bool, lift: float | None) -> str:
    if not available:
        return "leave off (backend unavailable, nothing measured)"
    if lift is None:
        return "leave off (no query with a judged relevant document)"
    if lift >= LIFT_THRESHOLD:
        return f"RERANK_ENABLED=1 (nDCG@10 lift {lift:+.4f} >= +{LIFT_THRESHOLD:.2f} on this set)"
    return f"leave off (nDCG@10 lift {lift:+.4f} < +{LIFT_THRESHOLD:.2f})"


def _evaluate_backend(
    queries: Sequence[EvalQuery],
    baseline: Sequence[tuple[float, float] | None],
    backend: str,
    *,
    top_k: int,
    model: str,
    rerank_fn: RerankFn,
    baseline_means: Mapping[str, float | None],
) -> dict[str, Any]:
    outcomes = [
        rerank_fn(
            candidates_to_fused(query.candidates),
            query.query,
            backend=backend,
            top_k=top_k,
            enabled=True,
            model=model,
        )
        for query in queries
    ]
    available = any(out.reranked for out in outcomes)
    per_query: list[list[Any]] = []
    ndcgs: list[float] = []
    recalls: list[float] = []
    improved = worsened = unchanged = 0
    for query, before, outcome in zip(queries, baseline, outcomes):
        if before is None:
            continue
        after = _metrics(query, outcome.results)
        # Same query, same judged pool: defined iff ``before`` is.
        assert after is not None
        ndcgs.append(after[0])
        recalls.append(after[1])
        per_query.append([query.qid, round(before[0], 6), round(after[0], 6)])
        delta = after[0] - before[0]
        if delta > 1e-9:
            improved += 1
        elif delta < -1e-9:
            worsened += 1
        else:
            unchanged += 1
    ndcg = _mean(ndcgs)
    recall = _mean(recalls)
    base_ndcg = baseline_means["ndcg@10"]
    base_recall = baseline_means["recall@5"]
    lift_ndcg = None if ndcg is None or base_ndcg is None else ndcg - base_ndcg
    lift_recall = (
        None if recall is None or base_recall is None else recall - base_recall
    )
    latencies = [out.latency_ms for out in outcomes]
    return {
        "available": available,
        "reason": next((out.reason for out in outcomes if out.reason), ""),
        "model": next((out.model for out in outcomes if out.reranked), model),
        "backend_used": next((out.backend for out in outcomes if out.reranked), "none"),
        "reranked_queries": sum(1 for out in outcomes if out.reranked),
        "ndcg@10": ndcg,
        "recall@5": recall,
        "lift_ndcg@10": lift_ndcg,
        "lift_recall@5": lift_recall,
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 3),
            "p50": round(statistics.median(latencies), 3),
            "max": round(max(latencies), 3),
        },
        "recommendation": _recommendation(available, lift_ndcg),
        "per_query": per_query,
    }


def evaluate(
    queries: Sequence[EvalQuery],
    *,
    backends: Sequence[str],
    top_k: int = DEFAULT_TOP_K,
    model: str = DEFAULT_MODEL,
    rerank_fn: RerankFn = rerank,
    eval_set: str = "<in-memory>",
) -> dict[str, Any]:
    """Score the input order, then each backend's reranked order; JSON-ready report.

    ``rerank_fn`` is :func:`rerank.rerank` unless injected (tests). It is always called with
    ``enabled=True``: the eval measures what the stage WOULD do, the env gate is for callers.
    """
    baseline = [
        _metrics(query, candidates_to_fused(query.candidates)) for query in queries
    ]
    scored = [pair for pair in baseline if pair is not None]
    baseline_means = {
        "ndcg@10": _mean([ndcg for ndcg, _ in scored]),
        "recall@5": _mean([recall for _, recall in scored]),
    }
    report: dict[str, Any] = {
        "eval_set": eval_set,
        "n_queries": len(queries),
        "n_scored": len(scored),
        "top_k": top_k,
        "model": model,
        "baseline": baseline_means,
        "backends": {},
        "decision_rule": DECISION_RULE,
    }
    for backend in backends:
        report["backends"][backend] = _evaluate_backend(
            queries,
            baseline,
            backend,
            top_k=top_k,
            model=model,
            rerank_fn=rerank_fn,
            baseline_means=baseline_means,
        )
    return report


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def _fmt_lift(value: float | None) -> str:
    return "-" if value is None else f"{value:+.4f}"


def summarize_markdown(report: Mapping[str, Any]) -> str:
    """Markdown table: baseline row, one row per backend, the decision rule and verdicts."""
    base = report["baseline"]
    lines = [
        f"# Rerank stage eval ({report.get('date', 'undated')})",
        "",
        f"Set: `{report['eval_set']}` - {report['n_queries']} queries "
        f"({report['n_scored']} with a judged relevant document), top_k={report['top_k']}, "
        f"requested model `{report['model']}`.",
        "",
        "| order | nDCG@10 | recall@5 | lift nDCG@10 | reranked queries | "
        "latency ms mean/p50/max | verdict |",
        "|---|---|---|---|---|---|---|",
        f"| baseline (RRF order) | {_fmt(base['ndcg@10'])} | {_fmt(base['recall@5'])} | - | - | - | - |",
    ]
    reasons: list[str] = []
    for name, entry in report["backends"].items():
        lat = entry["latency_ms"]
        lines.append(
            f"| {name} | {_fmt(entry['ndcg@10'])} | {_fmt(entry['recall@5'])} | "
            f"{_fmt_lift(entry['lift_ndcg@10'])} | "
            f"{entry['reranked_queries']}/{report['n_queries']} | "
            f"{lat['mean']}/{lat['p50']}/{lat['max']} | {entry['recommendation']} |"
        )
        if entry["reason"]:
            reasons.append(f"- `{name}`: {entry['reason']}")
    lines += ["", f"Decision rule: {report['decision_rule']}."]
    if reasons:
        lines += ["", "Reasons reported by the stage:", *reasons]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# BM25 first stage + BEIR conversion
# --------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25:
    """Okapi BM25 over an in-memory corpus; ASCII ``[a-z0-9]+`` tokens, no stemming.

    ``k1=0.9, b=0.4`` are the Anserini/BEIR defaults so the baseline is the one the
    literature reports for BM25 (SciFact nDCG@10 0.665 in the BEIR paper). Query terms are
    a set (term frequency in the query is ignored). Ties break on the document id so the
    candidate pool is reproducible byte for byte.
    """

    def __init__(
        self, docs: Mapping[str, str], *, k1: float = 0.9, b: float = 0.4
    ) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids = list(docs)
        self.doc_len: list[int] = []
        self.postings: dict[str, dict[int, int]] = {}
        for index, text in enumerate(docs.values()):
            tokens = _tokenize(text)
            self.doc_len.append(len(tokens))
            for term, tf in Counter(tokens).items():
                self.postings.setdefault(term, {})[index] = tf
        self.n_docs = len(self.doc_ids)
        self.avgdl = sum(self.doc_len) / self.n_docs if self.n_docs else 0.0

    def search(self, query: str, top: int) -> list[tuple[str, float]]:
        """Top ``top`` ``(doc_id, score)`` pairs, best first; only docs sharing a term."""
        scores: dict[int, float] = {}
        for term in set(_tokenize(query)):
            plist = self.postings.get(term)
            if not plist:
                continue
            idf = math.log(1.0 + (self.n_docs - len(plist) + 0.5) / (len(plist) + 0.5))
            for index, tf in plist.items():
                norm = 1.0 - self.b + self.b * self.doc_len[index] / self.avgdl
                scores[index] = scores.get(index, 0.0) + idf * tf * (self.k1 + 1.0) / (
                    tf + self.k1 * norm
                )
        ranked = sorted(
            scores.items(), key=lambda item: (-item[1], self.doc_ids[item[0]])
        )
        return [(self.doc_ids[index], score) for index, score in ranked[:top]]


def clip_text(text: str, limit: int) -> str:
    """Whitespace-collapse, then cut to ``limit`` chars without leaving a partial word.

    ``limit <= 0`` means no cut (full text). A cut that lands mid-word drops that word;
    the result is therefore ``<= limit`` chars and ends on a word boundary.
    """
    collapsed = " ".join(text.split())
    if limit <= 0 or len(collapsed) <= limit:
        return collapsed
    cut = collapsed[:limit]
    if not collapsed[limit].isspace():
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip()


def load_beir(
    root: str, split: str = "test"
) -> tuple[dict[str, tuple[str, str]], dict[str, str], dict[str, dict[str, int]]]:
    """Read a BEIR directory: ``corpus.jsonl``, ``queries.jsonl``, ``qrels/<split>.tsv``.

    Returns ``(corpus: id -> (title, text), queries: id -> text, qrels: qid -> {docid: grade})``.
    """
    corpus: dict[str, tuple[str, str]] = {}
    with open(os.path.join(root, "corpus.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            corpus[str(row["_id"])] = (
                str(row.get("title") or ""),
                str(row.get("text") or ""),
            )
    queries: dict[str, str] = {}
    with open(os.path.join(root, "queries.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            queries[str(row["_id"])] = str(row["text"])
    qrels: dict[str, dict[str, int]] = {}
    with open(os.path.join(root, "qrels", f"{split}.tsv"), encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "query-id":
                continue
            qid, doc_id, grade = parts[0], parts[1], int(parts[2])
            qrels.setdefault(qid, {})[doc_id] = grade
    return corpus, queries, qrels


def build_beir_jsonl(
    corpus: Mapping[str, tuple[str, str]],
    queries: Mapping[str, str],
    qrels: Mapping[str, Mapping[str, int]],
    *,
    top: int = 30,
    snippet_chars: int = 300,
    max_queries: int | None = None,
    only_hits: bool = False,
    url_prefix: str = "beir://scifact/",
) -> list[dict[str, Any]]:
    """BM25 top-``top`` per judged query -> eval-set rows (sorted by qid, deterministic).

    ``ideal_rels`` carries every positive judgement so the metrics use the qrels-based ideal;
    a judged document the first stage missed is therefore counted against recall and nDCG,
    exactly as BEIR does. ``only_hits`` drops queries whose pool holds no relevant document
    (a reranker cannot help them; useful for a compact committed set). ``max_queries`` cuts
    after that many emitted rows.
    """
    index = BM25(
        {doc_id: f"{title} {text}" for doc_id, (title, text) in corpus.items()}
    )
    rows: list[dict[str, Any]] = []
    for qid in sorted(qrels):
        grades = qrels[qid]
        ideal = sorted((g for g in grades.values() if g > 0), reverse=True)
        if not ideal or qid not in queries:
            continue
        candidates = [
            {
                "url": f"{url_prefix}{doc_id}",
                "title": corpus[doc_id][0],
                "snippet": clip_text(corpus[doc_id][1], snippet_chars),
                "rel": grades.get(doc_id, 0),
            }
            for doc_id, _ in index.search(queries[qid], top=top)
        ]
        if only_hits and not any(c["rel"] > 0 for c in candidates):
            continue
        rows.append(
            {
                "qid": qid,
                "query": queries[qid],
                "ideal_rels": ideal,
                "candidates": candidates,
            }
        )
        if max_queries is not None and len(rows) >= max_queries:
            break
    return rows


def beir_zip_url(dataset: str) -> str:
    """The UKP public mirror BEIR itself downloads from."""
    return f"{_BEIR_BASE}/{dataset}.zip"


def fetch_beir(dataset: str, workdir: str, zip_url: str | None = None) -> str:
    """Ensure ``<workdir>/<dataset>/`` exists: download the zip once, extract it once.

    Returns the dataset directory. The zip is kept beside it so a re-run is offline.
    """
    os.makedirs(workdir, exist_ok=True)
    zip_path = os.path.join(workdir, f"{dataset}.zip")
    root = os.path.join(workdir, dataset)
    if not os.path.isfile(zip_path):
        url = zip_url or beir_zip_url(dataset)
        with (
            urlopen(url, timeout=300) as response,
            open(f"{zip_path}.part", "wb") as out,
        ):
            shutil.copyfileobj(response, out)
        os.replace(f"{zip_path}.part", zip_path)
    if not os.path.isfile(os.path.join(root, "corpus.jsonl")):
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(workdir)
    return root


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval_rerank.py",
        description="Measure the rerank stage (nDCG@10 / recall@5, before vs after).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="score an eval set with one or more backends")
    run.add_argument(
        "eval_set",
        help="JSONL eval set, plain or .gz (see module docstring for the shape)",
    )
    run.add_argument(
        "--backend",
        default="auto",
        help="comma-separated backends: auto,onnx,fastembed,flashrank,none (default: auto)",
    )
    run.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument(
        "--out-dir", default="eval", help="where results-<date>.{json,md} go"
    )
    run.add_argument("--date", default=None, help="override the date in the file names")
    run.add_argument(
        "--label", default=None, help="suffix: results-<date>-<label>.{json,md}"
    )

    build = sub.add_parser(
        "build-beir", help="BEIR dataset -> eval JSONL via stdlib BM25"
    )
    build.add_argument("--dataset", default="scifact")
    build.add_argument("--split", default="test")
    build.add_argument("--workdir", default=os.path.join("/tmp", "beir"))
    build.add_argument("--zip-url", default=None, help="override the UKP mirror URL")
    build.add_argument("--out", required=True, help="output JSONL path (.gz = gzipped)")
    build.add_argument("--top", type=int, default=30, help="BM25 candidates per query")
    build.add_argument(
        "--snippet-chars",
        type=int,
        default=300,
        help="truncate document text; 0 = full",
    )
    build.add_argument("--max-queries", type=int, default=None)
    build.add_argument(
        "--only-hits",
        action="store_true",
        help="drop queries with no relevant candidate",
    )
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    queries = load_eval_set(args.eval_set)
    backends = [name.strip() for name in args.backend.split(",") if name.strip()]
    report = evaluate(
        queries,
        backends=backends,
        top_k=args.top_k,
        model=args.model,
        eval_set=args.eval_set,
    )
    report["date"] = args.date or today()
    stem = f"results-{report['date']}" + (f"-{args.label}" if args.label else "")
    os.makedirs(args.out_dir, exist_ok=True)
    with open(
        os.path.join(args.out_dir, f"{stem}.json"), "w", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    markdown = summarize_markdown(report)
    with open(
        os.path.join(args.out_dir, f"{stem}.md"), "w", encoding="utf-8"
    ) as handle:
        handle.write(markdown)
    print(markdown, end="")
    return 0


def _cmd_build_beir(args: argparse.Namespace) -> int:
    root = fetch_beir(args.dataset, args.workdir, zip_url=args.zip_url)
    corpus, queries, qrels = load_beir(root, split=args.split)
    rows = build_beir_jsonl(
        corpus,
        queries,
        qrels,
        top=args.top,
        snippet_chars=args.snippet_chars,
        max_queries=args.max_queries,
        only_hits=args.only_hits,
        url_prefix=f"beir://{args.dataset}/",
    )
    _write_text(
        args.out, "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in rows)
    )
    print(f"wrote {len(rows)} queries x top-{args.top} candidates to {args.out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    return _cmd_build_beir(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
