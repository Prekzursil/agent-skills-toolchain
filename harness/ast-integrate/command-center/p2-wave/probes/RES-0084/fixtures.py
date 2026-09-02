#!/usr/bin/env python3
"""Known-broken (gamed) and known-good (distinct) corpora for RES-0084.

Gamed: 100 distinct *strings* that are trivial rewordings / synonym swaps /
one-parameter numeric forks of one cache-family mechanism.

Distinct: 100 genuinely different mechanisms with disjoint core vocabularies.

Deep-paraphrase pair + a genuine-distinct control share the lexical band
that S1 cannot split — that pair is the named blind-spot fixture.
"""
from __future__ import annotations

import itertools

SEED = (
    "Cache expensive function results in a keyed in-memory table with TTL eviction"
)

# Full rewrite of SEED that keeps the meaning but shares almost no
# content tokens after fold. This is the metric's stated blind spot.
DEEP_PARAPHRASE = (
    "Remember answers already computed so identical questions never "
    "trigger the slow path twice"
)

# Genuinely different mechanism, used as the other end of the
# deep-paraphrase band comparison.
DISTINCT_CONTROL = "Elect a raft leader among replicas before applying the log"

VERBS = ("Cache", "Memoize", "Store", "Buffer")
COST = ("expensive", "costly")
CALL = ("function", "callable")
OUTS = ("results", "outputs", "values")
LINKS = ("in", "via", "using")
INDEX = ("keyed", "indexed")
PLACE = ("in-memory", "RAM", "memory")
SHAPE = ("table", "map", "dictionary")
LIFE = ("TTL", "timeout", "expiry")
DROP = ("eviction", "removal")
NUM = ("", " lasting 60 seconds", " lasting 90 seconds")


def gamed_corpus(n: int = 100) -> list[str]:
    """100 unique surface strings, one underlying mechanism."""
    seen: set[str] = set()
    out: list[str] = []
    prod = itertools.product(
        VERBS, COST, CALL, OUTS, LINKS, INDEX, PLACE, SHAPE, LIFE, DROP, NUM
    )
    for verb, cost, call, outs, link, index, place, shape, life, drop, num in prod:
        text = (
            f"{verb} {cost} {call} {outs} {link} a {index} {place} "
            f"{shape} with {life} {drop}{num}"
        )
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
        if len(out) >= n:
            break
    if len(out) != n:
        raise RuntimeError(f"gamed corpus short: {len(out)} != {n}")
    return out


