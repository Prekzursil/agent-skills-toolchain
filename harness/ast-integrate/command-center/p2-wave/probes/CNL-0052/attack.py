#!/usr/bin/env python3
"""Cheapest count-gaming attacks against F01, plus the named-failure fixture.

Named failure (_USER-PROMPTS.md:11339, quoted in WORK-UNIT-CATALOG.json):
a 100-idea brainstorm satisfies unique_ideas >= 100 with trivial wording
variants. This module EXECUTES that attack; it does not only describe it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import f01  # noqa: E402

SEED = (
    "Cache expensive function results in a keyed in-memory store with TTL eviction."
)

# Full rewrite of SEED using only in-table synonyms / stems. Zero new mechanism.
SEED_REWRITE = (
    "Memoize costly callable outputs in an indexed RAM dictionary using expiry removal."
)

# 100 genuinely distinct mechanisms. Each line leads with a unique technique
# name so pairwise Jaccard stays below F01's merge threshold.
DISTINCT_IDEAS: list[str] = [
    "Replenish a tokenbucket so bursts spend saved tokens then clamp to fill rate",
    "Drain a leakybucket at a constant leak so bursts queue rather than spend tokens",
    "Record every request timestamp in a slidinglog and reject when the window is full",
    "Schedule transmissions with GCRA virtual scheduling so cells obey a sustainable rate",
    "Grow a congestion window with AIMD additive increase after a loss halves it",
    "Shape a CUBIC window as a cubic function of time since the last reduction",
    "Probe bottleneck bandwidth and RTT with BBR pacing instead of loss signals",
    "Hold a Vegas window near the delay-based equilibrium instead of filling buffers",
    "Estimate bandwidth from ACKs with Westwood after a lossy wireless reduction",
    "Mix delay and loss in Illinois so high-BDP paths grow faster than Reno",
    "Elect a Raft leader by randomized timeouts and replicate a log through that leader",
    "Run Paxos acceptors through prepare and accept majorities for a single slot",
    "Collect PBFT prepare and commit quorums so Byzantine replicas cannot fork history",
    "Choke a HotStuff pacemaker into a linear view-change with threshold signatures",
    "Order Zab transactions through a primary and broadcast a commit once followers ack",
    "Stamp Viewstamped replicas with a view number and recover from a designated backup",
    "Seal EPaxos commands in a dependency graph so non-interfering writes commit fast",
    "Rotate Tendermint rounds with prevote and precommit majorities plus a locked value",
    "Sample Avalanche dag parents until snowball confidence finalizes a conflict set",
    "Notarize Algorand blocks with cryptographic sortition instead of a stable leader",
    "Flush an LSM tree by compacting sorted runs from memory into deeper levels",
    "Cluster a Bepsilon tree so random inserts pay sequential I/O on large nodes",
    "Buffer Fractal tree messages inside internal nodes until a flush cascades down",
    "Append Bitcask values as a log and keep an in-RAM hintfile of the latest offsets",
    "Separate WiscKey values from LSM keys so compaction does not rewrite large blobs",
    "Probe a Cuckoofilter table with two hash buckets and relocate on collision",
    "Test Bloomfilter bits to reject absent keys without storing the keys themselves",
    "Xorfilter a static set into fingerprints that decode with three hash slots",
    "Pack a Quotientfilter by storing remainders in a packed quotient-addressed array",
    "Ribbonfilter a set with a triangular Gaussian matrix over a sliding window",
    "Sync replicas with a Merkletree by exchanging only mismatched subtree hashes",
    "Chunk files with Rabin CDC so rolling fingerprints cut at content-defined boundaries",
    "Cut FastCDC chunks with a normalized gear hash instead of a polynomial Rabin",
    "Grow a Gset CRDT by unioning observed elements with no tombstones",
    "Count with a PNcounter CRDT as the difference of two grow-only counters",
    "Observe-remove an ORset CRDT by tagging each add with a unique identifier",
    "Resolve LWW-register concurrent writes by comparing timestamps and a tie-break id",
    "Lock rows with two-phase locking until the transaction commits or aborts",
    "Validate optimistic concurrency at commit against versions read at start",
    "Assign MVCC snapshots so readers see a frozen version while writers append",
    "Abort SSI transactions that form a dangerous wr-ww dependency cycle",
    "Commit a 2PC transaction only after every participant votes yes in prepare",
    "Advance 3PC through pre-commit so a coordinator timeout cannot block forever",
    "Compensate a Saga step with an inverse action when a later step fails",
    "Try-confirm-cancel a TCC reservation so holdings expire without a confirm",
    "Disseminate updates by gossip so each peer fans a rumor to random neighbors",
    "Repair replicas with anti-entropy Merkle exchanges during idle periods",
    "Leave hinted handoff writes on a neighbor until the dead node returns",
    "Place keys with consistent hashing on a ring so added nodes steal only neighbors",
    "Score rendezvous hashing by highest random weight instead of a ring",
    "Jump-hash a key onto N buckets with a single integer walk and no ring state",
    "Build Maglev lookup tables so backend weights stay almost equal under churn",
    "Pick two random backends and send the request to the least loaded of the two",
    "Balance with least-connections so new sockets land on the quietest listener",
    "Smooth load with an EWMA of observed latency and shift traffic off the hot tail",
    "Issue SPIFFE SVIDs from a workload API so services authenticate without static keys",
    "Attenuate Macaroon caveats so a token can be delegated with extra restrictions",
    "Seal capabilities in an object-capability sealer so possession is authorization",
    "Mint a Kerberos TGT at an AS and exchange it for a service ticket at a TGS",
    "Evaluate OPA Rego rules against an input document and return an allow decision",
    "Authorize Cedar policies by matching principals actions and resources in a hierarchy",
    "Store Zanzibar tuples of relation and object then check a rewrite graph",
    "Grant RBAC roles to subjects and expand those roles into a permission set",
    "Decide ABAC by evaluating attributes of subject object and environment together",
    "Enforce a MAC lattice so information cannot flow downward in confidentiality",
    "Unwrap data keys inside an HSM so plaintext keys never leave the module",
    "Envelope-encrypt records with a DEK wrapped by a KEK stored in a KMS",
    "Seal messages with NaCl secretbox XSalsa20-Poly1305 authenticated encryption",
    "Expand an HKDF from a shared secret into independent traffic keys",
    "Hash passphrases with Argon2id memory-hard parameters against GPU guessing",
    "Derive keys with scrypt using a large salt and a tunable work factor",
    "Stretch passwords with Balloon hashing so memory hardness resists ASICs",
    "Walk a Merkle-Patricia trie to prove an account belongs in a state root",
    "Commit with a Verkle tree so proofs stay short under a vector commitment",
    "Prove membership in a sparse Merkle tree by producing sibling hashes to the root",
    "Accumulate set members in an RSA accumulator and witness deletion with a remainder",
    "Commit polynomials with KZG so an opening proves an evaluation at a point",
    "Fold FRI layers until a low-degree test accepts or rejects a Reed-Solomon codeword",
    "Encode an AIR for a STARK and check the execution trace against constraints",
    "Prove a Groth16 circuit with a trusted setup and a three-element proof",
    "Permute wires in PLONK so copy constraints enforce equality across gates",
    "Range-prove a Pedersen commitment with Bulletproofs and no trusted setup",
    "Hide a value in a Pedersen commitment using a homomorphic blinding factor",
    "Encrypt under ElGamal so two ciphertexts multiply into an encryption of a sum",
    "Add Paillier ciphertexts so the product decrypts to the sum of the plaintexts",
    "Evaluate BGV homomorphic gates on packed SIMD slots then refresh the modulus",
    "Bootstrap TFHE ciphertexts so NAND gates can compose without noise blow-up",
    "Answer PIR by returning a cuckoo-hashed bucket the querier can decrypt locally",
    "Hide access patterns behind PathORAM by reshuffling a tree path each read",
    "Evict with S3-FIFO by admitting into a small FIFO then promoting to a larger one",
    "Age CLOCK-Pro pages with a cold/hot clock hand instead of a strict LRU stack",
    "Adapt ARC between recency and frequency lists when the workload mix shifts",
    "Count TinyLFU candidates in a sketch and admit only if they beat the eviction victim",
    "Keep SLRU protected and probationary segments so one-hit wonders die in probation",
    "Track LIRS recency of reuse rather than recency of access for scan resistance",
    "Apply 2Q by sending first-timers through an A1 FIFO before the main AM LRU",
    "Weight W-TinyLFU windows so a tiny admission sketch gates a larger SLRU",
    "Rank CAR pages with a clock and adaptive recency/frequency like ARC but cheaper",
    "Remember LFU frequencies in a heap and evict the coldest key when the cache fills",
    "Detect scans with FRD by giving ghost entries a second chance after a burst miss",
]

TARGET = 100


def suffix_attack(seed: str = SEED, n: int = TARGET) -> list[str]:
    """Cheapest attack: one extra integer token per extra 'idea'."""
    if n < 1:
        return []
    out = [seed]
    for i in range(1, n):
        out.append(f"{seed} {i}")
    return out


def synonym_attack(seed: str = SEED, n: int = TARGET) -> list[str]:
    """Slightly dearer: rotate one surface synonym per extra idea."""
    cache_words = ["Cache", "Memoize", "Buffer"]
    result_words = ["results", "outputs", "values"]
    out = []
    for i in range(n):
        c = cache_words[i % len(cache_words)]
        r = result_words[(i // len(cache_words)) % len(result_words)]
        out.append(
            f"{c} expensive function {r} in a keyed in-memory store with TTL eviction {i}."
        )
    return out


def one_parameter_attack(seed: str = SEED, n: int = TARGET) -> list[str]:
    """One-parameter forks: same mechanism, different TTL integer."""
    out = []
    for i in range(n):
        out.append(
            "Cache expensive function results in a keyed in-memory store "
            f"with TTL {i + 1} eviction."
        )
    return out


def rewrite_attack(n: int = TARGET) -> list[str]:
    """Full rewrite of the seed, then suffix it. Tests S2 when Jaccard drops."""
    body = suffix_attack(SEED_REWRITE, n)
    body[0] = SEED_REWRITE
    return body


def extra_tokens(seed: str, corpus: list[str]) -> int:
    seed_n = len(seed.split())
    return sum(max(0, len(s.split()) - seed_n) for s in corpus)


def _pair_audit(ideas: list[str]) -> dict:
    """Independent check that the distinct corpus does not self-merge."""
    n = len(ideas)
    max_j = 0.0
    max_pair = None
    key_collisions = 0
    keys = [f01.mechanism_key(s) for s in ideas]
    toks = [f01.content_tokens(s) for s in ideas]
    seen: dict[tuple[str, ...], int] = {}
    for i, key in enumerate(keys):
        if key in seen:
            key_collisions += 1
        else:
            seen[key] = i
        for j in range(i + 1, n):
            jv = f01.jaccard(toks[i], toks[j])
            if jv > max_j:
                max_j = jv
                max_pair = (i, j, jv)
    return {
        "n": n,
        "max_jaccard": round(max_j, 4),
        "max_jaccard_pair": max_pair,
        "key_collisions": key_collisions,
        "unique_keys": len(seen),
        "below_threshold": max_j < f01.JACCARD_THRESHOLD,
    }


def score_corpus(name: str, corpus: list[str], seed: str = SEED) -> dict:
    naive = f01.naive_unique(corpus)
    jac = f01.unique_count_jaccard_only(corpus)
    uf = f01.unique_count_union_find(corpus)
    cc = f01.unique_count_connected_components(corpus)
    return {
        "name": name,
        "n_rows": len(corpus),
        "extra_tokens": extra_tokens(seed, corpus),
        "naive_unique": naive,
        "jaccard_only_unique": jac,
        "f01_union_find_unique": uf,
        "f01_connected_components_unique": cc,
        "algorithms_agree": uf == cc,
        "naive_gate_ge_100": f01.gate_unique_ge(naive),
        "f01_gate_ge_100": f01.gate_unique_ge(uf),
    }


def rename_jaccard() -> float:
    synonym_rename = SEED.replace("Cache", "Memoize")
    return round(
        f01.jaccard(f01.content_tokens(SEED), f01.content_tokens(synonym_rename)),
        4,
    )


def measure() -> dict:
    if len(DISTINCT_IDEAS) != TARGET:
        raise RuntimeError(f"DISTINCT_IDEAS length {len(DISTINCT_IDEAS)} != {TARGET}")
    gamed = suffix_attack(SEED, TARGET)
    synonym = synonym_attack(SEED, TARGET)
    one_param = one_parameter_attack(SEED, TARGET)
    rewrite = rewrite_attack(TARGET)
    mixed = suffix_attack(SEED, 50) + suffix_attack(SEED_REWRITE, 50)
    distinct = list(DISTINCT_IDEAS)

    attacks = [
        score_corpus("suffix-integer", gamed),
        score_corpus("synonym-rotate", synonym),
        score_corpus("one-parameter-ttl", one_param),
        score_corpus("full-rewrite-in-vocab", rewrite, seed=SEED_REWRITE),
        score_corpus("mixed-seed-and-rewrite", mixed),
    ]
    good = score_corpus("distinct-100", distinct, seed="")
    audit = _pair_audit(distinct)

    trivial = [
        a
        for a in attacks
        if a["name"] in {"suffix-integer", "synonym-rotate", "one-parameter-ttl"}
    ]
    cheapest = min(trivial, key=lambda a: (a["extra_tokens"], a["n_rows"]))
    mixed_row = next(a for a in attacks if a["name"] == "mixed-seed-and-rewrite")
    cheapest_f01 = cheapest["f01_union_find_unique"]
    named_failure = cheapest["naive_gate_ge_100"] and cheapest["naive_unique"] >= TARGET

    bad_verbatim = (
        f"reject_state=100 suffix-variants of one seed; "
        f"naive_unique={cheapest['naive_unique']} naive_gate_ge_100={cheapest['naive_gate_ge_100']}; "
        f"f01_unique={cheapest_f01} f01_gate_ge_100={cheapest['f01_gate_ge_100']}"
    )
    good_verbatim = (
        f"known_good=100 distinct mechanisms; "
        f"f01_unique={good['f01_union_find_unique']} "
        f"f01_gate_ge_100={good['f01_gate_ge_100']}"
    )

    return {
        "seed": SEED,
        "target": TARGET,
        "jaccard_threshold": f01.JACCARD_THRESHOLD,
        "rename_jaccard": rename_jaccard(),
        "named_failure_cite": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11339"
        ),
        "named_failure_reproduced": named_failure,
        "cheapest_attack": {
            "id": cheapest["name"],
            "sequence": [
                "Start from one seed mechanism sentence.",
                "For i in 1..99 append a unique integer token (one extra token, no new mechanism).",
                "Submit the 100 strings to the unique-idea counter.",
            ],
            "extra_tokens": cheapest["extra_tokens"],
            "naive_unique": cheapest["naive_unique"],
            "jaccard_only_unique": cheapest["jaccard_only_unique"],
            "f01_unique": cheapest_f01,
            "f01_connected_components_unique": cheapest["f01_connected_components_unique"],
            "naive_gate_ge_100": cheapest["naive_gate_ge_100"],
            "f01_gate_ge_100": cheapest["f01_gate_ge_100"],
            "f01_survives": cheapest_f01 < TARGET,
            "mixed_seed_and_rewrite": {
                "naive_unique": mixed_row["naive_unique"],
                "jaccard_only_unique": mixed_row["jaccard_only_unique"],
                "f01_unique": mixed_row["f01_union_find_unique"],
                "jaccard_only_splits_rewrite": mixed_row["jaccard_only_unique"] > 1,
                "f01_collapses_rewrite": mixed_row["f01_union_find_unique"] == 1,
            },
        },
        "all_attacks": attacks,
        "distinct_audit": audit,
        "both_states": {
            "planted_bad": {
                "fixture": "suffix-integer x100",
                "f01_unique": cheapest_f01,
                "f01_gate_ge_100": cheapest["f01_gate_ge_100"],
                "fires_reject": cheapest_f01 < TARGET,
                "verbatim": bad_verbatim,
            },
            "known_good": {
                "fixture": "distinct-100",
                "f01_unique": good["f01_union_find_unique"],
                "f01_gate_ge_100": good["f01_gate_ge_100"],
                "silent_accept": good["f01_union_find_unique"] >= TARGET,
                "verbatim": good_verbatim,
            },
        },
        "negative_control": {
            "reject_state": (
                "100 trivial suffix variants of one seed counted as 100 unique ideas "
                "by string equality (the :11339 count-gaming failure)"
            ),
            "observed": (
                f"F01 unique_count={cheapest_f01}; unique_ideas>=100 is "
                f"{cheapest['f01_gate_ge_100']}"
            ),
            "verbatim": bad_verbatim,
        },
        "residual": (
            "An out-of-vocabulary full rewrite whose token Jaccard drops below "
            f"{f01.JACCARD_THRESHOLD} and whose folded mechanism key is not in "
            "the synonym table will still increment F01. That class is NOT-CHECKED "
            "here beyond the in-vocabulary rewrite attack."
        ),
    }


def write_fixtures(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "gamed-suffix.json").write_text(
        json.dumps(suffix_attack(), indent=1) + "\n", encoding="utf-8"
    )
    (dest / "distinct-100.json").write_text(
        json.dumps(DISTINCT_IDEAS, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    doc = measure()
    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")
    bad = doc["both_states"]["planted_bad"]
    good = doc["both_states"]["known_good"]
    if not doc["named_failure_reproduced"]:
        raise SystemExit("FAILED: named failure not reproduced")
    if not doc["cheapest_attack"]["f01_survives"]:
        raise SystemExit("FAILED: F01 did not survive cheapest attack")
    if not bad["fires_reject"] or not good["silent_accept"]:
        raise SystemExit("FAILED: both-states control")
    if not doc["distinct_audit"]["below_threshold"]:
        raise SystemExit("FAILED: distinct corpus Jaccard too high")
    if (
        doc["cheapest_attack"]["f01_unique"]
        != doc["cheapest_attack"]["f01_connected_components_unique"]
    ):
        raise SystemExit("FAILED: clustering algorithms disagree")
