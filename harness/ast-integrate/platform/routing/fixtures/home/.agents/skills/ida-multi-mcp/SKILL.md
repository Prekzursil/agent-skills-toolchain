---
name: ida-multi-mcp
description: Use when you need to analyze SEVERAL binaries in IDA at once through one MCP endpoint, or when you must re-find a function whose address SHIFTED after a rebuild/game-update. Wires MeroZemory/ida-multi-mcp (a distinct, more capable server than the already-installed mrexodia/ida-pro-mcp) and its local BCSD engine — similar_functions / compare_functions rank matches by instruction-shingle MinHash plus API/string/constant anchors plus CFG shape, name-independently (survives stripping), within a binary or across instances. The keystone Battle Cats recipe — open the pinned old IDB and the new .so as two instances, then similar_functions to auto-re-locate the moved offset table after a relink. Additive and opt-in — adds NO hook, gate, or blocking behavior. Reversecore mega-bundle stays PARKED (do not wire).
origin: user
metadata:
  gem: E5-ida-multi-mcp
  upstream: https://github.com/MeroZemory/ida-multi-mcp
---

# ida-multi-mcp — multi-instance IDA + local BCSD

`MeroZemory/ida-multi-mcp` is a **multi-instance IDA Pro MCP server**: it routes one
MCP endpoint to many live IDA instances (GUI or headless `idalib`) and adds a
**local Binary Code Similarity Detection (BCSD)** engine. That engine is the point of
this skill — `similar_functions()` re-locates the *same* function in a *different*
binary by behavior, so a function whose address shifted after a rebuild is found
again automatically instead of hand-re-porting an offset table.

Everything is local — "no cloud, no external service."

## How this relates to what's already wired (read first)

The workspace already wires **`mrexodia/ida-pro-mcp`** (see the `ida-pro-mcp` and
`re-ensure` skills + the re-harness) on the GUI `:13337` / headless idalib `:8745`.
That server exposes `list_instances` / `select_instance` / `open_file` but has **no
BCSD**. `ida-multi-mcp` is a **separate, additive** server that (a) manages several
instances through a single endpoint and (b) adds `similar_functions` /
`compare_functions`. They can coexist, but **both drive IDA and idalib consumes a
license seat** — run one headless seat at a time (the re-harness registry already
guards the GUI seat on `:13337`; do not start a second headless analysis of the same
binary set concurrently). Prefer this server when the task is cross-binary
similarity; keep mrexodia for single-target GUI work.

## The keystone use case — auto-re-find a shifted offset (Battle Cats)


### Install (opt-in — user/setup step, not wired by default)
### custom IDA-matching interpreter (Windows/macOS version mismatch):
### Tool reference (verified against upstream README)
### BCSD signals (why it survives stripping)
### Reversecore stays PARKED (do not wire)
### Anti-overfit / posture
### Verify
### 2) live smoke (only after the server is installed + wired): non-empty instance list
### list_instances()  -> at least one {type: gui|idalib} row
### idalib_open(<binary>) ; index_functions(<id>) ; similar_functions(<id>, <func>)
