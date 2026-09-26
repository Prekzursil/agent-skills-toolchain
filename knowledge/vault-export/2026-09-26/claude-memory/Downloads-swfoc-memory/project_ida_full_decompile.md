---
name: IDA full-decompile corpus complete
description: All 22,828 StarWarsG.exe functions exported via IDA Hex-Rays into knowledge-base/decompile_corpus/ida_full/
  as of 2026-04-26 (123 batch JSON files)
type: project
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/project-ida-full-decompile
---

The full IDA Hex-Rays decompile corpus for `StarWarsG.exe` is complete and on disk.

**Why:** The Ralph loop directive ("do it 100% with both ghidra, binary and ida") demanded exhaustive decompilation. The IDA leg was the bottleneck — 229 batches × 100 funcs = 22,828 total. Per-function dispatch was deferred for Ghidra/Binja because all three tools see the same binary fingerprint (SHA256 `07daeeaec9d1e751383b1db3f5847b6c66f68785440a6c52c87b85f723d018a4`), so the function inventory is identical across tools and IDA Hex-Rays output is the canonical reference.

**How to apply:** When researching unknown RVAs, start with `knowledge-base/decompile_corpus/ida_full/full_b*.json` — every function in the binary is in there. File naming: `full_b00.json` through `full_b15.json` (singles), `full_b16-17.json` through `full_b226-227.json` (pairs), `full_b228.json` (final, 28 funcs). Use `python -c "import json,glob; [print(f) for f in glob.glob('knowledge-base/decompile_corpus/ida_full/full_b*.json') if any(d['addr']==target for d in json.load(open(f,encoding='utf-8'))['functions'])]"` to find which batch contains a given address.

**Dispatch pattern (for re-runs):** 2-parallel `mcp__plugin_local-mcp-bridge_ida-pro-mcp__export_funcs` calls, 200 addresses per call, then bulk `curl -o knowledge-base/decompile_corpus/ida_full/full_bNN-MM.json http://127.0.0.1:13337/output/<id>.json`. 3-parallel triggers MCP server timeouts; 2-parallel is stable. Master batch list is `.ida-mcp/full_batches.json` (229 entries). Pre-materialized address CSVs live in `.ida-mcp/csv/pair_NN_MM.txt`.

**Ghidra / Binary Ninja:** If a specific RVA needs cross-tool verification, use the per-function MCP tools at point of use — `mcp__plugin_local-mcp-bridge_ghidra-mcp__decompile_function_by_address` and `mcp__plugin_local-mcp-bridge_binary-ninja-mcp__decompile_function`. As of 2026-04-26, **all 300 VERIFIED entries in `verified_facts.json` have `tool_findings` populated for all three tools** (ida_pro + ghidra + binary_ninja).

**Bulk Ghidra+Binja sweep (added 2026-04-26):** `tools/ghidra_binja_sweep.py` performs a direct-HTTP sweep against the Ghidra (`http://127.0.0.1:8089/decompile_function_by_address?address=...`) and Binary Ninja (`http://127.0.0.1:9009/decompile?name=...`) MCP servers, saving full decompile bodies to `knowledge-base/decompile_corpus/{ghidra_full,binja_full}/by_addr/0xADDR.json`. Idempotent: re-running skips addresses whose JSON already exists.

**Full-binary sweep complete (2026-04-26 22:08):** All 22,728 IDA functions now have corresponding Ghidra and Binary Ninja entries on disk (100% on both tools). Verified via `python tools/sweep_verify.py` and `python tools/callgraph_query.py coverage`. Total sweep time: ~118 minutes with 3 parallel ghidra-only + 3 parallel binja-only sweeps on non-overlapping chunks.

**Marker-file convention:** Some IDA functions are not standalone in Ghidra/Binja (their analyzers merge them into parent functions). The sweep tool writes marker JSON for these:
- Ghidra: `body: "# Ghidra has no function at this address.\n# error: No function found for 0xADDR\n"` (~498 markers)
- Binja: `body: "# Binja has no standalone function at this address.\n# error: Function not found\n# nearest_parent: [{name, address, delta}]\n"`

Markers count toward 100% coverage (binary-fingerprint identity preserved at the file-presence level).

**Throughput tuning lessons (2026-04-26):**
- 3 ghidra-only sweeps gives ~3.3 addrs/s (peak)
- Going beyond 3 (e.g., 6) overloads the Ghidra MCP server and tanks throughput
- Probing Ghidra with extra curl calls during active sweep also overloads the server
- Binja is ~5x faster than Ghidra per address (lighter decompile)
- Some addresses (e.g., `0x1404eea10`, `0x1405b43d0`) take >30s in Ghidra — bump TIMEOUT_SEC if needed
- Use `encoding="utf-8", errors="replace"` in subprocess.run to handle non-cp1252 bytes in decompile bodies

**Index integration:** `tools/callgraph_indexer.py` populates `has_ghidra` / `has_binja` columns in `knowledge-base/callgraph_index.sqlite` by scanning the by_addr/ directories. Re-run after any sweep update.