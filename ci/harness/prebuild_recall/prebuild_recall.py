#!/usr/bin/env python3
"""prebuild_recall.py — the PRE-BUILD RECALL GATE.

Fires on BUILD-SHAPED work (a Workflow launch, a plan being written, a
worktree being created, the first Write into a new program directory) and
INJECTS the top basic-memory hits for the derived topic.

Contract (AGENTS.md §6): this gate **injects** (exit 0 + additionalContext).
It NEVER blocks. Blocking on a memory miss would be intolerable — a miss is
the common case and a false block would burn the whole mechanism's trust.

Why this exists
---------------
On 2026-07-18 a live->repo harness rescue was rebuilt from scratch. The
branch `chore/enshrine-runtime-config` (2026-07-13) had already done it —
better, and five days earlier. The CLAUDE.md rule ("Recall (pull) —
PROACTIVELY, unasked") did not fire. A rule that is ignored is evidence
that a rule is the wrong mechanism.

But the trigger was NOT the binding constraint that day. The existing
`RecallModule` (bounded_recall) reads a prebuilt index and nothing ever
rebuilds it; both on-disk indexes were frozen at 2026-07-10, so the
2026-07-13 note was ABSENT from the index entirely. A perfect trigger over
a stale index still surfaces nothing. Hence this module owns three things,
in order of load-bearing-ness:

  1. FRESHNESS  — refuse to be silently stale (`index_health`, `ensure_fresh`).
  2. TRIGGER    — fire on build-shaped work, not only on UserPromptSubmit.
  3. QUERY      — derive a query good enough that the hits are worth reading.

Design notes on (3), the hard part
----------------------------------
A bad query returns noise and the gate gets ignored, which is worse than no
gate. Two measured facts drive the design (see README.md for the numbers):

  * Compound tokens carry the signal; naive path-splitting destroys it.
    `agent-skills-toolchain` appears in 26/513 notes (5.1%, idf 2.94) and is
    a genuinely discriminative term. Its split part `toolchain` appears in
    ZERO notes — splitting turns a good query term into a dead one. So we
    emit the compound AND the parts, and let IDF decide which one earns its
    place.
  * Broad single words are near-worthless: `build` 17.0%, `live` 14.8%,
    `harness` 12.1%, `config` 11.1%, `mcp` 10.3% of all notes. Any scorer
    that treats these like `enshrine` (0.4%) or `rescue` (0.2%) will rank by
    document length instead of by relevance.

So scoring is IDF-weighted over an index-derived document-frequency table —
no external deps, no embeddings, computed from the same index the gate
already loads.

Silence is the default (c). Three independent gates must ALL pass:
  * ABSOLUTE floor   — the top hit must clear MIN_SCORE.
  * MARGIN test      — the top hit must stand clear of the candidate pack,
                       so a flat "everything matches weakly" distribution
                       stays silent.
  * RARE-TOKEN test  — at least one matched token must be discriminative
                       (idf >= MIN_RARE_IDF). A hit assembled purely from
                       common words is rejected however high it scores.

Fail-open everywhere: any exception yields "stay silent", never an error.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

# ─── tunables (env-overridable) ──────────────────────────────────────────────

#: Tokens appearing in more than this fraction of notes are dropped outright.
#: Measured: the worst real offenders top out at 17% ("build"), so 0.30 drops
#: only true boilerplate while IDF soft-weights everything below it.
UBIQUITOUS_DF_RATIO = float(os.environ.get("PREBUILD_RECALL_UBIQ", "0.30"))

#: A token is "discriminative" when it appears in at most this FRACTION of
#: notes. Expressed as a ratio rather than an absolute IDF because IDF grows
#: without bound in N: an idf>=3.0 rule means "<=4.8% of notes" at N=513 but
#: is UNSATISFIABLE at N=6 (max achievable idf there is 1.79). Ratios are
#: scale-free; absolute IDF thresholds silently change meaning as the vault
#: grows, which is the same class of bug as an absolute score floor.
MAX_RARE_DF_RATIO = float(os.environ.get("PREBUILD_RECALL_RARE_DF", "0.05"))

#: Floor for the top hit, as a FRACTION of the best score this query could
#: possibly achieve. Deliberately a ratio, not an absolute: raw scores scale
#: with IDF, which scales with vault size, so an absolute floor silently
#: changes meaning as the vault grows. Calibrated to hold at both N=6 and
#: N=513 (see README.md "Calibration").
MIN_SCORE_RATIO = float(os.environ.get("PREBUILD_RECALL_MIN_RATIO", "0.18"))

#: How many of the top query tokens define "a good match" for normalisation.
CEILING_TOKENS = int(os.environ.get("PREBUILD_RECALL_CEILING_TOKENS", "8"))

#: A context yielding fewer than this many usable tokens is not a query.
#: Without it, a one-token query normalises against a one-token ceiling and
#: any weak match looks like a perfect one — measured: an unrelated
#: `acme-invoicing/billing/vat.py` write scored 0.65 against the real vault,
#: HIGHER than the true positive at 0.48.
MIN_QUERY_TOKENS = int(os.environ.get("PREBUILD_RECALL_MIN_QUERY", "3"))

#: The top hit must agree with the context on at least this many DISTINCT
#: tokens. This, not score magnitude, is what actually separates signal from
#: noise here. Measured against the real 513-note vault:
#:     true positive (the enshrine rebuild) -> 9 matched tokens
#:     unrelated invoicing project          -> 1
#:     generic "write the plan"             -> 2
#:     trivial scratch note                 -> 1
#: A threshold of 3 clears both sides with margin.
MIN_MATCHED_TOKENS = int(os.environ.get("PREBUILD_RECALL_MIN_MATCHED", "3"))

#: Top hit must exceed MARGIN_RATIO x the 75th-percentile candidate score.
MARGIN_RATIO = float(os.environ.get("PREBUILD_RECALL_MARGIN", "1.35"))

#: Maximum notes surfaced.
MAX_HITS = int(os.environ.get("PREBUILD_RECALL_MAX_HITS", "3"))

#: Maximum query tokens kept after ranking.
MAX_QUERY_TOKENS = int(os.environ.get("PREBUILD_RECALL_MAX_TOKENS", "24"))

#: Index older than this many days is reported STALE.
STALE_AFTER_DAYS = float(os.environ.get("PREBUILD_RECALL_STALE_DAYS", "2"))

#: Current index schema. An older schema is treated as stale regardless of age.
CURRENT_SCHEMA = int(os.environ.get("PREBUILD_RECALL_SCHEMA", "2"))

# ─── vocabulary ──────────────────────────────────────────────────────────────

#: Filesystem/scaffolding noise. These appear in essentially every path on this
#: box and carry zero information about WHAT is being built.
_PATH_NOISE: frozenset[str] = frozenset(
    """
    users user home appdata local locallow roaming temp tmp source sources src lib libs
    bin obj dist build out target node_modules venv env site-packages pycache
    documents downloads desktop program files programdata windows system32
    github git svn repos repo-root checkout worktree worktrees
    claude codex agents agent-self scratchpad
    """.split()
)

#: Generic English / dev filler that survives tokenisation but never
#: discriminates between notes.
_STOP: frozenset[str] = frozenset(
    """
    the and are was were for with this that from into over under via per any all only
    just like such been being have has had its our your their they them you
    than then use using used when whether not into new add also more most can could
    should would may might will must its their them what which who how why where here
    there about please make makes get gets set sets run runs running ran does doing
    file files dir dirs folder path paths name names test tests spec specs main index
    readme todo notes note doc docs data value values item items thing things stuff
    code codes work works working task tasks step steps part parts type types
    """.split()
)

def _machine_identity_tokens() -> frozenset[str]:
    """Tokens naming THIS machine/user rather than the work.

    The home-directory segments (the Windows username, the drive) appear in
    every absolute path on the box. They are high-IDF by accident — rare in
    the vault, ubiquitous in the context — which is the worst possible
    combination for a query term.
    """
    try:
        return frozenset(
            part.strip("\\/:").lower()
            for part in Path.home().parts
            if part.strip("\\/:")
        )
    except Exception:
        return frozenset()


_MACHINE_NOISE = _machine_identity_tokens()

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9._+#-]{1,}")
_SPLIT_RE = re.compile(r"[\\/\s._]+")
_DATEISH_RE = re.compile(r"^\d{4}(-\d{2}){0,2}$")
_NUMERIC_RE = re.compile(r"^[0-9]+$")


# ─── data types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuildContext:
    """What the gate knows about the build-shaped work about to happen."""

    kind: str  # workflow | plan | worktree | new-program-dir
    detail: str = ""  # human-readable trigger detail
    cwd: str = ""
    program_dir: str = ""
    prompt: str = ""
    paths: tuple[str, ...] = ()
    description: str = ""
    branch: str = ""


@dataclass(frozen=True)
class Hit:
    title: str
    permalink: str
    summary: str
    score: float
    matched: tuple[str, ...]


@dataclass
class IndexHealth:
    present: bool = False
    note_count: int = 0
    schema_version: int = 0
    age_days: float | None = None
    stale: bool = True
    reason: str = "absent"


@dataclass
class GateResult:
    """Terminal state (AGENTS.md §4)."""

    fired: bool = False
    reason: str = ""
    hits: list[Hit] = field(default_factory=list)
    health: IndexHealth | None = None
    query: tuple[str, ...] = ()
    message: str | None = None


# ─── tokenisation ────────────────────────────────────────────────────────────


def _tokens(text: Any) -> set[str]:
    """Whole-token extraction. Compounds like `agent-skills-toolchain` survive."""
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(str(text).lower()) if len(t) >= 3}


def _expand(raw: str) -> set[str]:
    """Emit the compound token AND its hyphen/underscore parts.

    Measured rationale: `agent-skills-toolchain` -> 26/513 notes (useful);
    its bare part `toolchain` -> 0/513 (dead). Neither form dominates in
    general, so emit both and let IDF pick the winner instead of guessing.
    """
    out: set[str] = set()
    for chunk in _SPLIT_RE.split(str(raw).lower()):
        for tok in _TOKEN_RE.findall(chunk):
            if len(tok) < 3:
                continue
            out.add(tok)
            if "-" in tok:
                out.update(p for p in tok.split("-") if len(p) >= 3)
    return out


def _usable(tok: str) -> bool:
    """Reject scaffolding, stopwords, machine identity, bare numbers."""
    if tok in _PATH_NOISE or tok in _STOP or tok in _MACHINE_NOISE:
        return False
    if _NUMERIC_RE.match(tok):
        return False
    # A bare year ("2026") is noise; a full date ("2026-07-13") is a real
    # discriminator and is kept.
    return not (_DATEISH_RE.match(tok) and tok.count("-") < 2)


# ─── document frequency / IDF ────────────────────────────────────────────────


#: A compound term matched only through one of its parts is a weaker signal
#: than an exact hit, so part-matches are discounted.
PART_MATCH_DISCOUNT = 0.5


def note_terms(note: dict[str, Any]) -> set[str]:
    """The full searchable term set of one indexed note, parts included.

    Symmetry matters here. The query side expands `enshrine-runtime-config`
    into its parts, so the note side must too — otherwise a context saying
    "runtime config" can never reach a note whose only relevant term is the
    compound `enshrine-runtime-config`. That asymmetry is a silent recall
    hole: the note is indexed, scores zero, and looks absent.
    """
    exact = _tokens(note.get("title"))
    exact |= _tokens(note.get("permalink"))
    exact |= _tokens(note.get("summary"))
    exact |= {str(k).lower() for k in (note.get("keywords") or []) if str(k).strip()}
    parts: set[str] = set()
    for term in exact:
        if "-" in term or "_" in term:
            parts.update(p for p in re.split(r"[-_]+", term) if len(p) >= 3)
    return exact | parts


def build_df(notes: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Document-frequency table over the index. Stdlib only, ~10ms at N=513."""
    df: dict[str, int] = {}
    for note in notes:
        for term in note_terms(note):
            df[term] = df.get(term, 0) + 1
    return df


