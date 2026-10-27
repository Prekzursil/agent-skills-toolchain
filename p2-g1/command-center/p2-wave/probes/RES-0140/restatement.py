#!/usr/bin/env python3
"""Planted restatement-talk generator and speech wrapper."""
from __future__ import annotations

from textutil import _clean_plain


def restatement_talk(blog_text: str, title: str) -> str:
    """Keep the companion blog's mechanism-bearing prose; wrap as a talk.

    Dedup must collapse this against the blog. Filler sentences contain no
    extra control-plane mechanisms. Caller must pass already-textified bytes.
    """
    body = _clean_plain(blog_text)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        paras = [ln.strip() for ln in body.split("\n") if ln.strip()]
    out = [
        f"Good morning. Thanks for having me. Today I am going to walk through {title}.",
        "This talk restates the companion engineering blog. I am not adding a new design.",
    ]
    for i, p in enumerate(paras):
        if i > 0 and i % 4 == 0:
            out.append("Let me say the same point in spoken form.")
        out.append(p)
    out.append(
        "That is the same design we already published in the companion post. "
        "I will take questions."
    )
    return "\n\n".join(out) + "\n"


def speech_wrap(source_text: str, title: str) -> str:
    """Spoken walkthrough of a fetched document that is not a blog restatement."""
    body = _clean_plain(source_text)
    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paras:
        paras = [ln.strip() for ln in body.split("\n") if ln.strip()]
    out = [
        f"Welcome. This session is a live walkthrough of {title}.",
        "I will read the control-plane surface as if we were on stage with the spec open.",
    ]
    for p in paras:
        out.append(p)
    out.append("That is the walkthrough. Questions from the floor.")
    return "\n\n".join(out) + "\n"
