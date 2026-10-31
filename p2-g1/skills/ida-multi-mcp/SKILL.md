---
name: ida-multi-mcp
description: Use when you need to analyze SEVERAL binaries in IDA at once through one MCP endpoint, or when you must re-find a function whose address SHIFTED after a rebuild/game-update. Wires MeroZemory/ida-multi-mcp and its local BCSD engine - similar_functions / compare_functions rank matches by instruction-shingle MinHash plus API/string/constant anchors plus CFG shape, name-independently (survives stripping), within a binary or across instances. The keystone Battle Cats recipe - open the pinned old IDB and the new .so as two instances, then similar_functions to auto-re-locate the moved offset table after a relink. Additive and opt-in - adds NO hook, gate, or blocking behavior. NOT for a single binary on the already-installed server (use ida-pro-mcp); the Reversecore mega-bundle stays PARKED.
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

When Battle Cats (or any app) ships an update the native `.so` relinks and every RVA
in the pinned offset table moves. Instead of re-porting by hand (or only diffing with
`ghidriff`), let BCSD carry the *named* old functions onto the new binary:

1. **Reference (old):** the pinned `15.4.1` IDB/`.i64` with named functions — the
   offset-table source of truth (e.g. the `NewButton` ctor documented at `0x668C70`
   in the `bc-drive` / `battlecats-event-unlock` skills).
2. **Target (new):** the updated `libnative-lib.so`.
3. Open both as instances and index them:
   ```
   idalib_open("D:/ReverseTools/.../old_15.4.1.i64")     -> instance OLD
   idalib_open("D:/ReverseTools/.../new/libnative-lib.so") -> instance NEW
   index_functions(OLD); index_functions(NEW)
   ```
4. For each pinned function, rank its twins in the new binary:
   ```
   similar_functions(instance_id=OLD, func="NewButton_ctor",
                     top_k=5, scope="instances")
   ```
   The top hit inside instance `NEW` is the shifted address. Confirm a borderline
   match with `compare_functions(old_func, candidate)` (cross-instance pairwise).
5. Write the recovered address back into the offset table; hand off to
   `bc_offset_guard` / the BC modding skills.

Because the signals are **name-independent** they survive the strip, and BCSD picks
up functions that a pure structural `ghidriff` diff misses when the CFG changed but
behavior did not — the two are complementary (diff first for the easy 1:1 renames,
BCSD for the movers).

## Install (opt-in — user/setup step, not wired by default)

```bash
python -m pip install "git+https://github.com/MeroZemory/ida-multi-mcp.git"
ida-multi-mcp --install        # installs the IDA plugin + client glue
# custom IDA-matching interpreter (Windows/macOS version mismatch):
python3.11 -m pip install --user "git+https://github.com/MeroZemory/ida-multi-mcp.git"
```

Register as an MCP server (Claude Code / Codex / Cursor):
```json
{ "command": "ida-multi-mcp", "args": [] }
```
For a non-default idalib Python: `ida-multi-mcp --idalib-python /path/to/python3.11`.

