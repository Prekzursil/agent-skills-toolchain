# Rerank stage eval set + results (2026-09-02)

This folder is the receipt behind the "Rerank stage (optional, default OFF)" section of
`../README.md`. Everything in it was produced by `../eval_rerank.py`; nothing was hand-edited.

## What is committed

| file | what | size |
|---|---|---|
| `scifact-50q-top30-300c.jsonl.gz` | 50 BEIR SciFact test claims, each with the stdlib-BM25 top-30 abstracts as candidates, text clipped to 300 chars (SERP-snippet length), graded `rel` from the qrels, `ideal_rels` = every positive judgement | 217 KB |
| `results-2026-09-02-scifact50q-snip300.{json,md}` | the ONNX run on the committed set (reproducible offline from this folder once the model is cached) | 5 KB |
| `results-2026-09-02-scifact300q-snip300.{json,md}` | the same recipe on ALL 300 test claims at 300 chars (built under `/tmp`, not committed: 4.3 MB) | 23 KB |
| `results-2026-09-02-scifact300q-fulltext.{json,md}` | all 300 claims with FULL abstracts (`--snippet-chars 0`): the upper bound, and the cross-check against the published BEIR number | 23 KB |

The 600- and 1000-char runs quoted below were produced the same way; their result files stay
under `/tmp` to keep this folder under the ~300 KB budget. Every row is one command away (see
"Reproduce").

## Provenance and license

* Dataset: **SciFact** (Wadden et al., "Fact or Fiction: Verifying Scientific Claims", EMNLP
  2020, https://aclanthology.org/2020.emnlp-main.609), in the **BEIR** packaging (Thakur et
  al., NeurIPS 2021 Datasets and Benchmarks) downloaded from the UKP mirror BEIR itself uses:
  `https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip`
  (2,816,079 bytes; 5,183 abstracts, 1,109 queries, `qrels/test.tsv` = 300 judged claims).
* License, per the official `allenai/scifact` `LICENSE.md`: the claims and evidence
  annotations (our `query` / `rel` / `ideal_rels`) are **CC BY 4.0**; the abstracts (our
  `title` / `snippet`) come from S2ORC and are **ODC-By 1.0**. The Hugging Face dataset card
  lists the set as CC BY-NC 2.0 instead; this folder is used for a non-commercial eval fixture
  either way, and attribution is given here. Cite the EMNLP 2020 paper if you reuse it.
* Derivation: `qid` is the BEIR query id; `url` is `beir://scifact/<corpus-id>`; candidates
  are the stdlib Okapi BM25 (`k1=0.9, b=0.4`, `[a-z0-9]+` tokens, no stemming) top-30 over
  `title + " " + text` of every abstract; `snippet` is the abstract clipped to 300 chars on a
  word boundary (`clip_text`); `rel` is the qrels grade (0 when unjudged); `ideal_rels` lists
  every positive grade for the claim so nDCG's ideal and recall's denominator are
  qrels-based, as in BEIR. The 50 committed claims are the first 50 by sorted string `qid`
  (`--max-queries 50`), no cherry-picking; 38 of them have a relevant abstract inside the
  BM25 top-30 (a first-stage miss scores 0 before AND after, so it dilutes the lift but keeps
  the absolute numbers comparable).

## Why BM25 and not the estate's SearXNG

The eval ran on a cloud VM that cannot reach the estate's SearXNG, and a reranker eval needs a
FIXED candidate pool anyway (the same 30 documents before and after). The stdlib BM25 is a
stand-in for "whatever produced the fused list"; its nDCG@10 of 0.6588 on the 300 test
claims sits next to the BEIR paper's Anserini BM25 figure for SciFact (0.665), which is the
sanity check that the first stage is not the thing being measured.

## Measured (2026-09-02)

Backend `onnx`: `onnxruntime` 1.29.0 CPU execution provider, `tokenizers` 0.23.1, `numpy`
2.4.4, Python 3.12.3, 8 vCPU cloud VM; model `Xenova/ms-marco-MiniLM-L-6-v2`
`onnx/model_quantized.onnx` (int8, 23,143,499 bytes) + `tokenizer.json`, pairs truncated to
512 tokens longest-first, batch 16. Latency is per query for 30 candidates; `max` includes the
first call, which loads the model (~0.7 s).

| set | passage text | nDCG@10 before -> after | lift | recall@5 before -> after | improved / worsened / unchanged | latency ms mean / p50 | verdict (rule: lift >= +0.02) |
|---|---|---|---|---|---|---|---|
| 300 claims | 300 chars (SERP snippet) | 0.6588 -> 0.5846 | **-0.0742** | 0.7126 -> 0.6522 | 59 / 84 / 157 | 74 / 67 | leave off |
| 300 claims | 600 chars | 0.6588 -> 0.6359 | -0.0230 | 0.7126 -> 0.6920 | 59 / 60 / 181 | 137 / 116 | leave off |
| 300 claims | 1000 chars | 0.6588 -> 0.6672 | +0.0084 | 0.7126 -> 0.7281 | 65 / 49 / 186 | 201 / 180 | leave off |
| 300 claims | full abstract (mean 1,590 chars) | 0.6588 -> 0.6845 | **+0.0256** | 0.7126 -> 0.7337 | 66 / 46 / 188 | 398 / 357 | RERANK_ENABLED=1 |
| 50 claims (committed) | 300 chars | 0.6334 -> 0.5306 | -0.1028 | 0.7033 -> 0.5933 | 5 / 15 / 30 | 110 / 106 | leave off |

Reading: the cross-encoder's value is a function of how much of the document it gets to
read. On full abstracts it delivers the lift the literature reports (BEIR: BM25 0.665 ->
BM25+CE 0.688 on SciFact; here 0.659 -> 0.685), which validates the pipeline end to end. On
SERP-length snippets the same model makes the ranking WORSE than the first stage that saw the
whole document, and the break-even is around 800-900 characters of passage. Recall@5 moves
the same way as nDCG@10 in every row.

## Reproduce

```bash
cd tools/search-expansion
pip install --break-system-packages onnxruntime tokenizers numpy      # eval only; tests need none
export RERANK_MODEL_DIR=/tmp/rerank-models RERANK_ALLOW_DOWNLOAD=1    # one 23 MB fetch, then offline

# the committed set (offline once the model is cached)
python3 eval_rerank.py run eval/scifact-50q-top30-300c.jsonl.gz --backend onnx \
    --out-dir eval --date 2026-09-02 --label scifact50q-snip300

# rebuild the committed set byte-for-byte (downloads scifact.zip once under /tmp/beir)
python3 eval_rerank.py build-beir --dataset scifact --workdir /tmp/beir \
    --out eval/scifact-50q-top30-300c.jsonl.gz --top 30 --snippet-chars 300 --max-queries 50

# the 300-claim rows: N in 300 600 1000 0 (0 = full abstracts)
python3 eval_rerank.py build-beir --dataset scifact --workdir /tmp/beir \
    --out /tmp/beir/scifact-full-N.jsonl --top 30 --snippet-chars N
python3 eval_rerank.py run /tmp/beir/scifact-full-N.jsonl --backend onnx \
    --out-dir /tmp/rerank-eval --date 2026-09-02 --label scifact300q-snipN
```

`--backend auto,onnx,fastembed,flashrank,none` runs several backends in one report; a backend
that is not installed shows up as `available: false` with the stage's own reason, never as a
crash.
