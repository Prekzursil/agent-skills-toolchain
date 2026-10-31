#!/usr/bin/env python
"""Phase 8 - SEMANTIC matching (`_USER-PROMPTS.md:10954`).

HONEST NAMING (read this before citing a recall number)
-------------------------------------------------------
This lane is **lexical-semantic**, not neural. It is BM25 (distributional term
weighting) + character-n-gram cosine (morphological robustness) + a curated concept
expansion (vocabulary bridging). It has NO embedding model and makes NO network call.

That is a deliberate trade, not an oversight:

  * `hooks/semantic-router/` already provides the neural lane (nomic-embed-text over
    Ollama). It fails open to lexical when the endpoint is down, so it cannot back a
    gate -- `ci-hygiene.md` 2 forbids a live-network dependency in the fast suite, and
    a probe that is silent both when the router works and when Ollama is missing
    measures nothing.
  * A hermetic lane can be a REGRESSION GATE. The spec's final clause demands a
    regression suite; a suite that needs a model server is not one.

**Residual, stated inline:** a neural lane would very likely (55-80%) beat this one on
pure paraphrase queries where the user shares no vocabulary with the capability at all.
The settling experiment is to run `metrics.evaluate()` over the same labelled set with
`hooks/semantic-router/embed.py` supplying the recall lane and compare recall@5 on the
L2 (author-paraphrase) subset specifically. NOT RUN here: it needs Ollama, which this
unit must not depend on. The two lanes are complementary, not competing -- this one
gates, that one serves live traffic.

WHY BM25 RATHER THAN RAW TERM OVERLAP
-------------------------------------
Term overlap ranks by how MANY words match; BM25 ranks by how SURPRISING the matches
are. Over this corpus that is the whole game: 912 capability records share a large
common vocabulary ("agent", "test", "review", "file", "workflow"), and a matcher
without inverse-document-frequency weighting is dominated by it. IDF is what makes
"reframe" (df=3) outweigh "video" (df=40) in the same query.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .descriptions import tokens

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .index import Index

# --------------------------------------------------------------------------- BM25

#: Okapi BM25 term-frequency saturation. 1.2 is the standard default; the corpus here
#: has short documents where repeated terms are rarely meaningful, so saturation should
#: bite early.
BM25_K1 = 1.2
#: Length normalization. 0.75 standard. Load-bearing for THIS corpus because record
#: lengths span two orders of magnitude (a 40-char mcp record vs a 4,000-char skill),
#: and without it long records win every query on term count alone.
BM25_B = 0.75

#: Character n-gram width for the morphology lane. 4 is the shortest width that keeps
#: whole short domain words ("dock", "burn", "mask") intact as single grams while still
#: matching across inflection ("docking"/"docked" share "dock").
NGRAM_N = 4

#: Fusion weights. Rule lane is added by router.py; these two are the recall lane.
W_BM25 = 0.75
W_NGRAM = 0.25


# ------------------------------------------------------------------ concept expansion
#
# A hand-authored bridge from natural TASK vocabulary to INVENTORY vocabulary. This is
# the component most at risk of flattering its own evaluation, so it is disclosed
# precisely and ablated in `metrics.evaluate(ablation=...)`:
#
#   * Authored from the TASK side (how a person phrases a request), then checked to
#     resolve against inventory terms. It was NOT authored by reading the labelled
#     query set, and no entry was added or tuned after seeing a precision/recall
#     number. `metrics` reports the with/without delta so the contribution is visible
#     rather than asserted.
#   * Expansion terms enter at REDUCED weight (`EXPANSION_WEIGHT`) so a bridged term can
#     never outrank a term the user actually typed.
CONCEPTS: dict[str, tuple[str, ...]] = {
    # media
    "vertical": ("reframe", "9:16", "portrait", "shorts", "reels", "tiktok"),
    "portrait": ("reframe", "vertical", "9:16"),
    "tiktok": ("reframe", "vertical", "shorts", "reels", "social"),
    "subtitle": ("caption", "subtitles", "ass", "libass", "burn", "hardsub"),
    "subtitles": ("caption", "burn", "hardsub", "libass"),
    "watermark": ("logo", "inpaint", "propainter", "removal", "bug"),
    "logo": ("watermark", "inpaint", "removal"),
    "dead": ("silence", "silencedetect", "trim", "pause"),
    "dub": ("dubbing", "voice", "clone", "translate", "tts"),
    "voiceover": ("tts", "speech", "narration", "voice"),
    "transcribe": ("asr", "transcription", "diarization", "whisper"),
    # engineering
    "flaky": ("flake", "nondeterministic", "retry", "intermittent"),
    "refactor": ("refactoring", "equivalence", "behaviour", "behavior", "rewrite"),
    "slow": ("performance", "perf", "latency", "profile", "optimi"),
    "crash": ("debug", "debugging", "traceback", "exception", "failure"),
    "bug": ("debug", "debugging", "defect", "failure", "repair"),
    "coverage": ("tests", "pytest", "threshold", "branch"),
    "merge": ("conflict", "rebase", "reconcile", "branch", "pr"),
    "deploy": ("deployment", "release", "rollout", "canary", "rollback"),
    "secret": ("credential", "token", "redact", "leak", "gitleaks"),
    "vulnerability": ("security", "vuln", "cve", "semgrep", "bandit", "audit"),
    "review": ("reviewer", "critique", "adversarial", "audit"),
    "lint": ("ruff", "format", "style", "static"),
    # reverse engineering
    "disassemble": ("disassembly", "ida", "ghidra", "radare2", "binary"),
    "decompile": ("decompilation", "pseudo", "ghidra", "ida"),
    "hook": ("frida", "instrumentation", "runtime", "intercept"),
    "offset": ("rva", "signature", "aob", "pattern", "relink"),
    "savefile": ("save", "bcsfe", "roundtrip"),
    # agents / harness
    "parallel": ("fan-out", "fanout", "concurrent", "subagents", "dispatch"),
    "subagent": ("agent", "fan-out", "dispatch", "orchestration"),
    "prompt": ("prompting", "instruction", "spec"),
    "memory": ("recall", "basic-memory", "note", "checkpoint", "continuity"),
    "decide": ("decision", "council", "deliberation", "tradeoff", "adjudicate"),
    "disagree": ("dissent", "council", "debate", "adversarial", "minority"),
    "unanimous": ("groupthink", "echo", "sycophancy", "dissent", "council"),
    "stuck": ("deadlock", "hang", "stall", "escalate", "pivot"),
    "hallucinate": ("fabricat", "unverified", "verification", "evidence", "honesty"),
    # design / ui
    "ugly": ("design", "visual", "critique", "aesthetic", "palette"),
    "accessibility": ("a11y", "contrast", "wcag", "focus", "aria"),
    "contrast": ("a11y", "wcag", "apca", "colour", "color"),
    "figma": ("design", "canvas", "transpose", "mirror"),
    "screenshot": ("visual", "capture", "playwright", "drive"),
    # science / cloud
    "docking": ("dock", "glide", "receptor", "ligand", "pose"),
    "molecule": ("smiles", "rdkit", "ligand", "cheminformatics"),
    "gpu": ("cuda", "runpod", "modal", "lightning", "compute"),
    "paper": ("literature", "arxiv", "doi", "scholarly", "citation"),
    "scrape": ("scraping", "crawl", "firecrawl", "extract", "markdown"),
}

#: Expansion terms are worth this fraction of a typed term. Strictly < 1 so a bridge
#: can add recall but never overrule the user's own words.
EXPANSION_WEIGHT = 0.45

#: CONCEPT EXPANSION IS OFF BY DEFAULT, ON A MEASURED NEGATIVE RESULT.
#:
#: The ablation over the 57-query labelled set (`metrics.ablate`) measured, at k=5:
#:     with expansion    recall 0.5196   gold-hit 0.5686
#:     without           recall 0.5392   gold-hit 0.5882   (delta +0.0196)
#:
#: The hand-authored bridge is NET HARMFUL: each expansion adds a 0.45-weight term to the
#: query, which raises the BM25 ceiling (`SemanticModel.ceiling`) for every candidate
#: while only some candidates gain matching mass -- so it dilutes the absolute score of
#: the records that were already right. The idea is defensible and the mechanism works;
#: it simply does not pay on this corpus, whose descriptions are already vocabulary-rich.
#:
#: Kept in the tree rather than deleted for two reasons: it is the ablation's control arm
#: (removing it would remove the evidence for this decision), and it is the component most
#: likely to matter for a corpus with terser descriptions. Shipping it ON because it was
#: effort already spent would be exactly the decorative-feature failure this program
#: keeps finding. Re-enable per call with `SemanticModel.fit(..., use_expansion=True)`.
EXPANSION_DEFAULT = False


def expand(query_tokens: list[str]) -> dict[str, float]:
    """Weighted query term bag: typed terms at 1.0, bridged terms at EXPANSION_WEIGHT.

    A term already typed by the user is never downgraded by also appearing as somebody
    else's expansion (`max`, not `+=`) -- otherwise a bridge could silently reweight the
    user's own vocabulary.
    """
    bag: dict[str, float] = {}
    for t in query_tokens:
        bag[t] = 1.0
    for t in query_tokens:
        for syn in CONCEPTS.get(t, ()):
            for s in tokens(syn) or [syn]:
                if bag.get(s, 0.0) < EXPANSION_WEIGHT:
                    bag[s] = EXPANSION_WEIGHT
    return bag


def ngrams(text: str, n: int = NGRAM_N) -> Counter[str]:
    """Character n-grams over whitespace-normalized lowercase text."""
    s = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not s:
        return Counter()
    padded = f" {s} "
    return Counter(padded[i : i + n] for i in range(max(len(padded) - n + 1, 0)))


# --------------------------------------------------------------------------- model


@dataclass
class SemanticModel:
    """Fitted, deterministic retrieval model over an index. Build once, query many."""

    ids: list[str] = field(default_factory=list)
    tf: list[Counter[str]] = field(default_factory=list)
    lens: list[int] = field(default_factory=list)
    df: Counter[str] = field(default_factory=Counter)
    idf: dict[str, float] = field(default_factory=dict)
    avgdl: float = 1.0
    grams: list[Counter[str]] = field(default_factory=list)
    gram_norm: list[float] = field(default_factory=list)
    n: int = 0
    use_expansion: bool = EXPANSION_DEFAULT
    use_ngram: bool = True

    # ---------------------------------------------------------------- fit
    @classmethod
    def fit(
        cls,
        idx: Index,
        *,
        use_expansion: bool = EXPANSION_DEFAULT,
        use_ngram: bool = True,
    ) -> SemanticModel:
        m = cls(use_expansion=use_expansion, use_ngram=use_ngram)
        for r in idx.records:
            toks = tokens(r.routing_text)
            tf = Counter(toks)
            m.ids.append(r.id)
            m.tf.append(tf)
            m.lens.append(len(toks))
            m.df.update(tf.keys())
            g = ngrams(r.routing_text) if use_ngram else Counter()
            m.grams.append(g)
            m.gram_norm.append(math.sqrt(sum(v * v for v in g.values())) or 1.0)
        m.n = len(m.ids)
        m.avgdl = (sum(m.lens) / m.n) if m.n else 1.0
        # Lucene-style BM25 IDF: always positive, so a term present in nearly every
        # document contributes ~0 instead of a NEGATIVE score (the textbook
        # `log((N-df)/df)` form goes negative past df > N/2 and would actively PENALIZE
        # a capability for containing a common word).
        for t, d in m.df.items():
            m.idf[t] = math.log(1.0 + (m.n - d + 0.5) / (d + 0.5))
        return m

    # ---------------------------------------------------------------- score
    def bm25(self, bag: dict[str, float]) -> list[float]:
        out = [0.0] * self.n
        for term, qw in bag.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            widf = idf * qw
            for i, tf in enumerate(self.tf):
                f = tf.get(term)
                if not f:
                    continue
                dl = self.lens[i] or 1
                denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / self.avgdl)
                out[i] += widf * (f * (BM25_K1 + 1)) / denom
        return out

    def ngram_cos(self, query: str) -> list[float]:
        if not self.use_ngram:
            return [0.0] * self.n
        qg = ngrams(query)
        if not qg:
            return [0.0] * self.n
        qn = math.sqrt(sum(v * v for v in qg.values())) or 1.0
        out = [0.0] * self.n
        for i, g in enumerate(self.grams):
            if not g:
                continue
            small, big = (qg, g) if len(qg) <= len(g) else (g, qg)
            dot = 0.0
            for k, v in small.items():
                w = big.get(k)
                if w:
                    dot += v * w
            if dot:
                out[i] = dot / (qn * self.gram_norm[i])
        return out

    def ceiling(self, bag: dict[str, float]) -> float:
        """Largest BM25 mass this query could plausibly earn: the sum of its own
        IDF-weighted term weights.

        With Okapi parameters and a document of average length, a term occurring ONCE
        contributes exactly `idf * qw`, so this sum is the score of a document that
        contains every query term. It is candidate-INDEPENDENT, which is the whole
        point: dividing by it yields "what fraction of the query's discriminative mass
        is explained by this record" on an ABSOLUTE scale.
        """
        return sum(qw * self.idf.get(t, 0.0) for t, qw in bag.items())

    def score(self, query: str) -> dict[str, float]:
        """id -> ABSOLUTE match score in [0, 1].

        MEASURED DEFECT this replaces -- and it was the most consequential bug in the
        unit. The first version divided by the run's own maximum (`b[i]/max(b)`), which
        forces the top candidate to ~1.0 for EVERY query no matter how irrelevant. The
        effect: on the six L3 no-fit queries ("what is the capital of Mongolia", "book me
        a dentist appointment") the router's abstain rate measured **0.0/6** -- it
        confidently injected a capability every time, because a per-query max-normalized
        score cannot express "nothing here matches". Relative normalization destroys
        exactly the signal abstention needs.

        Both lanes are now absolute: BM25 against the query's own achievable ceiling, and
        the n-gram lane as a raw cosine (which was already absolute before the old code
        divided that away too).
        """
        toks = tokens(query)
        bag = expand(toks) if self.use_expansion else {t: 1.0 for t in toks}
        b = self.bm25(bag)
        ceil = self.ceiling(bag)
        g = self.ngram_cos(query)
        if ceil <= 0:
            # Every query term is unknown to the corpus. The honest score is the
            # morphological lane alone -- never a rescaled zero.
            return {self.ids[i]: W_NGRAM * g[i] for i in range(self.n)}
        return {
            self.ids[i]: W_BM25 * min(1.0, b[i] / ceil) + W_NGRAM * g[i]
            for i in range(self.n)
        }

    def top(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        s = self.score(query)
        # Deterministic tie-break by id -- filesystem/dict order must never decide.
        return sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
