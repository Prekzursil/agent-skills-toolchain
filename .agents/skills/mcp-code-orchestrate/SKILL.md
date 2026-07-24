---
name: mcp-code-orchestrate
description: Use when one task needs the SAME tool-call shape repeated across MANY items - an xref-walk over many functions, a descriptor sweep over many SMILES, or one query across several MCP servers. Write ONE script (Python via the Bash tool) that calls the provider CLIs, native libraries, or MCP stdio, filters IN-CODE, and returns ONLY the distilled result. Reach for it past ~5 same-shape calls.
license: MIT
---

# MCP Code Orchestrate

> **The 98.7% fan-out token-cut.** When you would otherwise call the same MCP
> tool N times and let every raw result land in the context window, write **one
> script** that does the loop, filters/aggregates **in code**, and returns only
> the distilled answer. Anthropic's "Code execution with MCP" reports a single
> example dropping from ~150,000 tokens of tool chatter to ~2,000 (≈98.7% fewer)
> by moving the fan-out into code instead of the model loop.

## The pattern in one breath

Direct tool-calling is right for **one** call: ask, get the answer, done. It is
*pathological* for **fan-out** — "enumerate-then-filter" across the 39-server MCP
fleet — because:

1. Every tool *definition* you load is paid for on every turn (catalogue tax).
2. Every tool *result* (a 4 KB JSON blob × N functions / molecules / papers)
   is dumped verbatim into context, and the model re-reads all of it each turn.
3. The model is doing a mechanical loop (iterate, test a predicate, collect hits)
   that a `for` loop does for free, deterministically, off-context.

The fix: the agent writes **one Python script** (run via the **Bash** tool) that
calls the *underlying* provider — its native CLI/library when one exists, else
the MCP server over stdio/HTTP — loops over all the items, applies the filter in
code, and **prints only the distilled result** (a shortlist, a count, the 12
hits out of 4,000). Raw payloads stay on disk / in process memory; only the
answer enters the conversation.

## Decision rule (use this / don't)

| Situation | Do |
|---|---|
| One lookup, one answer | **Call the tool directly** (or load its schema with ToolSearch). Do NOT write a script. |
| The same call shape **> ~5 times** (a loop over functions / SMILES / DOIs / URLs) | **Code-orchestrate** — one script, filter in code, return the distilled result. |
| Enumerate a large set, keep only the few that match a predicate | **Code-orchestrate.** |
| Aggregate / cross-corroborate one query across several MCP servers | **Code-orchestrate** (fan out in code, merge, dedupe, rank, return top-N). |
| You need the model to *reason* between each call (each depends on the last) | Direct calls — the loop is not mechanical. |

Rule of thumb: **if you can describe the loop and the keep-predicate in one
sentence, script it.** If each step needs fresh model judgement, don't.

Pairs with **ToolSearch** (deferred-tool loading): ToolSearch is the complement
for the *single*-call case — it fetches one tool's schema on demand so the
catalogue stays small. Code-orchestrate handles the *many*-call case so the
*results* stay out of context. Use both: keep the listed-tool count low
(ToolSearch) **and** the returned-token count low (code-orchestrate).

## How a script reaches a provider — three access modes

Prefer them in this order (cheapest/most-robust first):

### 1. Native CLI or Python library (best — zero MCP overhead)

Many MCP servers are thin wrappers over a library or CLI you can call directly:

- **rdkit** MCP → `from rdkit import Chem` (the actual library).
- **radare2** MCP → `r2pipe` / `r2 -c '<cmds>' -q binary`.
- **github** MCP → `gh api ...`.
- **android/adb** → `adb shell ...`.
- **paper metadata** → the upstream REST APIs (Crossref / OpenAlex / Unpaywall)
  with `requests` (all key-free).

No JSON-RPC, no server spawn, full speed. Reach for this whenever it exists.

### 2. MCP server over stdio (one session, many calls)

When the only access is the MCP server, spawn it **once** and reuse the session
for all N calls (amortise the startup over the whole fan-out). Drop this helper
into your script (MCP stdio transport = newline-delimited JSON-RPC):