**Requirements:** IDA Pro **8.3+** (9.0+ recommended — the box has IDA Professional
9.3), Python **3.11+**. Headless `idalib` **requires a licensed IDA Pro** (IDA
Home/Free omit `idalib`). Plugin lands in `%APPDATA%\Hex-Rays\IDA Pro\plugins\` on
Windows. **Python-version match is critical** — IDA's bundled Python often differs
from your system default; check inside IDA with `import sys; print(sys.version)`
before installing, or point `--idalib-python` at the matching interpreter.

> Registering the MCP touches `~/.mcp.json`, which is **outside this skill's scope** —
> do that as an explicit, reviewed setup step (the `mcp_register` helper in the
> re-harness edits `~/.mcp.json` safely and never drops the enabled/disabled
> curation; see the "never destroy MCP enabled state" rule).

## Tool reference (verified against upstream README)

**Instance management**
- `list_instances()` — registered instances + metadata (binary, path, arch, port,
  `type`: `gui` or `idalib`).
- `refresh_tools()` — re-discover tools from active instances.
- `idalib_open(input_path, timeout, unsafe)` — spawn a headless session, auto-analyze,
  register with a generated `instance_id`.
- `idalib_close(instance_id)` — terminate + deregister a headless session.
- `idalib_list()` / `idalib_status(instance_id)` — enumerate / health-check headless
  sessions.

**Similarity (BCSD)**
- `similar_functions(instance_id, func, top_k=20, scope="binary"|"instances"|"all")`
  — rank the most similar functions within one binary or across instances; returns a
  per-signal breakdown plus a confidence score.
- `compare_functions(a, b)` — direct pairwise similarity between two functions
  (optionally cross-instance).
- `index_functions(instance_id, rebuild=False)` — build/refresh the searchable index.
- `index_status(instance_id)` — index readiness, function count, staleness, background
  progress.

**Plus ~80 IDA tools** auto-discovered per instance (`decompile`, `survey_binary`,
`func_query`, `imports_query`, `xrefs_*`, `list_funcs`, `find_*`, …). **Every tool
call takes an `instance_id`.**

**Instance IDs** are 4-char base36 (`0-9 a-z`) like `k7m2`, `px3a`, `9bf1`,
deterministic from pid + port + IDB path (reopening the same binary yields the same
id; auto-expands to 5 chars on collision). Registry on Windows:
`%USERPROFILE%\.ida-mcp\instances.json`.

## BCSD signals (why it survives stripping)

`similar_functions` combines, name-independently:
- **instruction-shingle MinHash** (n-gram of the instruction stream),
- **IDF-weighted anchors** — imported-API / string / constant references,
- **CFG structure / shape**,
- **symbol-gated pseudocode tokens**.

**Optional neural recall** for anchor-less cross-compiler twins the lexical/structural
signals miss:
```bash
pip install "ida-multi-mcp[neural]"     # extra
setx IDA_MCP_SIM_NEURAL 1               # enable (jTrans embeddings)
```
The jTrans model auto-downloads to `~/.ida-mcp/models/` and runs **locally**. Leave it
OFF by default (RAM + first-run download); flip it on only when MinHash+anchors return
low confidence on a known-moved function.

## Reversecore stays PARKED (do not wire)

The `E.5` gem pairs this with the **Reversecore** mega-bundle (angr + Qiling +
Volatility3 + binwalk + CAPA). Per the council it is **park-by-default** — do NOT wire
it here. The capabilities the workspace actually wants from it already ride existing,
leaner buses: `qiling-emulation` (skill), planned angr-MCP into the re-harness,
`capa-triage`, `radare2`/`ghidra-mcp`. Cherry-pick, never adopt the bundle.

## Anti-overfit / posture

- **Rides the existing RE bus** — same IDA + idalib + re-harness seat model as the
  wired `ida-pro-mcp`; local-only; no vector-DB, no second orchestration runtime.
- **Purely additive** — this skill adds no hook, no gate, nothing that blocks or nags.
- **Advisory** — a BCSD "match" is a ranked hypothesis; confirm the recovered address
  by decompiling both sides (`compare_functions` + a `decompile` eyeball) before you
  trust it as an offset. Do not act on a low-confidence twin (the "acting on stale
  offsets" failure the `bc_offset_guard` module exists to prevent).

## Verify

```bash
# 1) skill is well-formed / vault-admissible (frontmatter parses, no angle brackets in description)
python - <<'PY'
import re, pathlib
p = pathlib.Path.home()/".claude/skills/ida-multi-mcp/SKILL.md"
t = p.read_text(encoding="utf-8"); fm = t.split("---",2)[1]
assert "\nname: ida-multi-mcp" in fm and "\ndescription:" in fm, "frontmatter missing"
desc = re.search(r"\ndescription:\s*(.+)", fm).group(1)
assert "<" not in desc and ">" not in desc, "angle bracket in description breaks quick_validate"
print("SUCCESS ida-multi-mcp SKILL.md well-formed")
PY

# 2) live smoke (only after the server is installed + wired): non-empty instance list
#    list_instances()  -> at least one {type: gui|idalib} row
#    idalib_open(<binary>) ; index_functions(<id>) ; similar_functions(<id>, <func>)
```
