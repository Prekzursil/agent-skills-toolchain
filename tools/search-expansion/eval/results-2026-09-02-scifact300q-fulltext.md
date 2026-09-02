# Rerank stage eval (2026-09-02)

Set: `/tmp/beir/scifact-full-0.jsonl` - 300 queries (300 with a judged relevant document), top_k=30, requested model `Xenova/ms-marco-MiniLM-L-6-v2`.

| order | nDCG@10 | recall@5 | lift nDCG@10 | reranked queries | latency ms mean/p50/max | verdict |
|---|---|---|---|---|---|---|
| baseline (RRF order) | 0.6588 | 0.7126 | - | - | - | - |
| onnx | 0.6845 | 0.7337 | +0.0256 | 300/300 | 397.99/356.789/841.661 | RERANK_ENABLED=1 (nDCG@10 lift +0.0256 >= +0.02 on this set) |

Decision rule: RERANK_ENABLED=1 only if nDCG@10 lift >= +0.02 on the eval set; otherwise leave off (plan doc 2026-09-02-search-research-tools-gemhunt.md, Wave 2).
