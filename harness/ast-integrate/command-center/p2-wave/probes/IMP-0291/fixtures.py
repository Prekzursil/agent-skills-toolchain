"""IMP-0291 fixtures: 40 labelled ideas, 100 wording variants, distinct control."""
from __future__ import annotations

# Eight mechanism families, five hand-written wordings each (40 total).
# Gold labels are assigned by family, not by running the canonicaliser.
LABELLED_40: tuple[tuple[str, str, str, int, str], ...] = (
    # id, family, author, round, text
    (
        "L01",
        "circuit-breaker",
        "ada",
        0,
        "Put a circuit breaker around the downstream HTTP client.",
    ),
    (
        "L02",
        "circuit-breaker",
        "ada",
        0,
        "Wrap outbound calls in a circuit breaker that opens after consecutive failures.",
    ),
    (
        "L03",
        "circuit-breaker",
        "ben",
        1,
        "Install circuit-breaker protection so a dying dependency does not cascade.",
    ),
    (
        "L04",
        "circuit-breaker",
        "ben",
        1,
        "Trip a circuit breaker when the payment vendor starts returning errors.",
    ),
    (
        "L05",
        "circuit-breaker",
        "cyd",
        2,
        "Use a circuit breaker on the search replica so timeouts do not exhaust our pool.",
    ),
    (
        "L06",
        "exponential-backoff",
        "ada",
        0,
        "Retry failed requests with exponential backoff and jitter.",
    ),
    (
        "L07",
        "exponential-backoff",
        "ada",
        0,
        "Apply exponential backoff when the rate limiter returns 429.",
    ),
    (
        "L08",
        "exponential-backoff",
        "ben",
        1,
        "Back off exponentially between retries instead of retrying immediately.",
    ),
    (
        "L09",
        "exponential-backoff",
        "ben",
        1,
        "Use jittered exponential backoff on transient transport errors.",
    ),
    (
        "L10",
        "exponential-backoff",
        "cyd",
        2,
        "Space retries with exponential backoff so we do not stampede the origin.",
    ),
    (
        "L11",
        "bulkhead-isolation",
        "ada",
        0,
        "Isolate the rendering pool behind a bulkhead so it cannot starve ingestion.",
    ),
    (
        "L12",
        "bulkhead-isolation",
        "ada",
        0,
        "Split thread pools with bulkhead isolation between interactive and batch work.",
    ),
    (
        "L13",
        "bulkhead-isolation",
        "ben",
        1,
        "Partition connection pools as bulkheads so one tenant cannot consume all sockets.",
    ),
    (
        "L14",
        "bulkhead-isolation",
        "ben",
        1,
        "Apply bulkhead isolation to the image-processing workers.",
    ),
    (
        "L15",
        "bulkhead-isolation",
        "cyd",
        2,
        "Keep a separate bulkhead of timeouts for the slow report builder.",
    ),
    (
        "L16",
        "cache-aside",
        "ada",
        0,
        "Load cache-aside: on a miss, read the database and populate Redis.",
    ),
    (
        "L17",
        "cache-aside",
        "ada",
        0,
        "Use a cache-aside pattern for session lookups.",
    ),
    (
        "L18",
        "cache-aside",
        "ben",
        1,
        "Populate the cache on miss rather than writing through on every update (cache aside).",
    ),
    (
        "L19",
        "cache-aside",
        "ben",
        1,
        "Read through cache-aside for product pages with a short TTL.",
    ),
    (
        "L20",
        "cache-aside",
        "cyd",
        2,
        "Implement cache aside so the catalog service is not hit on every storefront request.",
    ),
    (
        "L21",
        "saga-compensation",
        "ada",
        0,
        "Run the checkout as a saga with compensating transactions on failure.",
    ),
    (
        "L22",
        "saga-compensation",
        "ada",
        0,
        "Use saga compensation to undo the reservation if payment fails.",
    ),
    (
        "L23",
        "saga-compensation",
        "ben",
        1,
        "Orchestrate a saga so each step has a named compensating action.",
    ),
    (
        "L24",
        "saga-compensation",
        "ben",
        1,
        "Replace a distributed two-phase commit with a saga of compensations.",
    ),
    (
        "L25",
        "saga-compensation",
        "cyd",
        2,
        "Emit compensating events when a saga step cannot complete.",
    ),
    (
        "L26",
        "event-sourcing",
        "ada",
        0,
        "Persist order state as an append-only event-sourced log.",
    ),
    (
        "L27",
        "event-sourcing",
        "ada",
        0,
        "Rebuild projections from the event-sourced history rather than mutating rows.",
    ),
    (
        "L28",
        "event-sourcing",
        "ben",
        1,
        "Store every decision as an event and derive current state by replay (event sourcing).",
    ),
    (
        "L29",
        "event-sourcing",
        "ben",
        1,
        "Adopt event sourcing for the inventory ledger.",
    ),
    (
        "L30",
        "event-sourcing",
        "cyd",
        2,
        "Keep an event-sourced audit log as the system of record.",
    ),
    (
        "L31",
        "request-hedging",
        "ada",
        0,
        "Hedge the read by sending the same request to two independent replicas.",
    ),
    (
        "L32",
        "request-hedging",
        "ada",
        0,
        "Use request hedging so a slow replica does not dominate tail latency.",
    ),
    (
        "L33",
        "request-hedging",
        "ben",
        1,
        "Duplicate the query to a second region as a hedge and take the first success.",
    ),
    (
        "L34",
        "request-hedging",
        "ben",
        1,
        "Apply hedging on idempotent GETs when p99 exceeds the budget.",
    ),
    (
        "L35",
        "request-hedging",
        "cyd",
        2,
        "Race independent replicas with request hedging and cancel the loser.",
    ),
    (
        "L36",
        "lease-fencing",
        "ada",
        0,
        "Protect the leader with a lease and a fencing token on every write.",
    ),
    (
        "L37",
        "lease-fencing",
        "ada",
        0,
        "Use lease fencing so a partitioned old leader cannot commit.",
    ),
    (
        "L38",
        "lease-fencing",
        "ben",
        1,
        "Require a fencing token from the lock service before applying mutations.",
    ),
    (
        "L39",
        "lease-fencing",
        "ben",
        1,
        "Fence zombie primaries with monotonically increasing lease tokens.",
    ),
    (
        "L40",
        "lease-fencing",
        "cyd",
        2,
        "Put a fencing token on the replication stream to ignore stale leaders.",
    ),
)

HEDGES: tuple[str, ...] = (
    "I think we should",
    "Perhaps we could",
    "Simply",
    "Maybe the team should",
    "Recommend that we",
    "Consider",
    "Proposal:",
    "Idea:",
    "Please",
    "Let us",
)


def wording_variants_100() -> list[str]:
    """100 string-distinct trivial wordings of one circuit-breaker idea.

    Variation is hedge × failure-count. After string_key() they remain
    distinct; after canonicalize_mechanism they must share one id.
    """
    texts: list[str] = []
    for hedge in HEDGES:
        for n in range(1, 11):
            texts.append(
                f"{hedge} use a circuit breaker on the downstream call "
                f"after {n} consecutive failures"
            )
    if len(texts) != 100:
        raise RuntimeError(f"variant count {len(texts)} want 100")
    if len(set(texts)) != 100:
        raise RuntimeError("variant texts are not string-distinct")
    return texts


DISTINCT_CONTROL = (
    "Retry the same call with exponential backoff and jitter instead of a breaker."
)

UNKNOWN_PARAPHRASES = (
    "Shard the WAL per tenant so one noisy tenant cannot fill it.",
    "Per-tenant WAL sharding keeps a noisy tenant from filling the log.",
)
