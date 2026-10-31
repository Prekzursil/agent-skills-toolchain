---
title: README
type: note
permalink: dqverify-repo-20261013/tools/repomap/readme
---

# `tools/repomap` — the fan-out grounding pack

`rules/common/fan-out-contract.md` §A11 prescribes injecting a **shared grounding
pack** into every fan-out:

> 16/25 agents read the same `codex_monitor.py`; 13/25 the same
> `codex-monitor.md`; one agent re-read `hub.py` **×22**. One grounding agent
> producing a pinned digest removes an estimated 60-90 tool calls in a single
> 39-agent workflow.

Nothing in this repository generated one. This is that generator: a
deterministic, stdlib-only repo map that ranks the most central files and
symbols and emits a digest sized to a token budget.

No embeddings. No vector store. No model call. Same tree in, same bytes out.

---

## Use it

```bash
# a ~900-token pack for a fan-out prompt
python tools/repomap/repo_map.py --budget 900 --out pack.md

# steer it at the area a wave is about to touch
python tools/repomap/repo_map.py --budget 900 \
    --focus tools/monitorcore/monitorcore/hub.py --mention poll_once

# drop vendored/duplicated trees that add bulk but no structure
python tools/repomap/repo_map.py --budget 900 \
    --exclude '.agents/skills/**' --exclude 'tools/crcp/vendor_src/**'

# machine-readable (ranks + digest together)
python tools/repomap/repo_map.py --budget 900 --json
```

| flag | effect |
| --- | --- |
| `--root PATH` | repository root (default `.`) |
| `--budget N` | token budget for the digest (default 1024) |
| `--focus PATH` | bias the ranking toward this file; repeatable |
| `--mention IDENT` | ×10 an identifier's edge weight, and exempt it from the ubiquity cap; repeatable |
| `--exclude GLOB` | skip repo-relative paths matching this glob; repeatable |
| `--no-git` | walk the filesystem instead of `git ls-files` |
| `--tiktoken ENC` | count tokens EXACTLY with a tiktoken encoding instead of estimating |
| `--json` / `--out` | JSON payload / also write to a file |

As a library:

```python
from repo_map import build_repo_map

pack = build_repo_map(".", budget_tokens=900, focus=["tools/monitorcore"])
print(pack.digest)            # the budgeted text
pack.definitions              # every ranked definition, most-central first
pack.included                 # the subset that fit the budget
```

Languages: Python, JavaScript/TypeScript, Shell, PowerShell, Go, Rust.

---

## How it works

Aider's repo-map technique (<https://aider.chat/2023/10/22/repomap.html>):

1. **Extract** per file the symbols it DEFINES and the symbols it REFERENCES.
2. **Build a graph over files** — an edge `referencer -> definer` per shared
   identifier, weighted by use count (`sqrt`) and by how informative the
   identifier looks.
3. **PageRank** it (pure-stdlib weighted, personalised power iteration).
4. **Distribute** each file's rank across its outgoing edges onto the
   `(definer, identifier)` pair each edge travelled over — so the output ranks
   SYMBOLS, not just files.
5. **Binary-search** the prefix length so the rendered digest is the largest one
   that fits the budget.

### Where this deviates from Aider, and why

| | Aider | here |
| --- | --- | --- |
| extraction | tree-sitter parse | per-language regex + quote-aware comment stripping |
| budget | accepts up to 15% over to exit early | **never** exceeds budget |
| ubiquitous idents | down-weighted ×0.1 | dropped above 10 definer files |
| self-references | kept | dropped |
| import evidence | (implicit in tree-sitter scoping) | explicit strong/weak edge gate |

`tree_sitter` is not importable on this box and its grammars need a compiler
toolchain on Windows, so extraction is the regex approximation the task brief
sanctioned. Stages 2-5 are unaffected by that choice.

---

## What measurement changed

The first working version produced a *plausible* ranking that was, on the real
1,386-file tree, **garbage**. Every fix below was made because the output was
measured, not because it was predicted. Each has a test, and each test is
verified to FAIL when the fix is reverted (see "Mutation" below).

| measured top-ranked symbol | why it was wrong | fix |
| --- | --- | --- |
| `timeoutMs`, `filePath` | the JS binding regex allowed leading whitespace, so every `const x = …` **inside a function** became a module symbol | bindings must start at column 0 |
| `layoutBuilders` | `const layoutBuilders = require("./layout_builders")` binds an IMPORT, not a new symbol | `definition_veto` on require/dynamic-import bindings |
| `a`, `f` | a file that defines `a` also uses it dozens of times, and that **self-reference** handed the file's whole rank to a one-letter local | no self-edges; `MIN_IDENT_LENGTH = 3` |
| `error`, `session_id` | defined in dozens of files, so they carry no information about structure — and they alone produced **1,005,573 edges** on a 1,386-node graph | drop above `MAX_DEFINER_FILES = 10` |
| `json`, `text` | a test double with `def json(self)` collected **every** `json.dumps` in the repository | import-evidence gate: unimported name matches weigh ×0.05 |
| `name`, `key` | one-word `@property` accessors absorbed every `x.name` attribute access | a module import stops counting as evidence once ≥50% of uses are attribute access |

After those six, the top of the ranking is the repository's actual core:

```
tools/taskwatch_monitor/core/models.py
   55: class TaskSpec:
  149: class PollResult:
tools/taskwatch_monitor/core/registry.py
   38: class RegistryError(ValueError):
   91: def load_registry(text: str) -> list[TaskSpec]:
  119: def load_registry_file(path: Path) -> list[TaskSpec]:
```