```python
import json, subprocess

class MCPSession:
    """One stdio MCP server, initialized once, called many times."""
    def __init__(self, cmd, env=None):
        self.p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        self._id = 0
        self._send({"jsonrpc": "2.0", "id": self._next(), "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "orch", "version": "1"}}})
        self._recv()  # initialize result
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _next(self):
        self._id += 1
        return self._id

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _recv(self):
        for line in self.p.stdout:
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        return None

    def call(self, tool, arguments):
        rid = self._next()
        self._send({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments}})
        while (msg := self._recv()) is not None:
            if msg.get("id") == rid:
                return msg.get("result")
        return None

    def close(self):
        try:
            self.p.terminate()
        except Exception:
            pass

# Example: spawn once, loop many.
# sess = MCPSession(["npx", "-y", "mcp-searxng@1.8.0"],
#                   env={**os.environ, "SEARXNG_URL": "http://127.0.0.1:8890"})
# hits = [sess.call("searxng_web_search", {"query": q}) for q in queries]
# sess.close()
```

### 3. MCP server over HTTP (already-running servers)

For HTTP-transport MCPs the fleet keeps up (e.g. basic-memory on `:8765`), POST
JSON-RPC with `requests` — no spawn at all. The IDA GUI MCP is reachable the
same way (`POST http://127.0.0.1:13337/mcp`); it is **read-only-safe** to query
in a loop but **never** tear it down.

## Concrete recipes

These are runnable templates — adapt the path/predicate, run via the Bash tool,
and read back only what they print.

### (a) RE xref-walk — find the hot functions across a whole binary

Goal: of thousands of functions, return only the few that are called from many
sites (likely shared helpers / good hook anchors). Direct tool-calling would
need one `get_xrefs_to` round-trip per function; the script does it in one pass
and returns the top-20.

```python
import json, r2pipe

THRESHOLD = 15
r2 = r2pipe.open("/path/to/lib.so", flags=["-2"])  # -2 silences stderr
r2.cmd("aa")                                        # or: r2.cmd("Po project")
hits = []
for fn in r2.cmdj("aflj") or []:                    # every function, as JSON
    xrefs = r2.cmdj(f"axtj @ {fn['offset']}") or []  # xrefs TO this function
    if len(xrefs) >= THRESHOLD:
        hits.append({"name": fn["name"], "addr": hex(fn["offset"]),
                     "callers": len(xrefs), "size": fn.get("size", 0)})
r2.quit()
hits.sort(key=lambda h: -h["callers"])
print(f"{len(hits)} functions with >= {THRESHOLD} callers")
print(json.dumps(hits[:20], indent=2))             # only the top-20 enter context
```

IDA/Ghidra-MCP variant: same loop, but `MCPSession.call("get_xrefs_to", {...})`
(stdio) or a `requests.post(":13337/mcp", ...)` loop (HTTP) instead of `axtj`.
Collect only the addresses whose caller-count passes the predicate.

### (b) Chemistry descriptor sweep over many SMILES (Lipinski screen)

Goal: from a list of candidate molecules, keep only the drug-like ones. Calling
the rdkit MCP once per descriptor per molecule is hundreds of round-trips; the
library does it locally and returns only the passers.

```python
import json
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen

smiles = [s for s in open("candidates.smi").read().split() if s]
kept = []
for smi in smiles:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        continue
    mw, logp = Descriptors.MolWt(m), Crippen.MolLogP(m)
    hbd, hba, tpsa = Descriptors.NumHDonors(m), Descriptors.NumHAcceptors(m), Descriptors.TPSA(m)
    if mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10:   # Lipinski, in code
        kept.append({"smiles": smi, "mw": round(mw, 1), "logp": round(logp, 2),
                     "tpsa": round(tpsa, 1)})
print(f"{len(kept)}/{len(smiles)} pass Lipinski Ro5")
print(json.dumps(sorted(kept, key=lambda r: r["mw"])[:20], indent=2))
```

(Same shape for a Tanimoto similarity sweep: build one query fingerprint, loop a
library of SMILES, keep only `sim >= cutoff`.)

### (c) Paper batch-resolve / screen across the paper-search fleet

Goal: turn a list of DOIs into a screened, ranked shortlist. Key-free Crossref
covers metadata directly; escalate to the paper-search / scholarly-access MCP
(stdio, via `MCPSession`) only for the survivors that need an OA-PDF resolve.

