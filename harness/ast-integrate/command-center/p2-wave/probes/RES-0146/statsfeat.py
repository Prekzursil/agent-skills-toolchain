#!/usr/bin/env python3
"""Rail 2: a priori statistical classifier. Independent of lexical.py.

Uses type-token ratio and sentence-length variance on body text only.
Does not import corpus labels, URLs, domains, or lexical.py.
"""
from __future__ import annotations

import math
import re

TOKEN_RE = re.compile(r"[A-Za-z0-9']+")
SENT_RE = re.compile(r"[.!?]+")

# Frozen a priori. Uniform medium sentences + low lexical diversity → mill.
TTR_MAX_TOKENS = 2000
TTR_THRESHOLD = 0.38
STDEV_THRESHOLD = 5.5
MEAN_LEN_THRESHOLD = 18.0


def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def sentence_lengths(text: str) -> list[int]:
    parts = [p.strip() for p in SENT_RE.split(text) if p.strip()]
    if not parts:
        words = text.split()
        return [len(words)] if words else [0]
    return [len(p.split()) for p in parts]


def _stdev(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    var = sum((x - mean) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(var)


def stats_score(text: str) -> dict:
    toks = tokens(text)[:TTR_MAX_TOKENS]
    n = len(toks)
    ttr = (len(set(toks)) / n) if n else 0.0
    lens = [float(x) for x in sentence_lengths(text)]
    mean_len = (sum(lens) / len(lens)) if lens else 0.0
    stdev = _stdev(lens)
    millish = (ttr < TTR_THRESHOLD) or (
        stdev < STDEV_THRESHOLD and mean_len > MEAN_LEN_THRESHOLD
    )
    pred = "mill" if millish else "practitioner"
    return {
        "n_tokens": n,
        "ttr": round(ttr, 6),
        "sentence_mean": round(mean_len, 4),
        "sentence_stdev": round(stdev, 4),
        "ttr_threshold": TTR_THRESHOLD,
        "stdev_threshold": STDEV_THRESHOLD,
        "mean_len_threshold": MEAN_LEN_THRESHOLD,
        "prediction": pred,
        "derivation": "a-priori-ttr-and-sentence-stdev-on-body-text",
    }


def predict_label(text: str) -> str:
    return stats_score(text)["prediction"]