# 100 genuinely distinct mechanisms. Distinctive content tokens are
# chosen so pairwise folded Jaccard stays well below the 0.50 band.
DISTINCT_IDEAS: tuple[str, ...] = (
    "Bloom filters skip disk lookups for absent keys",
    "Write-ahead logs replay durable prefixes after crashes",
    "Two-phase commit coordinates atomic distributed writes",
    "Merkle trees prove object tampering across replicas",
    "Consistent hashing places shards when nodes join",
    "Raft elects a leader before appending entries",
    "Vector clocks detect concurrent updates without locks",
    "Quorum reads overlap writes preserving linearizability",
    "Gossip spreads membership without a coordinator",
    "CRDTs merge replicas without consensus rounds",
    "Paxos chooses one value under message asynchrony",
    "B-trees keep range scans logarithmic on packed pages",
    "LSM trees flush writes into immutable sorted runs",
    "Copy-on-write snapshots isolate readers from mutators",
    "MVCC versions rows so readers skip writer locks",
    "Hopfield nets recall stored patterns from partial cues",
    "Simulated annealing escapes minima via a cooling schedule",
    "A-star expands graphs under admissible heuristics",
    "PageRank scores documents by inbound walk probability",
    "MinHash sketches estimate set overlap without storing elements",
    "HyperLogLog estimates cardinality from max hashed ranks",
    "Count-min sketches bound frequency with bounded memory",
    "Cuckoo filters store fingerprints for set membership",
    "Ribbon filters pack XOR codes for compact membership",
    "Erasure coding reconstructs objects from k of n shards",
    "Reed-Solomon recovers lost packets from parity blocks",
    "Lamport timestamps order events with local counters",
    "Snapshot isolation prevents dirty reads in transactions",
    "Serializable snapshot isolation blocks write skew",
    "Calvin sequences transactions through a shared log",
    "Spanner uses TrueTime to bound external consistency",
    "Percolator overlays incremental updates on snapshots",
    "MapReduce shuffles mapped pairs to reducers by key",
    "Spark lineage recomputes lost RDD partitions",
    "Flink checkpoints barrier-aligned operator state",
    "Kafka retains partitioned logs for consumer groups",
    "Pulsar separates compute brokers from bookkeeper storage",
    "NATS routes subjects through a lightweight mesh",
    "QUIC multiplexes streams without head-of-line blocking",
    "TCP congestion control probes available path capacity",
    "RED drops packets early to signal impending queues",
    "ECN marks packets instead of dropping on congestion",
    "BGP advertises reachability between autonomous systems",
    "OSPF floods link state inside an area",
    "DHCP leases addresses from a managed pool",
    "DNS caches nameserver answers with TTLs",
    "TLS handshakes negotiate ciphers before application bytes",
    "Noise protocols compose DH patterns for session secrecy",
    "Signal double-ratchet advances session material per message",
    "HMAC authenticates blobs with a shared secret",
    "Argon2 hashes passwords with memory-hard loops",
    "Balloon hashing inflates memory to slow guessing",
    "HKDF derives material from a shared secret and salt",
    "ChaCha20 encrypts bytes with a stream cipher",
    "AES-GCM authenticates ciphertext with a nonce",
    "SPHINCS signs with hash-based few-time signatures",
    "Kyber encapsulates secrets under module lattices",
    "Dilithium signs under module-LWE hardness",
    "OPAQUE hides passwords from the login server",
    "WebAuthn binds credentials to origin and hardware",
    "Capability tokens authorize actions without ambient ACL",
    "Macaroons attenuate authorization with caveats",
    "SPIFFE issues workload identities via SVIDs",
    "TUF rolls signing material so compromised mirrors cannot freeze",
    "in-toto links attest steps in a supply chain",
    "SLSA provenance records the builder that produced an artifact",
    "Reproducible builds bit-match binaries from source",
    "Nix hashes derivation inputs to sandbox installs",
    "Bazel sandboxes actions behind declared dependencies",
    "Content-addressed stores retrieve blobs by digest",
    "IPFS locates merkle-dags via a DHT",
    "BitTorrent swaps pieces among a swarm of peers",
    "Rsync rolls checksums to send only deltas",
    "CDC streams row changes from a database log",
    "SQLite checkpoints WAL back into the main image",
    "Postgres HOT updates avoid index churn on hot rows",
    "MySQL group replication certifies writesets for conflict",
    "Redis streams persist consumer offsets in the log",
    "Cassandra uses hinted handoff after replica downtime",
    "Dynamo style sloppy quorum hands off to neighbors",
    "Chubby locks serialize metadata mutations in a cell",
    "ZooKeeper znodes notify watchers of sequential updates",
    "etcd revisions order keys through raft",
    "Consul gossips health to steer service discovery",
    "Envoy sidecar proxies retries and outlier ejection",
    "Istio programs those proxies from a control plane",
    "Kubernetes schedules pods onto nodes with requested resources",
    "systemd supervises cgroups so services restart cleanly",
    "seccomp filters syscalls a sandbox may issue",
    "Landlock restricts filesystem reach of a process",
    "eBPF traces kernel events without new modules",
    "io_uring batches syscalls to cut context switches",
    "RCU defers reclamation until readers finish",
    "Hazard pointers retire nodes after no reader holds them",
    "Seqlocks retry readers when a writer raced",
    "Ticket locks grant FIFO entry into a critical section",
    "MCS locks spin on a local node to cut coherence traffic",
    "Work stealing balances deques among idle workers",
    "Actor mailboxes serialize state behind asynchronous messages",
    "STM retries transactions when occupancy conflicts",
)


def distinct_corpus() -> list[str]:
    ideas = list(DISTINCT_IDEAS)
    if len(ideas) != 100:
        raise RuntimeError(f"distinct corpus size {len(ideas)} != 100")
    if len(set(ideas)) != 100:
        raise RuntimeError("distinct corpus has duplicate strings")
    return ideas


def adversarial_ladder(seed: str = SEED, replacements: int = 8) -> list[dict]:
    """Replace successive content tokens with nonce tokens.

    Records folded Jaccard against the original after each replacement so
    a probe can locate the last step still >= threshold and the first
    step below it.
    """
    from counter import content_tokens, jaccard  # local import for fixtures-only use

    original = content_tokens(seed)
    words = seed.split()
    content_idx = [
        i
        for i, w in enumerate(words)
        if content_tokens(w)
    ]
    steps = []
    current = list(words)
    for k, idx in enumerate(content_idx[:replacements]):
        current[idx] = f"nonce{k}xyz"
        text = " ".join(current)
        toks = content_tokens(text)
        steps.append(
            {
                "k": k + 1,
                "text": text,
                "jaccard_vs_seed": round(jaccard(original, toks), 6),
                "replaced_index": idx,
            }
        )
    return steps