```python
import json, time, requests

dois = [d.strip() for d in open("dois.txt") if d.strip()]
kept = []
for doi in dois:
    r = requests.get(f"https://api.crossref.org/works/{doi}",
                     headers={"User-Agent": "research-harness (mailto:you@example.com)"},
                     timeout=20)
    if r.status_code != 200:
        continue
    msg = r.json()["message"]
    year = (msg.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0]
    cites = msg.get("is-referenced-by-count", 0)
    if year and year >= 2020 and cites >= 10:           # recency + impact screen
        kept.append({"doi": doi, "title": (msg.get("title") or [""])[0],
                     "year": year, "cites": cites})
    time.sleep(0.2)                                      # be polite to the API
kept.sort(key=lambda x: -x["cites"])
print(f"{len(kept)}/{len(dois)} pass the 2020+/10-cite screen")
print(json.dumps(kept, indent=2))
```

Only the shortlist (titles + DOIs + counts) enters context — not the full
Crossref record for every DOI.

### (d) Multi-source research aggregation (fan out, merge, rank)

Goal: one query, several providers, a single deduped/ranked result. Fan out in
code, merge on URL, rank by how many independent providers returned each URL
(in-code corroboration — feeds straight into `deep-research`'s grader).

```python
import json, os
# ... MCPSession from mode 2 above ...

query = "post-quantum signature scheme adoption 2026"
results = {}   # url -> {"title":..., "providers": set()}

def absorb(provider, items):
    for it in items or []:
        url = it.get("url") or it.get("link")
        if not url:
            continue
        row = results.setdefault(url, {"title": it.get("title", ""), "providers": set()})
        row["providers"].add(provider)

searx = MCPSession(["npx", "-y", "mcp-searxng@1.8.0"],
                   env={**os.environ, "SEARXNG_URL": "http://127.0.0.1:8890"})
absorb("searxng", (searx.call("searxng_web_search", {"query": query}) or {}).get("results"))
searx.close()
# ...absorb("exa", ...), absorb("tavily", ...) the same way...

ranked = sorted(results.items(), key=lambda kv: -len(kv[1]["providers"]))
out = [{"url": u, "title": d["title"], "corroboration": len(d["providers"]),
        "providers": sorted(d["providers"])} for u, d in ranked[:15]]
print(json.dumps(out, indent=2))   # top-15 by cross-provider corroboration
```

## Output discipline (so the win is real)

- **Print only the distilled result** — a shortlist, a count, the hits. Never
  `print()` the raw per-item payloads; that re-imports the bloat you were
  avoiding. Write raw output to a temp file if you must keep it, and report the
  path (this is the `context-sandbox` skill's rule).
- **End with a terminal-state line** the orchestrator can read at a glance, e.g.
  `KEPT 12/4180 functions` or `SHORTLIST 8 papers -> shortlist.json`.
- **Make it idempotent & re-runnable** — read inputs from a file/argv, not from
  pasted-in context, so a re-run is one Bash call, not a re-derivation.
- **Handle the empty/None case** — a flaky provider or unparsable item should
  `continue`, not crash the whole sweep. The point is to finish the fan-out.
- **Long sweeps (> ~60s)** go through `longrun` in the background (AGENTS.md §4a),
  not a blocking foreground call.

## When NOT to use this

- A single tool call — just call it (optionally `ToolSearch` its schema first).
- Steps that each need the model to reason on the previous result — the loop
  isn't mechanical, so code can't stand in for the model.
- Writes/mutations you can't safely batch (e.g. one-shot game patches) — keep a
  human/agent in the loop per step.

## References

- Anthropic Engineering — **"Code execution with MCP: building more efficient
  agents"** (2025): the canonical write-up of this pattern and the ~98.7%
  token-reduction example (≈150k → ≈2k tokens on a fan-out task).
- Anthropic Engineering — **"Writing effective tools for agents"** and the
  **Claude Agent SDK** docs (tool/observation design; why mechanical loops
  belong in code, not the model turn).
- **Model Context Protocol** spec — *Transports* (stdio = newline-delimited
  JSON-RPC; Streamable HTTP) for the `MCPSession` / HTTP access modes.
- Sibling skills: `context-sandbox` (sandbox raw payloads, surface only the
  answer), `deep-research` (the routing/grading harness this feeds), and
  `ToolSearch` deferred-tool loading (the single-call complement).
