#!/usr/bin/env python3
"""Rail 1: a priori lexical/template classifier. Body text only.

Frozen before scoring. Does not import gold labels, URLs, or domains.
"""
from __future__ import annotations

# Case-insensitive substrings typical of SEO/LLM filler. Frozen a priori.
PHRASES: tuple[str, ...] = (
    "in today's digital world",
    "in the ever-evolving",
    "in this article, we will",
    "in this article we will",
    "in this blog post",
    "in this tutorial, we will",
    "in this tutorial we will",
    "it's important to note",
    "it is important to note",
    "delve into",
    "deep dive into",
    "unlock the power",
    "harness the power",
    "take your",
    "to the next level",
    "look no further",
    "without further ado",
    "comprehensive guide",
    "one-stop solution",
    "packed with features",
    "cutting-edge",
    "game-changer",
    "game changer",
    "revolutionize",
    "seamlessly",
    "leverage",
    "robust solution",
    "landscape of",
    "whether you're a beginner",
    "whether you are a beginner",
    "stay tuned",
    "in conclusion",
    "to sum up",
    "the world of",
    "as we navigate",
    "in today's fast-paced",
    "it is worth mentioning",
    "when it comes to",
    "in order to",
    "not only",
    "but also",
    "a wide range of",
    "plays a crucial role",
    "it goes without saying",
    "let's dive in",
    "lets dive in",
    "by the end of this",
    "this article aims",
    "in this post, we'll",
    "in this post we'll",
)

# A priori: predict mill if at least this many phrase hits.
HIT_THRESHOLD = 2


def phrase_hits(text: str) -> list[str]:
    low = text.lower()
    return [p for p in PHRASES if p in low]


def lexical_score(text: str) -> dict:
    hits = phrase_hits(text)
    pred = "mill" if len(hits) >= HIT_THRESHOLD else "practitioner"
    return {
        "n_hits": len(hits),
        "hits": hits[:12],
        "threshold": HIT_THRESHOLD,
        "prediction": pred,
        "derivation": "a-priori-substring-count-on-body-text",
    }


def predict_label(text: str) -> str:
    return lexical_score(text)["prediction"]
