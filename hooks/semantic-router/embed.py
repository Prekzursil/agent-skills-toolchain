#!/usr/bin/env python
"""Shared Ollama embedding helper for the semantic router (nomic-embed-text, 768-dim).

ONE place that talks to Ollama, read by build_index.py, route.py and eval.py.
Hard contract: every public call is FAIL-OPEN — it returns None / [] on any error
(Ollama down, model missing, timeout, malformed JSON) and NEVER raises. Callers
treat None as "no semantic lane this turn" and fall back to the lexical lane.

Vectors are L2-normalized on return, so cosine similarity == dot product downstream.
`keep_alive` is sent on every call so the (small, 274MB) model stays resident and
warm-call latency stays ~100ms; the first call after an idle eviction pays a one-time
~2s model load, which route.py bounds with a short timeout + fail-open.
"""
import json
import math
import os
import urllib.request

OLLAMA_URL = os.environ.get("SEMROUTER_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("SEMROUTER_EMBED_MODEL", "nomic-embed-text")
KEEP_ALIVE = os.environ.get("SEMROUTER_KEEP_ALIVE", "60m")
DIM = 768

# nomic-embed-text is a RETRIEVAL model: asymmetric task prefixes (documents vs query)
# measurably sharpen query<->document separation vs symmetric embedding. The index is built
# with DOC_PREFIX; the live prompt is embedded with QUERY_PREFIX. Both must match the index,
# so they are pinned here (env-overridable only for deliberate experiments).
DOC_PREFIX = os.environ.get("SEMROUTER_DOC_PREFIX", "search_document: ")
QUERY_PREFIX = os.environ.get("SEMROUTER_QUERY_PREFIX", "search_query: ")


def _l2(v):
    s = 0.0
    for x in v:
        s += x * x
    n = math.sqrt(s) or 1.0
    return [x / n for x in v]


def _post(payload, timeout):
    req = urllib.request.Request(
        OLLAMA_URL + "/api/embed",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def embed(texts, timeout=8.0, keep_alive=None):
    """Embed a str or list[str]. Returns a single L2-normalized vector (str input),
    a list of vectors (list input), or None on ANY failure. Never raises."""
    if texts is None:
        return None
    single = isinstance(texts, str)
    batch = [texts] if single else [t for t in texts]
    if not batch:
        return [] if not single else None
    try:
        r = _post({"model": MODEL, "input": batch, "keep_alive": keep_alive or KEEP_ALIVE}, timeout)
        embs = r.get("embeddings")
        if not isinstance(embs, list) or len(embs) != len(batch):
            return None
        out = [_l2(v) for v in embs]
        return out[0] if single else out
    except Exception:
        return None


def embed_query(text, timeout=8.0):
    """Embed a live prompt for retrieval (applies QUERY_PREFIX). Returns vector or None."""
    if not text:
        return None
    return embed(QUERY_PREFIX + text, timeout=timeout)


def embed_many(texts, batch_size=48, timeout=120.0, progress=None):
    """Embed a long list in chunks (index build path). Returns list[vector|None] aligned
    to `texts`; a failed chunk yields None placeholders (caller decides retry/skip)."""
    out = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        vecs = embed(chunk, timeout=timeout)
        if vecs is None:
            vecs = [None] * len(chunk)
        out.extend(vecs)
        if progress:
            progress(min(i + batch_size, len(texts)), len(texts))
    return out


def health():
    """Return (ok, detail). Cheap reachability + dim check for build/eval diagnostics."""
    v = embed("health probe", timeout=15.0)
    if v is None:
        return False, "ollama-unreachable-or-model-missing"
    if len(v) != DIM:
        return False, f"unexpected-dim-{len(v)}"
    return True, f"ok dim={len(v)} model={MODEL}"


if __name__ == "__main__":
    ok, detail = health()
    print(("SUCCESS" if ok else "FAILED") + ":embed-health " + detail)
