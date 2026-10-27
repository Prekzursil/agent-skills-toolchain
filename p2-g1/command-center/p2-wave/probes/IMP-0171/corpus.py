"""IMP-0171 corpus: one seed workflow doc plus 5x5 planted mutants and controls.

Classes:
  exact_rename      same body, workflow renamed           -> high band
  paraphrase        same body, light rewording             -> high band
  one_parameter_fork same body, one parameter changed      -> high band
  full_rewrite      same workflow name, new body           -> low band (lexical blind spot)
  known_distinct    genuinely different workflows          -> low band

Deterministic: every doc is composed from fixed strings, no randomness.
"""

SEED_NAME = "seed-harbor-review-gate"
DISTINCT_NAMES = [
    "distinct-kiln-sign-pipeline",
    "distinct-quay-tide-scheduler",
    "distinct-mast-ledger-closer",
    "distinct-berth-crane-balancer",
    "distinct-hull-inspection-loop",
]

_GLYPHS = ["alpha", "bravo", "charlie", "delta", "echo"]

SEED = """workflow seed-harbor-review-gate nightly gate for harbor review receipts
stages fetch receipts from the harbor bucket then validate each receipt against the schema
then emit the summary index then reconcile the digest with the ledger then record the run
stage one fetch harbor receipts limit 500 timeout 300 retries 3 artifact receipts jsonl
stage two validate receipts against harbor receipt schema strict fields id hash source time
stage three emit summary index counts per source per class and per gate verdict
stage four reconcile emitted digest against the harbor ledger and refuse on drift
stage five record the run with the digest the band and the review verdict then exit
roles scout reads receipts validator checks schema reconciler diffs digests
reviewer verifies the review verdict and signs the run before the gate closes
gates quality gate passes when every receipt hash reproduces and drift is zero
stopping rule stop when all receipts validated and digest reconciled cleanly
on failure refuse the run and keep the previous index untouched and alert the owner
"""


def _exact_rename(i: int) -> str:
    name = f"shore-harbor-review-gate-{_GLYPHS[i]}"
    return SEED.replace("seed", name.split("-")[0], 1).replace(
        "workflow seed-harbor-review-gate", f"workflow {name}", 1
    ) + f"\nvariant exact rename {_GLYPHS[i]}\n"


def _paraphrase(i: int) -> str:
    swaps = [
        ("nightly gate for harbor review receipts", "every night gate on harbor review receipts"),
        ("fetch receipts from the harbor bucket", "pull receipts out of the harbor bucket"),
        ("validate each receipt against the schema", "check every receipt against the schema"),
        ("emit the summary index", "write out the summary index"),
        ("refuse on drift", "stop on drift"),
        ("alert the owner", "page the owner"),
        ("signs the run", "countersigns the run"),
    ]
    out = SEED
    ordered = swaps[i % len(swaps):] + swaps[: i % len(swaps)]
    for a, b in ordered[:2]:  # two light rewordings: stays in the high band
        if a in out:
            out = out.replace(a, b, 1)
    return out + f"\nvariant paraphrase {_GLYPHS[i]}\n"


def _one_parameter_fork(i: int) -> str:
    out = SEED.replace("limit 500 timeout 300 retries 3",
                       f"limit {500 + i} timeout {300 + 60 * (i + 1)} retries {3 + i % 3}")
    return out + f"\nvariant one parameter fork {_GLYPHS[i]}\n"


def _full_rewrite(i: int) -> str:
    body = (f"workflow {SEED_NAME} rewritten from a blank page variant {_GLYPHS[i]}\n"
            f"a single observer polls the queue then batches the delta then compacts the store\n"
            f"compaction keeps the newest shard prunes the cold tier and rotates the key\n"
            f"the observer signs each batch with a fresh nonce and appends the tally\n"
            f"migration replays the changelog into the warehouse and archives the spill\n"
            f"rollback restores the snapshot then replays the journal from the trunk\n")
    return body


def _distinct(i: int) -> str:
    name = DISTINCT_NAMES[i]
    return (f"workflow {name} a separate pipeline with its own contract variant {_GLYPHS[i]}\n"
            f"the runner executes stages then review the artifact then gates the merge\n"
            f"each stage records a verdict the gate refuses when the review fails\n"
            f"rules stop when the queue drains and every artifact reconciles\n"
            f"failure keeps the previous verdict and alerts the owner before exit\n")


def classes() -> dict:
    return {
        "exact_rename": [_exact_rename(i) for i in range(5)],
        "paraphrase": [_paraphrase(i) for i in range(5)],
        "one_parameter_fork": [_one_parameter_fork(i) for i in range(5)],
        "full_rewrite": [_full_rewrite(i) for i in range(5)],
        "known_distinct": [_distinct(i) for i in range(5)],
    }


def pair_scores() -> dict:
    """Class -> list of seed-vs-doc Jaccard scores (order-stable)."""
    import lexical
    return {cls: [lexical.score_pair(SEED, doc) for doc in docs]
            for cls, docs in classes().items()}
