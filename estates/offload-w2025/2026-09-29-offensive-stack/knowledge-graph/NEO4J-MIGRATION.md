---
title: NEO4J-MIGRATION
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/knowledge-graph/neo4-j-migration
---

# NEO4J-MIGRATION — the Graphiti/Neo4j path for the docker era

Status 2026-09-29. The estate's shared knowledge graph today is an **embedded
Kùzu 0.11.3** database (`D:\opt\knowledge-graph\db`) driven in-process by the
gateway (`fronts.knowledge_graph`, kind=module). This document describes why
that is a deliberate bridge and how to move the same graph model onto
**Neo4j + Graphiti** when the estate's docker layer comes up.

## Why the embedded bridge exists (constraints that forced it)

- `pip install kuzu` **cannot** succeed into C:\Python314 on Windows: PyPI has
  no cp314 win_amd64 wheel for any kuzu release (0.11.0–0.11.3 checked
  individually — cp314 wheels are Linux-only), the sdist fails at extraction
  on Windows MAX_PATH, and the VM has no C/C++ toolchain to build it.
- Upstream `kuzudb/kuzu` is **archived** (final release v0.11.3, 2025-10-10),
  so no cp314 Windows wheel is coming. The workaround binds the official
  prebuilt `kuzu_shared.dll` (from the v0.11.3 `libkuzu-windows-x86_64.zip`
  release asset) via ctypes (`kuzucapi.py`) — same engine, same on-disk
  format as the PyPI package, running in-process under C:\Python314.
- Estate doctrine is one process and no docker dependence for the live
  gateway; Kùzu embedded fits that. A graph **server** (Neo4j) is a
  different lifecycle and belongs to the docker era.

## Where Neo4j/Graphiti already fits the estate

Two estate stacks already speak this world (both docker-pending per
`D:\opt\OFFENSIVE-STACK.md`):

- **PentAGI** `D:\opt\pentagi` — full profile has **Graphiti KG on**
  (compose base/graphiti profiles ready, `bring-up.ps1`).
- **Decepticon upstream** `D:\opt\decepticon-upstream` — 7-service stack with
  a **Neo4j KG** service, `.env` ready.

Graphiti (getzep/graphiti) is a temporal knowledge-graph layer on Neo4j:
episodes (raw event/journal entries) are ingested and resolved into entities
and relations with validity intervals. The offensive analog: engagement logs
in → entities (hosts, creds, findings, techniques) out — which is exactly the
model this module maintains by hand today.

## Target topology (docker era)

```
gateway 127.0.0.1:31100/mcp
  └─ backs "knowledge-graph" (kind=module, same front, swapped backend)
       ├─ NOW : kgcore.py  -> embedded Kuzu (kuzucapi.py / kuzu_shared.dll)
       └─ THEN: neo4j_backend.py -> neo4j Python driver -> bolt://127.0.0.1:7687
                     └─ Neo4j container (loopback-only port binding!)
                          └─ Graphiti ingestion for temporal/episode layers
```

Constraints carried over unchanged:
- **Loopback-only binding** — Neo4j publishes `127.0.0.1:7474` (HTTP) and
  `127.0.0.1:7687` (bolt) only, never `0.0.0.0`. Estate rule.
- **Single writer** — the gateway remains the only writer; other agents keep
  going through `harness_invoke`. Neo4j browser UI is operator-only.
- **No watchdogs** — the Neo4j container is owned by docker compose, not by
  the gateway. The gateway treats it like any rpc backend: probe lazily,
  report honestly if down (`available` when bolt answers).
- **Secrets stay local** — neo4j password lives in the compose `.env`
  (private estate) and is referenced by name; logs carry sha8 at most.

## Migration steps

1. Bring docker up (remote-engine path is decided; see OFFENSIVE-STACK.md),
   then add to the estate compose:
   ```yaml
   neo4j:
     image: neo4j:5
     environment:
       NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}          # from .env, never committed
     ports:
       - "127.0.0.1:7474:7474"                      # loopback-only, estate rule
       - "127.0.0.1:7687:7687"
     volumes:
       - neo4j-data:/data
     healthcheck:
       test: ["CMD-SHELL", "wget -qO- http://localhost:7474 || exit 1"]
       interval: 15s
       retries: 10
   ```
2. `pip install neo4j` into C:\Python314 (pure-python driver — no wheel
   problem this time).
3. New backend `D:\opt\knowledge-graph\neo4j_backend.py` implementing the
   **same six operations** (add_node, add_edge, neighbors, shortest_path,
   search, cypher) against bolt. Schema translation:

   | Kùzu (this repo)           | Neo4j                                   |
   |----------------------------|------------------------------------------|
   | `Host(id PK, name, ip, …)` | `(:Host {id: …})` + uniqueness constraint on `id` per label |
   | `reached_from(Host→Host)`  | `[:REACHED_FROM]`                        |
   | `authenticated_to(Cred→Host)` | `[:AUTHENTICATED_TO]`                 |
   | `exploited_via(Finding→Technique)` | `[:EXPLOITED_VIA]`               |
   | `found_during(Finding→Engagement)` | `[:FOUND_DURING]`                |
   | rel `props STRING` (JSON)  | rel map properties (`apoc.convert`/json at the driver layer) |
   | `MERGE (n {id}) SET …`     | identical Cypher                         |
   | iterative-deepening `[*k]` shortest path | `shortestPath((a)-[*]-(b))` — Neo4j has the real function |
   | `nodes(p)` string parsing  | driver returns real nodes/paths — no parsing |

4. Flip the front: `fronts.knowledge_graph` keeps its name, tools and args;
   internally it calls `neo4j_backend` when `KG_BACKEND=neo4j` (or when bolt
   probes alive and `KG_BACKEND=auto`), else the embedded Kùzu store. The
   SSOT row does not change.
5. Data migration out of Kùzu (one-time):
   - export nodes: `cypher` tool → `MATCH (n) RETURN label(n), properties(n)`
   - export edges: `MATCH (a)-[r]->(b) RETURN label(a), a.id, label(r),
     label(b), b.id, properties(r)`
   - load into Neo4j with the driver using the same MERGE statements the
     tools use. Idempotent; re-run safe.
6. Graphiti layer (optional, additive): feed engagement journals as episodes;
   map Graphiti entity types to Host/Credential/Finding/Technique/Engagement.
   The six tools keep operating on the deterministic hand-curated subgraph;
   Graphiti adds the temporal/inferred layer on the same Neo4j instance.

## Rollback

`KG_BACKEND=kuzu` pins the front to the embedded store at any time. The
Kùzu database directory stays the offline/single-file fallback of record
(no server, no docker needed — the property that made it the right bridge).