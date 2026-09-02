# Rerank stage eval (2026-09-02)

Set: `eval/scifact-50q-top30-300c.jsonl.gz` - 50 queries (50 with a judged relevant document), top_k=30, requested model `Xenova/ms-marco-MiniLM-L-6-v2`.

| order | nDCG@10 | recall@5 | lift nDCG@10 | reranked queries | latency ms mean/p50/max | verdict |
|---|---|---|---|---|---|---|
| baseline (RRF order) | 0.6334 | 0.7033 | - | - | - | - |
| onnx | 0.5306 | 0.5933 | -0.1028 | 50/50 | 109.992/105.71/370.825 | leave off (nDCG@10 lift -0.1028 < +0.02) |

Decision rule: RERANK_ENABLED=1 only if nDCG@10 lift >= +0.02 on the eval set; otherwise leave off (plan doc 2026-09-02-search-research-tools-gemhunt.md, Wave 2).
