# Rerank stage eval (2026-09-02)

Set: `/tmp/beir/scifact-full-300.jsonl` - 300 queries (300 with a judged relevant document), top_k=30, requested model `Xenova/ms-marco-MiniLM-L-6-v2`.

| order | nDCG@10 | recall@5 | lift nDCG@10 | reranked queries | latency ms mean/p50/max | verdict |
|---|---|---|---|---|---|---|
| baseline (RRF order) | 0.6588 | 0.7126 | - | - | - | - |
| onnx | 0.5846 | 0.6522 | -0.0742 | 300/300 | 74.26/66.951/824.286 | leave off (nDCG@10 lift -0.0742 < +0.02) |

Decision rule: RERANK_ENABLED=1 only if nDCG@10 lift >= +0.02 on the eval set; otherwise leave off (plan doc 2026-09-02-search-research-tools-gemhunt.md, Wave 2).
