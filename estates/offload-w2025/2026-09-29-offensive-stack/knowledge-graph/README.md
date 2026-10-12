# knowledge-graph — shared estate graph store (embedded Kùzu)

One graph store for the estate: hosts, credentials, findings, techniques and
engagements, with the attack-path edges between them. Consumed through the
gateway (`harness_invoke backend="knowledge-graph"`), owned by no one else.

## Layout

```
D:\opt\knowledge-graph\
├── kgcore.py            schema + the six tools (import this for library use)
├── kuzucapi.py          ctypes binding of the official prebuilt Kuzu C API
├── _dist\libkuzu\       kuzu_shared.dll + kuzu.h/.hpp + kuzu_shared.lib
│                        (github.com/kuzudb/kuzu release v0.11.3,
│                         asset libkuzu-windows-x86_64.zip, 4931545 bytes,
│                         zip sha256 8c2297955f98cf23b45c3f69935e4eebc6672dac2e2fa00973f6eaae00d20259,
│                         kuzu_shared.dll sha256 a6dc4402b8550752ab4cee46b77f63bbd29fbc0fed16965b21bee5282ee59ff4)
├── db                   the embedded database - a single Kuzu storage file
│                        (plus db.wal beside it; created on first open;
│                        env KG_DB_PATH overrides the path)
├── NEO4J-MIGRATION.md   the Graphiti/Neo4j path for the docker era
└── README.md            this file
```

Gateway wiring: `D:\opt\cyberstrike-mcp\fronts\knowledge_graph.py`
(SSOT row `knowledge-graph`, kind=module).

## Why the ctypes binding (2026-09-29)

`pip install kuzu` into C:\Python314 fails on Windows and cannot be fixed:
no cp314 win_amd64 wheel exists on PyPI (any release), the sdist dies on
MAX_PATH at extraction, there is no C/C++ toolchain on the VM, and upstream
is archived (final release 0.11.3, 2025-10-10). `kuzucapi.py` binds the
official v0.11.3 `kuzu_shared.dll` directly — same engine, same file format
as the PyPI package. When the docker-era swap to Neo4j/Graphiti happens,
`NEO4J-MIGRATION.md` is the playbook; a real `kuzu` wheel (different Python)
would slot in behind `kgcore.py` unchanged.

## Schema

Node tables (PRIMARY KEY `id STRING`; `props` column holds unknown fields as
JSON text; `notes` is free text):

| label       | fixed columns |
|-------------|---------------|
| Host        | name, ip, os, status, owner, notes |
| Credential  | kind, principal, secret_ref, realm, notes |
| Finding     | title, severity, target_ref, notes |
| Technique   | name, mitre_id, tactic, notes |
| Engagement  | name, status, scope, started, ended, notes |

Rel tables (all carry `props STRING` JSON):

| rel              | from → to          | meaning (stored direction) |
|------------------|--------------------|----------------------------|
| `reached_from`   | Host → Host        | attacker moved from → to (lateral movement pivot) |
| `authenticated_to`| Credential → Host | credential authenticates to the host |
| `exploited_via`  | Finding → Technique| the finding was achieved via the technique |
| `found_during`   | Finding → Engagement | the finding belongs to the engagement |

Secrets policy: `Credential.secret_ref` is an indirection (env var name,
vault path, sha8) — raw secret values stay out of the graph.

## Tools (args are one JSON object)

| tool | args | notes |
|------|------|-------|
| `add_node` | `label, id, props{}` | upsert (MERGE on id); unknown props → JSON `props` column |
| `add_edge` | `type, from_id, to_id, props{}` | create-or-update one edge of the named type; endpoint labels enforced by schema |
| `neighbors` | `id, label?, rel?, direction=out\|in\|both, limit` | adjacent nodes with rel + direction + props |
| `shortest_path` | `src, dst, src_label?, dst_label?, max_hops` | iterative deepening over exact-depth matches (Kùzu 0.11.3 has no shortestPath()); undirected across all rel types; returns parsed hops + raw `nodes(p)` |
| `search` | `q, limit` | case-insensitive substring over id/name/title/notes/props; empty `q` → per-label counts |
| `cypher` | `query, max_rows` | raw Cypher passthrough (read AND write); cells are string-rendered |

## Engine notes (verified live against 0.11.3 on this VM)

- `MERGE` works for nodes and rels; `SET` **immediately after** a rel-MERGE
  hard-fails the engine (state=1) — props updates are a separate MATCH+SET.
- `shortestPath()` / `SHORTEST k` / `ANY SHORTEST` do not parse in 0.11.3;
  exact-depth var-length matches (`[*k]`) do — that is what `shortest_path`
  iterates. Undirected traversal (`-[*]-`) crosses stored edge directions.
- List comprehensions over `nodes(p)` are unsupported; hop lists are parsed
  from the `nodes(p)` rendering (best-effort for exotic `id` values; the raw
  rendering is always included as `path_raw`).
- A failed Cypher statement returns `state=1` from `kuzu_connection_query`
  but the result object still carries the binder/parser error message — the
  binding surfaces it as `{"ok": false, "error": ...}`.
- `label(n)` / `label(r)` give node/rel types; `type(r)` hard-fails.

## Quick use (direct, without the gateway)

```python
import sys; sys.path.insert(0, r"D:\opt\knowledge-graph")
import kgcore, json
print(kgcore.run("add_node", {"label": "Host", "id": "h-01", "props": {"name": "alpha"}}))
print(kgcore.run("add_edge", {"type": "reached_from", "from_id": "h-01", "to_id": "h-02"}))
print(kgcore.run("shortest_path", {"src": "h-01", "dst": "h-02"}))
kgcore.close()
```

Through the gateway (after gateway restart):

```
harness_invoke backend="knowledge-graph" tool="shortest_path"
               arguments='{"src":"h-01","dst":"h-02"}'
```

Concurrency: one Connection, every query serialized by a lock; safe to call
from any gateway thread. The DB directory is locked by Kùzu while open, so
only one writer process at a time (the gateway) — open other processes
read-only if ever needed.