def idf(token: str, df: dict[str, int], total: int) -> float:
    """Smoothed IDF. Unknown token -> max idf (it simply will not match)."""
    if total <= 0:
        return 0.0
    return math.log(total / (1 + df.get(token, 0)))


def is_discriminative(token: str, df: dict[str, int], total: int) -> bool:
    """True when `token` is rare enough to carry real signal.

    The `max(1, ...)` floor keeps the rule satisfiable on small vaults: at
    N=6 a 5% budget is 0.3 documents, which no matching token could ever
    meet, so the gate would reject everything.
    """
    if total <= 0:
        return False
    budget = max(1, int(MAX_RARE_DF_RATIO * total))
    return 0 < df.get(token, 0) <= budget


# ─── (b) query derivation — the hard part ────────────────────────────────────

#: Source weights. The program directory being created is the single most
#: honest statement of "what am I about to build", so it outranks the prompt.
_SOURCE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("program_dir", 3.0),
    ("description", 2.5),
    ("prompt", 2.0),
    ("paths", 2.0),
    ("cwd", 1.5),
    ("branch", 1.5),
)


def derive_query(
    ctx: BuildContext,
    df: dict[str, int] | None = None,
    total: int = 0,
    max_tokens: int = MAX_QUERY_TOKENS,
) -> list[tuple[str, float]]:
    """Derive a weighted query from the build context.

    Returns [(token, weight)] sorted by descending weight, where
    weight = source_weight x idf. Without a df table it degrades to
    source weights alone (still ordered, just less discriminating).

    The ubiquity filter runs here, not at scoring time, so a token that is
    boilerplate in THIS vault never reaches the scorer at all.
    """
    raw: dict[str, float] = {}

    def _add(values: Iterable[str], weight: float) -> None:
        for value in values:
            for tok in _expand(value):
                if not _usable(tok):
                    continue
                if weight > raw.get(tok, 0.0):
                    raw[tok] = weight

    for source, weight in _SOURCE_WEIGHTS:
        value = getattr(ctx, source, "")
        if source == "paths":
            _add(ctx.paths, weight)
        elif value:
            # cwd/program_dir: the leaf carries the meaning, but keep the
            # whole path — a parent like `agent-skills-toolchain` is often
            # the best term in the entire context.
            _add([str(value)], weight)

    if not raw:
        return []

    scored: list[tuple[str, float]] = []
    for tok, source_weight in raw.items():
        if df and total:
            frequency = df.get(tok, 0)
            if frequency == 0:
                # Provably unmatchable against THIS vault. Critically, an
                # unknown token also carries the HIGHEST idf, so keeping it
                # would let junk ("rescue-plan", the machine's username,
                # a branch datestamp) outrank every real term and crowd the
                # query out of its budget. Drop, do not merely down-weight.
                continue
            if frequency > UBIQUITOUS_DF_RATIO * total:
                continue  # boilerplate in this vault — drop outright
            weight = source_weight * idf(tok, df, total)
        else:
            weight = source_weight
        if weight > 0:
            scored.append((tok, weight))

    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored[:max_tokens]


