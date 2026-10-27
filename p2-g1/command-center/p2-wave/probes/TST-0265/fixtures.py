"""TST-0265 probe fixtures: planted mutant classes, blind class, distinct-100.

Mutant classes mirror the receipt: exact_rename, single_word_swap,
full_rewrite_paraphrase must FIRE; oov_deep_paraphrase is the declared blind
class and must stay SILENT. distinct-100 is generated from three 100-entry
word tables so every pair shares only template tokens (pairwise raw Jaccard
~0.2, distinct folded keys).
"""
from __future__ import annotations

MUTANT_PAIRS: dict[str, tuple[str, str]] = {
    "exact_rename": (
        "Reattempt the failed request with exponential backoff",
        "Retry the failed request with exponential backoff",
    ),
    "single_word_swap": (
        "Cache the response for a 30 ms TTL",
        "Cache the response for a 30 ms timeout",
    ),
    "full_rewrite_paraphrase": (
        "keep the result in a cache behind the failed request",
        "put the result into a cache under the unsuccessful request",
    ),
}

BLIND_PAIR: tuple[str, str] = (
    "Retry the failed request with exponential backoff",
    "Schedule a fresh exponential wait after every rejection",
)

_DOMAINS = [
    "ingest", "render", "audit", "billing", "auth", "search", "storage",
    "notify", "scheduling", "logging", "queue", "docs", "tests", "build",
    "release", "telemetry", "quota", "parsing", "encoding", "serialization",
    "crypto", "network", "memory", "disk", "cli", "sdk", "export", "import",
    "sync", "batch", "stream", "index", "query", "schema", "migration",
    "rollback", "deploy", "alert", "dashboard", "report", "ledger", "graph",
    "topology", "partition", "shard", "replica", "failover", "backup",
    "restore", "archive", "compress", "encrypt", "session", "header",
    "proxy", "gateway", "router", "filter", "mapper", "reducer", "validator",
    "normalizer", "compiler", "scheduler", "executor", "worker", "runner",
    "watcher", "scanner", "linter", "formatter", "bundler", "packager",
    "publisher", "subscriber", "broker", "relay", "bridge", "adapter",
    "connector", "gatewayx", "routex", "filterx", "mapperx", "reducerx",
    "validatorx", "compilerx", "schedulerx", "executorx", "workerx",
    "runnerx", "watcherx", "scannerx", "linterx", "formatterx", "bundlerx",
    "packagerx", "publisherx", "subscriberx", "brokerx", "relayx",
]

_VERBS = [
    "debounce", "version", "fingerprint", "checkpoint", "splice", "prune",
    "graft", "mirror", "widen", "narrow", "invert", "flatten", "nest",
    "bubble", "cascade", "stage", "promote", "demote", "quarantine",
    "sample", "throttle", "amplify", "dampen", "offset", "anchor", "float",
    "pin", "rotate", "scramble", "shuffle", "bucket", "stamp", "seal",
    "wrap", "unwrap", "peel", "fold", "unfold", "braid", "weave", "knot",
    "fuse", "split", "shatter", "meld", "anneal", "temper", "quench",
    "etch", "engrave", "outline", "sketch", "trace", "chart", "grid",
    "pivot", "hinge", "swivel", "glide", "hop", "march", "crawl", "sprint",
    "pace", "ramp", "plateau", "cliff", "slope", "orbit", "parallax",
    "zoom", "pan", "tilt", "dolly", "fade", "dissolve", "loop", "ping",
    "echo", "reverb", "tune", "detune", "pitch", "yaw", "roll", "heave",
    "sway", "drag", "lift", "sink", "buoy", "mull", "mend", "trim", "tend",
    "cope", "cull", "curb", "damp", "eave", "gable",
]

_CONS = "bcdfgklmnprstvz"
_VOWELS = "aeiou"


def _suffixes() -> list[str]:
    """100 guaranteed-distinct suffix names (two syllable series)."""
    series_a = [c + v for c in _CONS for v in _VOWELS]
    series_b = [v + c for v in _VOWELS for c in _CONS]
    names = series_a + series_b
    seen, out = set(), []
    for nm in names:
        if nm not in seen:
            seen.add(nm)
            out.append(nm)
    return out[:100]


def distinct_100() -> list[str]:
    """100 genuinely distinct mechanism sentences (pairwise Jaccard < 0.5)."""
    suff = _suffixes()
    out = []
    for i in range(100):
        out.append(f"As {_DOMAINS[i]} work, {_VERBS[i]} the {suff[i]} lane.")
    return out


def gaming_pad_100() -> list[str]:
    """A cast instructed to pad to 100: trivial wording variants of ONE idea."""
    bases = [
        "retry the failed request with backoff",
        "reattempt the unsuccessful call with waits",
        "rerun the rejected task using delays",
    ]
    out = []
    for i in range(100):
        out.append(f"{bases[i % 3]} variant {i}")
    return out