Residual noise, disclosed rather than hidden: test doubles (`def json`,
`def read_text`) and dataclass field names still appear below the top ~6
entries. They are genuine repo symbols that the tool cannot rank down without a
type checker. `--exclude '**/tests/**'` removes them if you want a
production-only pack.

### The token estimator was wrong too

The folklore "~4 characters per token" **under-counted every sample**, which is
the one direction that silently overruns a budget. Measured with tiktoken
`cl100k_base` over 13 digest prefix sizes (1 … 8,735 definitions) rendered from
this repository:

```
   defs     chars  tiktoken  chars/tok
      1        62        16      3.875
     25      1822       549      3.319
    500     32561       9939     3.276
   8735    477160    151846      3.142     <- worst
```

So `CHARS_PER_TOKEN = 3`, a ceiling division, with ~4.5% margin at the worst
observed point. Callers that have a real tokenizer should pass one
(`--tiktoken cl100k_base`, or `token_counter=` in the API) and get exact counts
instead.

*Confidence that divisor 3 does not under-count a cl100k-family tokenizer on
other corpora: **likely (55-80%)**. Evidence: 13 samples, one corpus, one
encoding. It is NOT proven for prose-heavy trees or for non-cl100k tokenizers —
settle it by running `--tiktoken <enc>` on the target repo and comparing against
`estimate_tokens`.*

---

## Measured, and where

Run on `agent-skills-toolchain` @ `c3c0637`, Python 3.14.6, Windows 11.

| | |
| --- | --- |
| files discovered / parsed | 1,388 / 1,386 |
| graph | 1,386 nodes, 121,481 edges |
| ranked definitions | 8,735 |
| wall clock | **10.5 s** (extract 5.4 · rank 2.4 · graph 1.3 · pagerank 1.3 · discover 0.1) |
| tests | **63 passed** (`python tools/repomap/test_repo_map.py`) |
| mutation kill rate | **12/12** |

### Two assertions do NOT run in CI

The suite is stdlib-only so it runs in the existing `gate-tests-coverage` lane
with no new dependency. Two cross-checks therefore **skip** on CI and were
measured locally instead — CI green is not evidence for either:

* `test_matches_networkx_reference_implementation` — our power iteration vs
  `networkx.pagerank` on a weighted 4-node graph with a dangling node.
  Locally: **agrees to 1e-9** (networkx 3.1).
* `test_estimator_does_not_undercount_a_real_tokenizer` — locally:
  **passes** (tiktoken 0.13.0) after the divisor fix; it FAILED (20 < 22) with
  the folklore divisor of 4, which is how that defect was found.

### Accuracy of the regex approximation vs a real parse — **UNVERIFIED**

The definition/reference extractor is regex-based, so it will disagree with a
tree-sitter parse. **The size of that disagreement has not been measured**, and
no claim here depends on it being small. `tree_sitter` is not importable on this
box, so the comparison could not be run. *Settling experiment: install
`tree_sitter` + `tree-sitter-language-pack`, extract definitions for the same
file set both ways, and report precision/recall of the regex set against the
parse.* Known-approximate by construction, in both directions:

* block comments and triple-quoted strings are **not** stripped, so identifiers
  inside them still count as references (line comments **are** stripped, with a
  quote-aware scanner so a `#` inside a string does not truncate the line);
* Python module-level bindings are recognised at column 0 only, so a
  conditionally-defined or `if TYPE_CHECKING:`-indented symbol is missed;
* an identifier's binding is never resolved to a scope — that is the whole
  reason the import-evidence gate exists.

---

## Wiring it into a fan-out

Per §A11 the pack is produced **once**, by one unit, and pinned — not rebuilt
per agent.

1. **Build it before the first spawn**, into the run's artifact root:

   ```bash
   python tools/repomap/repo_map.py --budget 900 \
       --exclude '.agents/skills/**' --exclude '**/vendor/**' \
       --out "$ARTIFACT_ROOT/GROUNDING-PACK.md"
   ```

   Add `--focus` for the files the wave is actually about; that is what moves
   the ranking toward the work instead of toward the repo's global centre.

2. **Inline it in every spawn prompt** under a fixed heading. Inline, not a
   path — §A11's whole finding is that agents re-read the same file, and a path
   is an invitation to do exactly that:

   ```
   === GROUNDING PACK (pinned; do NOT re-derive) ===
   Ranked by PageRank over symbol references. `path` then `line: signature`.
   These are the most-depended-on symbols in the tree — read the FILE only if
   you need more than the signature.
   <digest>
   ```

3. **Budget it against the prompt, not the model.** 900 tokens is roughly a
   third of a ~2,500-token spawn prompt and leaves room for the ground-truth
   block §A8 says earns its tokens. Under ~400 the digest degrades to a handful
   of files and stops being a map.

4. **Freeze it for the run** (§A10). Regenerating mid-wave leaves two cohorts
   grounded on different premises — the split-brain that let 8 agents ship
   against a premise fixed while they ran. To revise: kill cleanly, delete
   partials, restart.

5. **It is a map, not a substitute for reading.** Signatures only, no bodies.
   Pair it with §A5: any path an agent cannot `Read` at that literal location
   still needs its access method spelled out.

### What it does NOT do

* It does not replace the ground-truth block — it says where things ARE, not
  what is true about them.
* It does not rank documentation. Markdown has no symbol graph; the languages
  above are the whole surface.
* It does not track changes. Rebuild it per run; there is no cache and no state.