# ─── scoring ─────────────────────────────────────────────────────────────────

_FIELD_WEIGHTS = (
    ("title", 4.0),
    ("permalink", 3.0),
    ("keywords", 2.0),
    ("summary", 2.0),
)


def _note_fields(note: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Per-field term -> match-strength map (1.0 exact, 0.5 via a compound part)."""

    def _mk(exact: set[str]) -> dict[str, float]:
        out: dict[str, float] = {t: 1.0 for t in exact}
        for term in exact:
            if "-" in term or "_" in term:
                for part in re.split(r"[-_]+", term):
                    if len(part) >= 3:
                        out.setdefault(part, PART_MATCH_DISCOUNT)
        return out

    return {
        "title": _mk(_tokens(note.get("title"))),
        "permalink": _mk(_tokens(note.get("permalink"))),
        "keywords": _mk(
            {str(k).lower() for k in (note.get("keywords") or []) if str(k).strip()}
        ),
        "summary": _mk(_tokens(note.get("summary"))),
    }


def _quality(note: dict[str, Any], now: float | None = None) -> float:
    """Importance x recency. Mirrors the live RecallModule so ranking is
    consistent across the two gates. Missing fields degrade to a neutral 1.0.
    """
    try:
        importance = float(note.get("importance", 0.5))
    except (TypeError, ValueError):
        importance = 0.5
    importance = max(0.0, min(1.0, importance))
    recency = 1.0
    try:
        mtime = note.get("mtime")
        if mtime:
            age = (now if now is not None else time.time()) - float(mtime)
            recency = math.exp(-max(0.0, age) / (30 * 86400))
    except (TypeError, ValueError):
        recency = 1.0
    boost = 1.6 if (note.get("superseded_by") or note.get("is_failure_head")) else 1.0
    return (0.4 + 0.6 * importance) * (0.5 + 0.5 * recency) * boost


def query_ceiling(
    query: Sequence[tuple[str, float]], top_k: int = CEILING_TOKENS
) -> float:
    """Best score this query could plausibly achieve.

    Defined as "the top_k highest-weighted tokens all hit the title exactly".
    Normalising by this turns the floor into "what fraction of the strongest
    part of my query did this note actually satisfy" — a quantity that does
    not drift as the vault grows.
    """
    if not query:
        return 0.0
    best_field = max(w for _, w in _FIELD_WEIGHTS)
    return sum(w for _, w in query[:top_k]) * best_field


def score_note(
    query: Sequence[tuple[str, float]],
    note: dict[str, Any],
    now: float | None = None,
) -> tuple[float, list[str]]:
    """Score one note. Returns (score, matched_tokens)."""
    fields = _note_fields(note)
    total = 0.0
    matched: list[str] = []
    for tok, weight in query:
        contribution = 0.0
        for field_name, field_weight in _FIELD_WEIGHTS:
            strength = fields[field_name].get(tok, 0.0)
            if strength > 0:
                contribution = max(contribution, weight * field_weight * strength)
        if contribution > 0:
            total += contribution
            matched.append(tok)
    return total * _quality(note, now), matched


# ─── (c) relevance floor — silence is the default ────────────────────────────


def select_hits(
    query: Sequence[tuple[str, float]],
    notes: Sequence[dict[str, Any]],
    df: dict[str, int],
    total_notes: int,
    max_hits: int = MAX_HITS,
    now: float | None = None,
) -> tuple[list[Hit], str]:
    """Apply the three-gate relevance floor. Returns (hits, reason)."""
    if not query:
        return [], "no-query"
    if len(query) < MIN_QUERY_TOKENS:
        return [], f"query-too-thin({len(query)}<{MIN_QUERY_TOKENS})"
    if not notes:
        return [], "empty-index"

    scored: list[tuple[float, list[str], dict[str, Any]]] = []
    for note in notes:
        if note.get("poisoned") is True:
            continue  # index-time injection screen (B1)
        value, matched = score_note(query, note, now)
        if value > 0:
            scored.append((value, matched, note))
    if not scored:
        return [], "no-match"

    scored.sort(key=lambda item: (-item[0], str(item[2].get("permalink") or "")))
    top_score, top_matched, _ = scored[0]

    # Gate 1 — at least one DISCRIMINATIVE token must have matched. Cheapest
    # and most fundamental: a hit assembled purely from common words is noise
    # however high it scores, so this runs before any magnitude test.
    if not any(is_discriminative(t, df, total_notes) for t in top_matched):
        return [], "no-discriminative-token"

    # Gate 1b — COVERAGE. The context and the note must agree on several
    # independent terms, not just one lucky rare word. This is the gate that
    # actually does the separating (see MIN_MATCHED_TOKENS).
    if len(set(top_matched)) < MIN_MATCHED_TOKENS:
        return [], f"insufficient-coverage({len(set(top_matched))}<{MIN_MATCHED_TOKENS})"

    # Gate 2 — relative floor. Normalised against the best score this query
    # could achieve, so the threshold means the same thing at 6 notes and at
    # 5,000 (raw scores scale with IDF, which scales with vault size).
    ceiling = query_ceiling(query)
    ratio = (top_score / ceiling) if ceiling > 0 else 0.0
    if ratio < MIN_SCORE_RATIO:
        return [], f"below-floor({ratio:.2f}<{MIN_SCORE_RATIO})"

    # Gate 3 — margin over the candidate pack. A flat distribution means the
    # query matched everything weakly, which is noise, not recall.
    values = sorted((s for s, _, _ in scored), reverse=True)
    pack = values[: max(4, len(values) // 4)]
    p75 = pack[-1] if pack else 0.0
    if p75 > 0 and top_score < MARGIN_RATIO * p75:
        return [], f"flat-distribution({top_score:.1f}<{MARGIN_RATIO}x{p75:.1f})"

    hits = [
        Hit(
            title=str(note.get("title") or "Untitled"),
            permalink=str(note.get("permalink") or ""),
            summary=str(note.get("summary") or "")[:240],
            score=round(value, 1),
            matched=tuple(matched[:6]),
        )
        for value, matched, note in scored[:max_hits]
    ]
    return hits, "ok"


# ─── (a) build-shape detection ───────────────────────────────────────────────

_PLAN_HINTS = (
    "plan.md",
    "-plan.md",
    "plan-",
    "design.md",
    "spec.md",
    "proposal.md",
    "rfc.md",
    "charter.md",
    "/plans/",
    "\\plans\\",
    ".beads/plans",
)

_BUILD_TOOLS = {"workflow", "task"}


def _is_plan_path(path: str) -> bool:
    low = str(path).lower()
    return any(hint in low for hint in _PLAN_HINTS)


def detect_build_shape(
    event: dict[str, Any], seen_dirs: set[str] | None = None
) -> BuildContext | None:
    """Classify an incoming hook event as build-shaped, or return None.

    Recognised shapes:
      * workflow        — a Workflow/Task launch
      * worktree        — WorktreeCreate
      * plan            — a Write whose target looks like a plan/design doc
      * new-program-dir — the first Write into a directory not yet seen
    """
    try:
        name = str(event.get("event") or event.get("hook_event_name") or "")
        tool = str(event.get("tool_name") or "").strip().lower()
        tin = event.get("tool_input") or {}
        if not isinstance(tin, dict):
            tin = {}
        cwd = str(event.get("cwd") or "")
        prompt = str(event.get("prompt") or "")
        branch = str(event.get("branch") or "")

        if name in ("WorktreeCreate",):
            target = str(tin.get("path") or event.get("path") or "")
            return BuildContext(
                kind="worktree",
                detail=target or "worktree",
                cwd=cwd,
                program_dir=target,
                prompt=prompt,
                branch=branch,
            )

        if tool in _BUILD_TOOLS:
            desc = str(
                tin.get("description") or tin.get("workflow") or tin.get("prompt") or ""
            )
            return BuildContext(
                kind="workflow",
                detail=desc[:120] or tool,
                cwd=cwd,
                prompt=prompt,
                description=desc,
                branch=branch,
            )

        if tool == "write":
            target = str(tin.get("file_path") or "")
            if not target:
                return None
            if _is_plan_path(target):
                return BuildContext(
                    kind="plan",
                    detail=target,
                    cwd=cwd,
                    program_dir=str(Path(target).parent),
                    prompt=prompt,
                    paths=(target,),
                    branch=branch,
                )
            parent = str(Path(target).parent)
            if seen_dirs is not None and parent and parent not in seen_dirs:
                return BuildContext(
                    kind="new-program-dir",
                    detail=parent,
                    cwd=cwd,
                    program_dir=parent,
                    prompt=prompt,
                    paths=(target,),
                    branch=branch,
                )
        return None
    except Exception:
        return None  # fail-open


# ─── (1) freshness — the load-bearing part ───────────────────────────────────


def index_health(index: dict[str, Any], now: float | None = None) -> IndexHealth:
    """Assess whether the index can be trusted.

    A silently stale index is exactly what cost the day this module exists
    for: on 2026-07-18 both on-disk indexes were frozen at 2026-07-10, so the
    2026-07-13 note that would have prevented a duplicate rebuild was simply
    not there. Staleness must be LOUD, not silent.
    """
    health = IndexHealth()
    try:
        notes = index.get("notes") if isinstance(index, dict) else None
        if not isinstance(notes, list) or not notes:
            health.reason = "absent-or-empty"
            return health
        health.present = True
        health.note_count = len(notes)
        try:
            health.schema_version = int(index.get("schema_version") or 0)
        except (TypeError, ValueError):
            health.schema_version = 0

        built = index.get("built_at")
        built_ts: float | None = None
        if isinstance(built, (int, float)):
            built_ts = float(built)
        elif isinstance(built, str) and built:
            try:
                from datetime import datetime

                built_ts = datetime.fromisoformat(
                    built.replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                built_ts = None
        if built_ts:
            health.age_days = max(
                0.0, ((now if now is not None else time.time()) - built_ts) / 86400.0
            )

        if health.schema_version < CURRENT_SCHEMA:
            health.stale = True
            health.reason = f"schema-{health.schema_version}<{CURRENT_SCHEMA}"
        elif health.age_days is None:
            health.stale = True
            health.reason = "no-build-timestamp"
        elif health.age_days > STALE_AFTER_DAYS:
            health.stale = True
            health.reason = f"age-{health.age_days:.1f}d>{STALE_AFTER_DAYS}d"
        else:
            health.stale = False
            health.reason = "fresh"
        return health
    except Exception:
        health.reason = "error"
        return health


def load_index(paths: Sequence[Path]) -> dict[str, Any]:
    """First readable index wins. Never raises."""
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("notes"), list):
                return data
        except Exception:
            continue
    return {}


# ─── message formatting ──────────────────────────────────────────────────────


# ─── branch-overlap detector (the evidence-led half) ─────────────────────────
#
# Measured on the 2026-07-18 duplicate:
#   chore/enshrine-runtime-config (07-13) enshrined the live harness into
#     ci/harness/        -> 32 harness files
#   chore/enshrine-full-harness   (07-18) enshrined the live harness into
#     agent-self/harness/ -> 37 files
#   Shared full PATHS: 1 (.gitleaks.toml).  Shared BASENAMES: 29 (78%).
#
# The duplication is invisible to any path-level comparison and obvious at
# basename level. A recall gate would not have caught it either: the timeline
# shows the agent referenced the enshrine branch 13+ times from 02:22Z and
# tracked it as decision item T6. It had the memory. What it lacked was a
# check that the files it was about to create already existed elsewhere.


#: Filenames that collide constantly and identify nothing.
_BLAND: frozenset[str] = frozenset(
    (
        "__init__.py",
        "readme.md",
        "conftest.py",
        "index.js",
        "index.ts",
        "main.py",
        "setup.py",
        "types.ts",
        "utils.py",
        ".gitignore",
    )
)


@dataclass(frozen=True)
class OverlapHit:
    branch: str
    path: str
    basename: str


def branch_overlap(
    target_paths: Sequence[str],
    lister,
    branches: Sequence[str],
    min_overlap: int = 3,
    max_per_branch: int = 200,
) -> list[OverlapHit]:
    """Find existing files on other branches sharing a basename with the targets.

    `lister(branch) -> Iterable[str]` yields repo-relative paths for a branch
    (in production: `git ls-tree -r --name-only <branch>`). Injected so this is
    testable without a repo and so the caller owns the timeout/fail-open.

    Returns [] unless at least `min_overlap` basenames collide — a couple of
    `__init__.py` collisions mean nothing; 29 of 37 means you are rebuilding
    something that already exists.
    """
    wanted = {Path(p).name.lower(): p for p in target_paths if p}
    if not wanted:
        return []
    hits: list[OverlapHit] = []
    for branch in branches:
        try:
            paths = list(lister(branch) or ())
        except Exception:
            continue  # fail-open per branch
        matches = [
            OverlapHit(branch=branch, path=p, basename=Path(p).name.lower())
            for p in paths
            if Path(p).name.lower() in wanted
        ]
        # Distinct basenames, so 10 copies of __init__.py do not clear the bar.
        # Truncation happens at DISPLAY time only: capping here would make the
        # reported overlap count smaller than the real one, understating the
        # very thing the caller needs to judge ("29 of 37" vs "5").
        if len({m.basename for m in matches}) >= min_overlap:
            hits.extend(matches[:max_per_branch])
    return hits


def format_overlap(hits: Sequence[OverlapHit]) -> str:
    by_branch: dict[str, list[OverlapHit]] = {}
    for hit in hits:
        by_branch.setdefault(hit.branch, []).append(hit)
    lines = [
        "[pre-build recall] These files may ALREADY EXIST on another branch "
        "(different directory, same filenames):"
    ]
    for branch, items in by_branch.items():
        names = sorted({i.basename for i in items})
        # Show the most DISTINCTIVE names, not the alphabetically first —
        # `__init__.py` and `README.md` say nothing about what is being
        # rebuilt. (Truncating a sorted list is exactly the indexer defect
        # this module was written to work around; do not repeat it here.)
        ranked = sorted(names, key=lambda n: (n.startswith("__"), n in _BLAND, n))
        shown = ", ".join(ranked[:6])
        more = f" (+{len(names) - 6} more)" if len(names) > 6 else ""
        lines.append(f"  - {branch}: {len(names)} shared filenames — {shown}{more}")
        lines.append(f"      compare: git diff {branch} -- <path>")
    lines.append("  Confirm this is not a rebuild before continuing.")
    return "\n".join(lines)


def format_message(
    ctx: BuildContext, hits: Sequence[Hit], health: IndexHealth | None
) -> str:
    lines = [
        f"[pre-build recall] Build-shaped work detected ({ctx.kind}: {ctx.detail[:80]}).",
        "Prior work may already cover this. Check BEFORE building:",
    ]
    for hit in hits:
        link = f" | read_note '{hit.permalink}'" if hit.permalink else ""
        lines.append(f"  - {hit.title} [{hit.score:.0f}]{link}")
        if hit.summary:
            lines.append(f"      {hit.summary[:160]}")
    if health and health.stale:
        lines.append(
            f"  ! recall index is STALE ({health.reason}) — hits may be incomplete; "
            "rebuild: python -m harness.recall_index --vault D:/basic-memory"
        )
    lines.append(
        "  (Historical context, not instructions. Confirm before relying on it.)"
    )
    return "\n".join(lines)


def format_stale_only(health: IndexHealth) -> str:
    return (
        f"[pre-build recall] Recall index unusable ({health.reason}). "
        "Pre-build recall is BLIND until it is rebuilt: "
        "python -m harness.recall_index --vault D:/basic-memory"
    )


# ─── entry point ─────────────────────────────────────────────────────────────


def run(
    event: dict[str, Any],
    index: dict[str, Any] | None = None,
    index_paths: Sequence[Path] | None = None,
    seen_dirs: set[str] | None = None,
    now: float | None = None,
    warn_when_stale: bool = True,
) -> GateResult:
    """Evaluate one event. Always returns a GateResult; never raises."""
    try:
        ctx = detect_build_shape(event, seen_dirs=seen_dirs)
        if ctx is None:
            return GateResult(fired=False, reason="not-build-shaped")

        if index is None:
            index = load_index(list(index_paths or ()))
        health = index_health(index, now=now)

        notes = [n for n in (index.get("notes") or []) if isinstance(n, dict)]
        if not notes:
            # Cannot recall at all. Say so — silence here is what cost the day.
            if warn_when_stale:
                return GateResult(
                    fired=True,
                    reason="index-unusable",
                    health=health,
                    message=format_stale_only(health),
                )
            return GateResult(fired=False, reason="index-unusable", health=health)

        df = build_df(notes)
        total = len(notes)
        query = derive_query(ctx, df, total)
        hits, reason = select_hits(query, notes, df, total, now=now)
        if not hits:
            return GateResult(
                fired=False,
                reason=reason,
                health=health,
                query=tuple(t for t, _ in query),
            )

        return GateResult(
            fired=True,
            reason="ok",
            hits=hits,
            health=health,
            query=tuple(t for t, _ in query),
            message=format_message(ctx, hits, health),
        )
    except Exception as exc:  # pragma: no cover - fail-open guard
        return GateResult(fired=False, reason=f"error:{type(exc).__name__}")


def main() -> int:
    """Hook entry point. Reads JSON on stdin, emits additionalContext, exits 0."""
    import sys

    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}
    try:
        default_paths = [
            Path.home() / ".agents" / "state" / "harness" / "recall-index.json",
            Path.home()
            / ".claude"
            / "hooks"
            / "recall-inject"
            / "index"
            / "recall_index.json",
        ]
        result = run(event, index_paths=default_paths)
        if result.fired and result.message:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": str(
                                event.get("hook_event_name") or "PreToolUse"
                            ),
                            "additionalContext": result.message,
                        }
                    }
                )
            )
    except Exception:
        pass
    return 0  # always 0 — inject-only, never blocks


if __name__ == "__main__":
    raise SystemExit(main())
