"""Mechanism signature derivation.

A MECHANISM is modelled as a triple:

    (verb_set, locus, artifact_set)

    verb_set     -- WHAT the record does, canonicalised through a synonym table so that
                    "carry every other group through untouched" and "per-event merge" both
                    reduce to {MERGE}.
    locus        -- WHERE the change lands (installer / dispatcher / council / ...).
    artifact_set -- WHICH concrete named things it operates on.  Split into
                    hard_artifacts (file paths, code identifiers, config keys -- strong
                    evidence) and soft_concepts (controlled-vocabulary domain nouns --
                    weak evidence, used only when no hard artifact is named).

This is deliberately LEXICAL-OVER-A-CONTROLLED-VOCABULARY, not semantic.  Two consequences
are disclosed rather than hidden:
  * it under-merges paraphrases that share no vocabulary token (measured recall below 1.0);
  * it never merges on wording alone, because wording that carries no verb+locus+artifact
    agreement produces no match.
The measured recall/precision against the corpus's own authored dedup ledger is emitted by
`dedup.validate()` -- no claim here is made without that measurement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------------------
# verb classes -- canonical operation vocabulary
# --------------------------------------------------------------------------------------
# Order matters only for tie-breaking the "principal" verb; membership is a set.
VERB_CLASSES: dict[str, tuple[str, ...]] = {
    "MERGE": (
        "merge",
        "merge-not-replace",
        "carried through",
        "carry through",
        "carry every",
        "preserve",
        "per-group",
        "per-event merge",
        "union",
        "additive",
        "add and update",
        "non-destructive",
        "coexist",
        "splice",
    ),
    "REPLACE": (
        "replace",
        "overwrite",
        "swap",
        "cut over",
        "cutover",
        "supersede",
        "rewrite",
        "whole-key assignment",
        "regenerate",
        "reassign",
        "in place of",
    ),
    "DELETE": (
        "delete",
        "prune",
        "remove",
        "retire",
        "tombstone",
        "garbage collect",
        " gc ",
        "uninstall",
        "purge",
        "quarantine the",
        "drop",
    ),
    "GATE": (
        "gate",
        "block",
        "fail-closed",
        "fail closed",
        "refuse",
        "require",
        "enforce",
        "must fail",
        "reject",
        "veto",
        "deny",
        "threshold",
        "floor",
        "predicate",
        "precondition",
        "lint error",
        "barrier",
        "quorum",
        "stopping rule",
        "stop when",
    ),
    "OBSERVE": (
        "observe",
        "record",
        "log ",
        "logs",
        "ledger",
        "emit",
        "receipt",
        "telemetry",
        "metric",
        "measure",
        "count",
        "score",
        "report",
        "surface",
        "append-only",
        "journal",
        "audit trail",
        "accounting",
        "histogram",
    ),
    "PROBE": (
        "probe",
        "test",
        "assert",
        "verify",
        "both-states",
        "both states",
        "mutation",
        "detector control",
        "control =",
        "negative control",
        "reproduc",
        "red today",
        "green after",
        "settling experiment",
        "falsif",
        "self-test",
        "smoke",
    ),
    "DECLARE": (
        "declare",
        "declarative",
        "schema",
        "typed",
        "contract",
        "manifest",
        "spec",
        " ir ",
        "dsl",
        "registry",
        "frontmatter",
        "as data",
        "single source of truth",
        "vocabulary",
        "taxonomy",
        "charter",
        "descriptor",
        "field",
        "yaml",
        "json-schema",
    ),
    "ROUTE": (
        "route",
        "dispatch",
        "escalate",
        "select",
        "rank",
        "rerank",
        "choose",
        "tier",
        "governor",
        "adapter",
        "fallback",
        "delegate",
        "assign",
        "seat",
        "bind",
        "activation",
        "lazy",
        "gateway",
        "load only",
    ),
    "CACHE": (
        "cache",
        "content-address",
        "content address",
        "checkpoint",
        "resume",
        "snapshot",
        "pin",
        "freeze",
        "immutable",
        "digest",
        "hash",
        "memoi",
        "prefix stable",
    ),
    "ISOLATE": (
        "isolate",
        "sandbox",
        "least-privilege",
        "least privilege",
        "scope to",
        "worktree",
        "no-network",
        "air-gap",
        "confine",
        "read-only",
    ),
    "INDEX": (
        "index",
        "search",
        "catalogue",
        "catalog",
        "discover",
        "corpus",
        "dedup",
        "duplicate_of",
        "cluster",
        "distil",
        "consolidat",
        "salvage",
        "archaeolog",
        "faceted",
        "lexical",
    ),
    "SYNC": (
        "sync",
        "reconcile",
        "mirror",
        "deploy",
        "install",
        "version-control",
        "version control",
        "upstream",
        "drift",
        "propagate",
        "publish",
        "release",
    ),
    "PROVENANCE": (
        "provenance",
        "lineage",
        "source probe",
        "source_probe",
        "attribut",
        "capsule",
        "resolved ref",
        "traceab",
        "chain of custody",
        "citation",
        "anchor",
    ),
    "DELIBERATE": (
        "deliberat",
        "debate",
        "council",
        "panel",
        "vote",
        "voting",
        "dissent",
        "consensus",
        "round-robin",
        "devil",
        "adversarial collaboration",
        "cross-examin",
        "moderat",
        "chair",
    ),
    "RECOVER": (
        "recover",
        "rollback",
        "retry",
        "relaunch",
        "self-heal",
        "restart",
        "backoff",
        "back off",
        "poison",
        "requeue",
        "work steal",
        "resume from",
    ),
}

# --------------------------------------------------------------------------------------
# locus -- where the change lands
# --------------------------------------------------------------------------------------
LOCI: dict[str, tuple[str, ...]] = {
    "installer": (
        "install.py",
        "installer",
        "--bootstrap",
        "--deploy",
        "build_hooks",
        "registration.py",
    ),
    "hook-dispatch": (
        "dispatch.py",
        "_dispatch",
        "hook",
        "pretooluse",
        "posttooluse",
        "sessionstart",
        "stopfailure",
        "sessionend",
        "dispatcher",
    ),
    "settings-registration": (
        "settings.json",
        "registration",
        "hooks key",
        "managedby",
        "groupid",
        "events tuple",
        "matcher",
    ),
    "marketplace-plugins": (
        "marketplace",
        "plugin",
        "catalogue",
        "cache/",
        "installed.json",
        "enabledplugins",
    ),
    "workflow-runtime": (
        "workflow",
        "agent()",
        "parallel()",
        "phase()",
        "fan-out",
        "fanout",
        "work unit",
        "work-unit",
        "stage",
        "blueprint",
        "pipeline",
    ),
    "council": (
        "council",
        "seat",
        "protocol",
        "preset",
        "vote",
        "quorum",
        "panel",
        "chair",
    ),
    "evidence-gates": (
        "gate",
        "verdict",
        "evidence",
        "receipt",
        "claim-verify",
        "predicate",
        "no-regression",
        "inv-",
        "coverage",
        "mutation",
    ),
    "corpus-claims": (
        "claim",
        "corpus",
        "dedup",
        "duplicate_of",
        "index",
        "record",
        "provenance",
        "unknown register",
    ),
    "routing-models": (
        "model",
        "vendor",
        "codex",
        "opus",
        "sonnet",
        "router",
        "budget",
        "quota",
        "token",
        "cost",
    ),
    "recall-memory": (
        "basic-memory",
        "basic_memory",
        "recall",
        "memory",
        "now.md",
        "compaction",
        "note.py",
        "ledger.py",
        "event-ledger",
    ),
    "daemon-scheduler": (
        "scheduled task",
        "schtask",
        "supervisor",
        "daemon",
        "agent-mail",
        "8812",
        "memguard",
        "ram-keeper",
        "ramkeeper",
        "listener",
    ),
    "security-credentials": (
        "credential",
        "secret",
        "token",
        "deny",
        "git-crypt",
        "redact",
        "permission",
        "junction",
        "crcp",
        "force-push",
    ),
    "vcs-repo": (
        "git",
        "commit",
        "branch",
        "pr ",
        "pull request",
        "repo",
        "worktree",
        "main-mirror",
        "upstream",
        "sync-from-live",
    ),
    "observability": (
        "cockpit",
        "monitor",
        "dashboard",
        "statusline",
        "hud",
        "benchmark",
        "metrics",
    ),
    "research-sources": (
        "research",
        "source",
        "citation",
        "paper",
        "web",
        "search",
        "multilingual",
        "domain allow",
    ),
    "skills-rules": (
        "skill",
        "skill.md",
        "rule",
        "agents.md",
        "claude.md",
        "frontmatter",
        "always-on",
        "router",
    ),
}

# --------------------------------------------------------------------------------------
# soft concept vocabulary (used only when no hard artifact is named)
# --------------------------------------------------------------------------------------
SOFT_CONCEPTS: tuple[str, ...] = (
    "registration group",
    "hook group",
    "event name",
    "receipt",
    "digest",
    "artifact",
    "manifest",
    "schema",
    "predicate",
    "invariant",
    "detector",
    "control",
    "mutation",
    "seat",
    "role",
    "round",
    "vote",
    "quorum",
    "dissent",
    "stopping rule",
    "budget",
    "work unit",
    "fan-out",
    "barrier",
    "claim",
    "mechanism",
    "duplicate",
    "provenance",
    "confidence band",
    "verdict",
    "severity",
    "corpus",
    "index",
    "cache",
    "checkpoint",
    "rollback",
    "backup",
    "quarantine",
    "junction",
    "credential",
    "secret",
    "guard",
    "gate",
    "ladder",
    "shadow mode",
    "promotion",
    "demotion",
    "drift",
    "reconcile",
    "deploy",
    "release",
    "channel",
    "marketplace",
    "plugin",
    "skill",
    "rule",
    "router",
    "activation",
    "model floor",
    "vendor",
    "cost tier",
    "quota",
    "escalation",
)

_RE_PATH = re.compile(
    r"\b((?:[\w.@-]+/)*[\w.@-]+\.(?:py|json|md|mjs|js|ps1|sh|yaml|yml|toml|cmd|pyz))\b"
)
_RE_BACKTICK = re.compile(r"`([^`\n]{2,60})`")
_RE_CONST = re.compile(r"\b([A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)+)\b")
_RE_CAMEL_KEY = re.compile(r'"([a-z][a-zA-Z]{3,})"')
_RE_DOTTED = re.compile(r"\b([a-z_]{3,}\.[a-z_]{2,}(?:\.[a-z_]{2,})*)\b")
_STOP_ARTIFACT = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "not",
    "is",
    "it",
    "this",
    "that",
    "e.g",
    "i.e",
    "etc",
    "vs",
    "per",
    "into",
    "from",
    "with",
    "for",
}


def _tokens_lower(s: str) -> str:
    return " " + re.sub(r"\s+", " ", (s or "").lower()) + " "


def hard_artifacts(text: str) -> set[str]:
    """Concrete named things: file paths, backticked identifiers, CONSTANTS, json keys."""
    out: set[str] = set()
    for m in _RE_PATH.finditer(text or ""):
        out.add(m.group(1).lower().lstrip("./"))
    for m in _RE_BACKTICK.finditer(text or ""):
        tok = m.group(1).strip()
        # keep only identifier-ish / path-ish backtick content, drop prose in backticks
        if (
            re.fullmatch(r"[\w./:>\[\]@$-]{2,60}", tok)
            and tok.lower() not in _STOP_ARTIFACT
        ):
            out.add(tok.lower().lstrip("./"))
    for m in _RE_CONST.finditer(text or ""):
        out.add(m.group(1).lower())
    for m in _RE_CAMEL_KEY.finditer(text or ""):
        out.add(m.group(1).lower())
    for m in _RE_DOTTED.finditer(text or ""):
        out.add(m.group(1).lower())
    # a bare ``x.py`` inside a longer path is already covered; drop pure numbers
    return {a for a in out if not re.fullmatch(r"[\d.:-]+", a) and len(a) >= 3}


def soft_concepts(text: str) -> set[str]:
    low = _tokens_lower(text)
    return {c for c in SOFT_CONCEPTS if c in low}


def verb_set(text: str) -> set[str]:
    low = _tokens_lower(text)
    out = set()
    for cls, pats in VERB_CLASSES.items():
        for p in pats:
            if p in low:
                out.add(cls)
                break
    return out


def locus_scores(text: str) -> list[tuple[str, int]]:
    low = _tokens_lower(text)
    scored = [(name, sum(1 for p in pats if p in low)) for name, pats in LOCI.items()]
    scored = [(n, s) for n, s in scored if s > 0]
    scored.sort(key=lambda t: (-t[1], list(LOCI).index(t[0])))
    return scored


def locus_of(text: str) -> str:
    """Single dominant locus: the one with the most keyword hits; ties broken by declaration
    order in LOCI, which runs most-specific (installer) to least (skills-rules)."""
    s = locus_scores(text)
    return s[0][0] if s else "unknown"


def locus_top_k(text: str, k: int = 2) -> frozenset[str]:
    """The top-k scoring loci.

    Requiring the single dominant locus to be EQUAL was measured to reject 22 of the 55
    authored duplicate pairs -- the same mechanism routinely lands one keyword-hit apart
    (`vcs-repo` vs `marketplace-plugins`, `evidence-gates` vs `routing-models`).  Locus
    COMPATIBILITY (non-empty top-k intersection) is the corrected predicate.
    """
    return frozenset(n for n, _ in locus_scores(text)[:k])


@dataclass(frozen=True)
class Signature:
    verbs: frozenset[str]
    locus: str
    locus_top: frozenset[str]
    hard: frozenset[str]
    soft: frozenset[str]

    @property
    def key(self) -> str:
        v = ",".join(sorted(self.verbs)) or "-"
        h = ",".join(sorted(self.hard)[:6]) or "-"
        return f"{self.locus}|{v}|{h}"

    def as_dict(self) -> dict:
        return {
            "locus": self.locus,
            "locus_top": sorted(self.locus_top),
            "verbs": sorted(self.verbs),
            "hard_artifacts": sorted(self.hard),
            "soft_concepts": sorted(self.soft),
            "key": self.key,
        }


def signature(
    mechanism_text: str, title: str = "", problem_text: str = ""
) -> Signature:
    """Derive the mechanism signature.

    The mechanism field is the PRIMARY input.  Title is folded in because several corpus
    dialects put the mechanism's operative verb only in the heading ("Merge-not-replace hook
    installer").  The problem field is used ONLY for locus, never for verbs -- a problem
    statement describes what is broken, and folding its verbs in would merge a repair with
    the defect it repairs.
    """
    mech = mechanism_text or ""
    vt = f"{title} . {mech}"
    lt = f"{title} . {mech} . {problem_text}"
    return Signature(
        verbs=frozenset(verb_set(vt)),
        locus=locus_of(lt),
        locus_top=locus_top_k(lt, 2),
        hard=frozenset(hard_artifacts(vt)),
        soft=frozenset(soft_concepts(vt)),
    )


def jaccard(a: frozenset[str] | set[str], b: frozenset[str] | set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
