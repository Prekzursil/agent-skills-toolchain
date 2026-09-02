"""Planted 20-cluster corpus for RES-0145 circular-citation / origin-descent.

Ten clusters are citation cycles whose members restate one origin (shared
nonce 6-gram + shared distinctive quantity + later dates + a directed
citation cycle). Ten clusters are genuinely independent sources on a
related claim; two of those (CLAIM-18, CLAIM-19) contain citation cycles
of *distinct* facts so a cycle-only detector is a known-broken control.

Gold lives in gold_by_cluster(). The detector must never read it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "corpus.json"
FETCHED_AT = "2026-08-24T20:00:00Z"
FILE_URL = (
    "file:command-center/p2-wave/probes/RES-0145/fixtures/corpus.json"
)

# CLAIM-01..10 = planted single-origin cycles; 11..20 = independent.
CYCLE_SPECS: list[dict[str, Any]] = [
    {
        "id": "CLAIM-01",
        "claim": "Salt-fog aged zinc hardware shows a specific stall torque.",
        "nonce": "zinc plated latch hysteresis of 47.3 newton metres",
        "qty": "47.3",
        "dates": ("2019-04-11", "2020-01-08", "2021-06-02"),
        "hosts": (
            "https://marine-lab.example/hasp/2019-stall",
            "https://vendor-echo.example/whitepaper/hasp-stall",
            "https://hardware-digest.example/roundup/hasp",
        ),
        "extras": (
            "Marine hardware lab salt-fog protocol 2019 recorded a zinc hasp stall.",
            "A vendor whitepaper later quoted the stall figure without new benches.",
            "An aggregator newsletter reprinted the stall figure as industry consensus.",
        ),
    },
    {
        "id": "CLAIM-02",
        "claim": "A WASM trap-recover path has a characteristic wall-clock cost.",
        "nonce": "wasm trap recover path costs 13.91 microseconds",
        "qty": "13.91",
        "dates": ("2018-11-02", "2019-07-19", "2022-03-14"),
        "hosts": (
            "https://engine-notes.example/wasm/trap-recover",
            "https://runtime-blog.example/copy/trap-cost",
            "https://systems-weekly.example/wasm-trap",
        ),
        "extras": (
            "The engine diary logged a trap-recover sample on a quiet host.",
            "A later runtime blog restated the sample as a portable constant.",
            "A weekly roundup treated the sample as established folklore.",
        ),
    },
    {
        "id": "CLAIM-03",
        "claim": "Raft pre-vote has a published window length.",
        "nonce": "raft pre vote window of 0.0062 seconds",
        "qty": "0.0062",
        "dates": ("2017-05-22", "2018-02-01", "2020-09-30"),
        "hosts": (
            "https://consensus-lab.example/raft/prevote",
            "https://distsys-mirror.example/raft-window",
            "https://ops-handbook.example/raft-timing",
        ),
        "extras": (
            "Consensus lab notes fixed a pre-vote timer during a partition drill.",
            "A mirror post repeated the timer as if it were in the Raft thesis.",
            "An ops handbook copied the timer into a checklist.",
        ),
    },
    {
        "id": "CLAIM-04",
        "claim": "A blocked Bloom filter is claimed to occupy a tiny bit array.",
        "nonce": "blocked bloom occupies exactly 2048 bits",
        "qty": "2048",
        "dates": ("2016-08-09", "2017-12-12", "2019-04-04"),
        "hosts": (
            "https://db-origin.example/bloom/blocked-size",
            "https://index-tips.example/bloom-size",
            "https://data-eng-list.example/bloom-copy",
        ),
        "extras": (
            "The original index note mis-stated the blocked Bloom footprint.",
            "A tips thread repeated the footprint without measuring bytes.",
            "A mailing-list digest recycled the footprint as a rule of thumb.",
        ),
    },
    {
        "id": "CLAIM-05",
        "claim": "A prefix cache is said to freeze a specific token count.",
        "nonce": "prefix cache retains 881 frozen prompt tokens",
        "qty": "881",
        "dates": ("2023-01-17", "2023-06-21", "2024-02-09"),
        "hosts": (
            "https://infer-lab.example/cache/prefix-881",
            "https://serving-notes.example/prefix-cache",
            "https://mlops-digest.example/frozen-prefix",
        ),
        "extras": (
            "Infer-lab logged a frozen-prefix occupancy during a canary.",
            "Serving notes repeated the occupancy as a default.",
            "An MLOps digest presented the occupancy as a community default.",
        ),
    },
    {
        "id": "CLAIM-06",
        "claim": "A Merkle tree is described with an odd fanout.",
        "nonce": "merkle fanout uses 17.0 arity layout",
        "qty": "17.0",
        "dates": ("2015-03-03", "2016-10-18", "2018-07-07"),
        "hosts": (
            "https://tree-paper.example/merkle/odd-fanout",
            "https://crypto-explainer.example/merkle-arity",
            "https://ledger-weekly.example/fanout",
        ),
        "extras": (
            "The tree paper picked an odd fanout for a packing experiment.",
            "An explainer restated the fanout as the usual layout.",
            "A ledger weekly copied the fanout into a diagram caption.",
        ),
    },
    {
        "id": "CLAIM-07",
        "claim": "A GPU kernel energy sample is treated as a constant.",
        "nonce": "kernel joule meter read 0.000314 joules",
        "qty": "0.000314",
        "dates": ("2021-02-14", "2021-11-03", "2023-05-25"),
        "hosts": (
            "https://gpu-lab.example/energy/kernel-sample",
            "https://perf-blog.example/joule-copy",
            "https://hpc-roundup.example/kernel-joules",
        ),
        "extras": (
            "GPU lab joule-metered a single kernel on an idle board.",
            "A perf blog copied the joule reading as a budget line.",
            "An HPC roundup repeated the joule reading without a board id.",
        ),
    },
    {
        "id": "CLAIM-08",
        "claim": "A recursive resolver is said to advertise an enormous TTL.",
        "nonce": "recursive resolver advertised ttl 918273 seconds",
        "qty": "918273",
        "dates": ("2014-09-01", "2015-06-16", "2017-01-29"),
        "hosts": (
            "https://dns-origin.example/ttl/misprint",
            "https://netops-wiki.example/ttl-copy",
            "https://resolver-news.example/ttl",
        ),
        "extras": (
            "The origin ticket logged a mis-printed resolver TTL.",
            "A wiki page copied the TTL into a tuning table.",
            "A resolver newsletter repeated the TTL as observed fact.",
        ),
    },
    {
        "id": "CLAIM-09",
        "claim": "A CRDT tombstone identity is described as a 48-bit pack.",
        "nonce": "tombstone identity packed into 48.0 bits",
        "qty": "48.0",
        "dates": ("2020-05-05", "2021-03-22", "2022-08-18"),
        "hosts": (
            "https://crdt-lab.example/tombstone/width",
            "https://sync-blog.example/tombstone-bits",
            "https://offline-first.example/tombstone",
        ),
        "extras": (
            "CRDT lab described a packed tombstone key during a spike.",
            "A sync blog restated the pack width as the on-wire format.",
            "An offline-first post repeated the pack width as canonical.",
        ),
    },
    {
        "id": "CLAIM-10",
        "claim": "SQLite WAL checkpointing is said to trip after 4097 pages.",
        "nonce": "wal checkpoint after 4097 pages exactly",
        "qty": "4097",
        "dates": ("2013-12-24", "2016-04-09", "2019-09-11"),
        "hosts": (
            "https://sqlite-notes.example/wal/4097",
            "https://embed-db.example/wal-copy",
            "https://mobile-storage.example/wal",
        ),
        "extras": (
            "Engine notes recorded an off-by-one WAL checkpoint trip.",
            "An embedded-db post copied the trip count as a default.",
            "A mobile-storage article repeated the trip count as gospel.",
        ),
    },
]

INDEPENDENT_SPECS: list[dict[str, Any]] = [
    {
        "id": "CLAIM-11",
        "claim": "Hardware stiction after weathering is measurable.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2022-03-01",
                "url": "https://padlock-bench.example/salt-fog/12nm",
                "cites": [],
                "body": (
                    "A painted padlock from the 2022 salt-fog lot needed 12 Nm "
                    "of breakaway torque on a dry jig."
                ),
            },
            {
                "role": "b",
                "date": "2021-11-19",
                "url": "https://bronze-lab.example/humidity/clasp",
                "cites": [],
                "body": (
                    "Humidity-aged bronze clasps unstuck at 19 newton metres "
                    "when pulled in a tensile frame."
                ),
            },
            {
                "role": "c",
                "date": "2023-07-08",
                "url": "https://polymer-test.example/uv/hasp",
                "cites": [],
                "body": (
                    "Third-party UV aging of a polymer hasp produced 8.5 N m "
                    "stiction; the lab did not share a zinc coupon."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-12",
        "claim": "Interpreter trap handling has a measurable cost.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2020-04-12",
                "url": "https://lua-vm.example/trap/cost",
                "cites": [],
                "body": (
                    "A Lua VM unwind of a debug hook cost 2.4 microseconds on "
                    "the laptop used for the note."
                ),
            },
            {
                "role": "b",
                "date": "2019-08-30",
                "url": "https://jvm-safepoint.example/poll",
                "cites": [],
                "body": (
                    "HotSpot safepoint polls on an idle loop added 0.7 "
                    "microseconds per iteration in that patch set."
                ),
            },
            {
                "role": "c",
                "date": "2021-01-15",
                "url": "https://ebpf-verifier.example/reject",
                "cites": [],
                "body": (
                    "The eBPF verifier reject path returned in 44 microseconds "
                    "on the CI box; no WASM runtime was involved."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-13",
        "claim": "Consensus election timing is environment-specific.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2018-06-06",
                "url": "https://etcd-ops.example/election/cloud",
                "cites": [],
                "body": (
                    "etcd leader elections on that VPC completed in 180 "
                    "milliseconds under a 100 ms RTT."
                ),
            },
            {
                "role": "b",
                "date": "2019-02-28",
                "url": "https://zk-ensemble.example/tick",
                "cites": [],
                "body": (
                    "ZooKeeper tickTime 2000 with syncLimit 5 produced a "
                    "different failover envelope than Raft tutorials claim."
                ),
            },
            {
                "role": "c",
                "date": "2022-10-10",
                "url": "https://paxos-class.example/lab",
                "cites": [],
                "body": (
                    "Classroom Paxos replicas on loopback elected in 12 "
                    "milliseconds; WAN numbers were not collected."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-14",
        "claim": "Probabilistic filters have independently measured sizes.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2017-07-07",
                "url": "https://cuckoo-filter.example/bytes",
                "cites": [],
                "body": (
                    "A cuckoo filter for 1e6 keys used 3.1 bits per key in "
                    "the published occupancy table."
                ),
            },
            {
                "role": "b",
                "date": "2018-01-21",
                "url": "https://quotient-filter.example/mem",
                "cites": [],
                "body": (
                    "Quotient filter memory on that workload was 12 MiB, "
                    "measured with /proc/self/statm."
                ),
            },
            {
                "role": "c",
                "date": "2020-12-03",
                "url": "https://xor-filter.example/build",
                "cites": [],
                "body": (
                    "xor-filter construction for the same key set finished "
                    "in 90 milliseconds on a desktop CPU."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-15",
        "claim": "Prompt-prefix caching occupancy varies by stack.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2024-01-04",
                "url": "https://vllm-notes.example/prefix/hit",
                "cites": [],
                "body": (
                    "vLLM prefix hits on a 2k system prompt saved 140 "
                    "milliseconds to first token in that log."
                ),
            },
            {
                "role": "b",
                "date": "2023-09-16",
                "url": "https://tgi-bench.example/cache",
                "cites": [],
                "body": (
                    "TGI block cache held 32 sequences of 512 tokens; occupancy "
                    "was reported in blocks rather than a frozen token count."
                ),
            },
            {
                "role": "c",
                "date": "2024-06-22",
                "url": "https://llama-cpp.example/prompt-cache",
                "cites": [],
                "body": (
                    "llama.cpp prompt cache files on disk were 18 MiB for a "
                    "local 7B run and were not a token occupancy claim."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-16",
        "claim": "Hash-tree fanout is a local packing choice.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2016-02-02",
                "url": "https://git-pack.example/fanout",
                "cites": [],
                "body": (
                    "Git pack idx fanout is a 256-entry prefix table, not an "
                    "odd Merkle arity."
                ),
            },
            {
                "role": "b",
                "date": "2019-05-19",
                "url": "https://ipfs-unixfs.example/links",
                "cites": [],
                "body": (
                    "UnixFS directory nodes in that corpus used 174 links on "
                    "average; the author did not cite an odd Merkle arity."
                ),
            },
            {
                "role": "c",
                "date": "2021-08-08",
                "url": "https://certificate-transparency.example/merkle",
                "cites": [],
                "body": (
                    "CT Merkle trees are binary. Leaf hashing followed RFC 6962 "
                    "on the log we fetched."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-17",
        "claim": "Accelerator energy samples are board-specific.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2022-04-04",
                "url": "https://nvml-trace.example/energy",
                "cites": [],
                "body": (
                    "NVML energy counters on an A100 rose 1.8 joules during "
                    "the matmul microbench."
                ),
            },
            {
                "role": "b",
                "date": "2023-03-13",
                "url": "https://rocm-smi.example/power",
                "cites": [],
                "body": (
                    "rocm-smi average power on the MI250 run was 280 watts; "
                    "no sub-millijoule kernel constant appears."
                ),
            },
            {
                "role": "c",
                "date": "2020-10-27",
                "url": "https://tpu-profiler.example/duty",
                "cites": [],
                "body": (
                    "Cloud TPU profiler duty cycle was 61 percent; energy was "
                    "not reported as a per-kernel joule constant."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-18",
        "claim": "Retry policy should be documented as complementary knobs.",
        "cycle": True,
        "docs": [
            {
                "role": "a",
                "date": "2022-09-01",
                "url": "https://queue-depth.example/inbound/31",
                "cites": ["CLAIM-18-b"],
                "body": (
                    "Queue depth 31 is the saturation point on the inbound "
                    "worker. Complementary timeout numbers live in the sibling "
                    "note CLAIM-18-b."
                ),
            },
            {
                "role": "b",
                "date": "2023-01-20",
                "url": "https://client-budget.example/timeout/250ms",
                "cites": ["CLAIM-18-c"],
                "body": (
                    "Timeout 250 milliseconds is the client budget before abort. "
                    "Jitter rationale is in CLAIM-18-c, not copied here."
                ),
            },
            {
                "role": "c",
                "date": "2021-12-12",
                "url": "https://retry-jitter.example/factor/015",
                "cites": ["CLAIM-18-a"],
                "body": (
                    "Jitter 0.15 keeps lockstep retries from colliding. Queue "
                    "saturation is tabulated by CLAIM-18-a rather than restated."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-19",
        "claim": "Storage checkpoints have several independently chosen trips.",
        "cycle": True,
        "docs": [
            {
                "role": "a",
                "date": "2018-03-03",
                "url": "https://postgres-chkpt.example/timeout",
                "cites": ["CLAIM-19-b"],
                "body": (
                    "PostgreSQL checkpoint_timeout of 5 minutes dominated I/O "
                    "in that OLTP mix. Page-count trips are a different engine."
                ),
            },
            {
                "role": "b",
                "date": "2019-11-11",
                "url": "https://rocksdb-wal.example/size-limit",
                "cites": ["CLAIM-19-c"],
                "body": (
                    "RocksDB max_total_wal_size of 128 MiB triggered a flush. "
                    "SQLite page trips are out of scope for this note."
                ),
            },
            {
                "role": "c",
                "date": "2020-07-07",
                "url": "https://lmdb-map.example/sync",
                "cites": ["CLAIM-19-a"],
                "body": (
                    "LMDB map sync after 4096 KiB writes was a local knob. "
                    "Postgres timeouts remain in the CLAIM-19-a write-up."
                ),
            },
        ],
    },
    {
        "id": "CLAIM-20",
        "claim": "Resolver TTLs should be taken from the zone, not folklore.",
        "cycle": False,
        "docs": [
            {
                "role": "a",
                "date": "2016-05-05",
                "url": "https://zonefile.example/example-com/ttl",
                "cites": [],
                "body": (
                    "The example.com zone we pulled advertised 3600 seconds on "
                    "the apex A record."
                ),
            },
            {
                "role": "b",
                "date": "2018-08-18",
                "url": "https://unbound-conf.example/cache-min",
                "cites": [],
                "body": (
                    "Unbound cache-min-ttl 60 overrode tiny TTLs on that campus "
                    "resolver; no six-digit folklore TTL appeared in the capture."
                ),
            },
            {
                "role": "c",
                "date": "2021-04-04",
                "url": "https://rfc8767.example/serve-stale",
                "cites": [],
                "body": (
                    "RFC 8767 serve-stale permits answering after expiry; it "
                    "does not invent a six-digit TTL."
                ),
            },
        ],
    },
]


def gold_by_cluster() -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in CYCLE_SPECS:
        out[spec["id"]] = "cycle"
    for spec in INDEPENDENT_SPECS:
        out[spec["id"]] = "independent"
    return out


def _cycle_documents(spec: dict[str, Any]) -> list[dict[str, Any]]:
    cid = spec["id"]
    ids = [f"{cid}-a", f"{cid}-b", f"{cid}-c"]
    cites = {
        ids[0]: [ids[1]],
        ids[1]: [ids[2]],
        ids[2]: [ids[0]],
    }
    tails = (
        "Origin notes were filed first.",
        "Secondary write-up restates the origin figure.",
        "Tertiary blog copies the same figure.",
    )
    docs = []
    for i, role in enumerate(("a", "b", "c")):
        body = f"{spec['extras'][i]} {spec['nonce']} {tails[i]}"
        docs.append(
            {
                "id": ids[i],
                "cluster_id": cid,
                "role": role,
                "claim": spec["claim"],
                "url": spec["hosts"][i],
                "published_at": spec["dates"][i],
                "body": body,
                "cites": list(cites[ids[i]]),
                "nonce": spec["nonce"],
                "qty": spec["qty"],
            }
        )
    return docs


def _independent_documents(spec: dict[str, Any]) -> list[dict[str, Any]]:
    docs = []
    for row in spec["docs"]:
        docs.append(
            {
                "id": f"{spec['id']}-{row['role']}",
                "cluster_id": spec["id"],
                "role": row["role"],
                "claim": spec["claim"],
                "url": row["url"],
                "published_at": row["date"],
                "body": row["body"],
                "cites": list(row["cites"]),
            }
        )
    return docs


def build_corpus() -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    gold = gold_by_cluster()
    for spec in CYCLE_SPECS:
        docs = _cycle_documents(spec)
        documents.extend(docs)
        clusters.append(
            {
                "id": spec["id"],
                "claim": spec["claim"],
                "gold": gold[spec["id"]],
                "member_ids": [d["id"] for d in docs],
                "citation_cycle_planted": True,
            }
        )
    for spec in INDEPENDENT_SPECS:
        docs = _independent_documents(spec)
        documents.extend(docs)
        clusters.append(
            {
                "id": spec["id"],
                "claim": spec["claim"],
                "gold": gold[spec["id"]],
                "member_ids": [d["id"] for d in docs],
                "citation_cycle_planted": bool(spec["cycle"]),
            }
        )
    return {
        "unit_id": "RES-0145",
        "fetched_at": FETCHED_AT,
        "file_url": FILE_URL,
        "n_clusters": len(clusters),
        "n_cycle": 10,
        "n_independent": 10,
        "clusters": clusters,
        "documents": documents,
    }


def materialize() -> Path:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    doc = build_corpus()
    FIXTURE.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return FIXTURE


def load_corpus() -> dict[str, Any]:
    if not FIXTURE.is_file():
        materialize()
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def documents_for_detector(corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Strip gold / nonce / qty so the detector cannot cheat."""
    corpus = corpus or load_corpus()
    drop = {"nonce", "qty"}
    out = []
    for doc in corpus["documents"]:
        row = {k: v for k, v in doc.items() if k not in drop}
        row["cluster_id"] = row.get("cluster_id") or row.get("cluster_id")
        row["cluster_id"] = row["cluster_id"]
        row["url"] = row.get("url") or row.get("url")
        row["published_at"] = row.get("published_at") or row.get("published_at")
        row["cites"] = list(row.get("cites") or row.get("cites") or [])
        out.append(row)
    return out


gold_by_cluster = gold_by_cluster
load_corpus = load_corpus
documents_for_detector = documents_for_detector
FETCHED_AT = FETCHED_AT
