# Adversarial validation: lane `native-features`

Lane: **validate-native-features** · Host: OFFLOAD-W2025 · Date: 2026-09-25
Status: **COMPLETE.** Every verdict below is measured. No claim is carried over from the
implementer's report without an independent instrument.

**Instrument discipline.** The implementer read the binary at FIXED BYTE OFFSETS
(`0xc10e57d`, `0xc694d40`, `0xc8d4b13`, …). I never used an offset. Every binary claim below
was re-derived by **pattern-addressed scan** (`re.finditer` over the whole 244,960,928 B file,
reporting every hit and its neighbourhood), and every vocabulary claim by reading the
**complete array literal**, not a prefix. Scripts:
`<scratch>/scan_binary.py`, `scan2.py`, `scan3.py`. File facts came from opening the files.

---

## Verdict table

| # | Claimed gem | Claimed | **My verdict** | Different instrument used |
|---|---|---|---|---|
| a | `omitClaudeMd` on reader/docs-lookup | implemented | **CONFIRMED** | pattern scan; full `var v` + `var sp` arrays; read both files |
| b | `maxTurns` 30/20 | implemented | **CONFIRMED** (+ their residual CLOSED) | parser error-string region + `brt()` notification builder |
| c | `mcpServers` premise refuted | skipped | **CONFIRMED** | my own frontmatter recount of all 20 agents; settings.json parse |
| d | `effort` / `context: fork` declined | skipped | **CONFIRMED** | skill zod schema + the parser's `has invalid effort` error string + live count |
| e | `paths:` gates the LISTING | partial | **CONFIRMED** | loader body re-found by pattern, not offset |
| G | `lint-frontmatter-keys.py` gate | implemented | **OVERCLAIM** | 4 both-states tests I authored + 1 instrument-failure test |
| F1 | security-reviewer dead keys | implemented | **OVERCLAIM** (fix right, evidence false) | unquoted-needle counts + full vocabulary array |
| F2 | `allowed_tools` typo | implemented | **OVERCLAIM — severity INVERTED** | read the permission-layer applier `d()` body |

Nothing is REFUTED outright. Three items are OVERCLAIMS: in each the **code is right and the
sentence is wider than the evidence** — the estate's dominant failure shape.

---

## Ground facts I re-measured (all CONFIRMED)

| Fact | Their number | Mine | Instrument |
|---|---|---|---|
| binary size | 244,960,928 B | **244,960,928 B** | `ls -la` on both hardlinked copies |
| version | 2.1.283 | **2.1.283** | `package.json` `"version"` **and** the in-chunk `// Version: 2.1.283` banner |
| `~/.local/bin/claude.exe` absent | absent | **absent** | `ls` → No such file |
| parser vocabulary | 61 keys | **61 keys** (counted item by item) | full `var v` array read whole |
| agent projection | 17 keys | **17 keys** | full `var sp` array read whole |
| agents carrying `tools:` | 20/20 | **20/20, 0 missing** | my own frontmatter parser over `~/.claude/agents` |
| agents carrying `effort:` | 9 | **9** | same |
| `ENABLE_TOOL_SEARCH` | `"true"` | **`"true"`** | `ConvertFrom-Json` on settings.json |

**Corpus byte drift, as they predicted.** CLAUDE.md corpus is now **42,904 B**, not 41,884 B —
`~/.claude/CLAUDE.md` grew 9,384 → 10,404 B (the sibling lane's `# Compact instructions`).
They labelled their figure "a point-in-time floor"; it drifted exactly as stated. Honestly
scoped, so CONFIRMED rather than OVERCLAIM. The saving got *larger*, not smaller.

---

## (a) `omitClaudeMd` — CONFIRMED

- Pattern scan: `omitClaudeMd` = **28 hits**. The zod schema neighbourhood carries the
  describe() string **verbatim as quoted**: "Run this agent without the user, project and local
  CLAUDE.md instruction files when it runs as a subagent; managed policy files are kept…".
- Present in **both** arrays I read whole — `var v` (61 keys) and `var sp` (17 keys).
- Their first-party precedent is real: the two bundled `claude-test` agents ship
  `omitClaudeMd: true`. I confirmed their honest counter-evidence too — the `runner` one carries
  `tools: Read, Edit, Write, Bash, ToolSearch, …`, i.e. Anthropic does ship the flag on a
  mutation-capable agent. They disclosed this against their own decision. Good faith.
- Both edited files open and parse: `reader.md` (`tools: ["Read","Grep","Glob"]`,
  `omitClaudeMd: true`, `maxTurns: 30`), `docs-lookup.md` (`tools: ["Read","Grep",
  2×mcp__context7__*]`, `omitClaudeMd: true`, `maxTurns: 20`).

**One scoped correction, inside their RISK note, not the gem:** "neither can mutate or egress".
`docs-lookup` holds `mcp__context7__resolve-library-id` and `mcp__context7__query-docs` — those
are outbound network calls. Correct wording: *neither can MUTATE; `reader` cannot egress either,
`docs-lookup` egresses a library name and a question to Context7.* It does not change the
decision (no write/shell tool, and the agent body already carries its own prompt-injection
clause), but "cannot egress" is false for one of the two.

## (b) `maxTurns` — CONFIRMED, and their open residual is now CLOSED

- Schema confirmed by pattern: `maxTurns:E().int().positive().optional().describe("Maximum
  number of agentic turns (API round-trips) before stopping")`.
- **Second, independent signal they did not have:** the parser's own error table carries
  `` has invalid maxTurns '…'. Must be a positive integer `` — a different code region
  (validation messages, not the zod schema). Two mechanically independent signals.
- **Their residual UNVERIFIED — "whether hitting the cap returns partial output or an error" —
  is SETTLED, in the benign direction.** The notification builder `brt({…maxTurnsReached:w…})`
  computes
  `` Oe = w ? `stopped at its ${w}-turn limit (partial result; ${lo} to task-id to continue)` : … ``
  and is invoked with `status:"completed"`. So cap exhaustion = **completed with a partial
  result and a resume hint**, not a failure. Their stated risk ("a long recon could fail instead
  of degrading") does not materialise. Confidence: almost certain (90-99%).

## (c) `mcpServers` premise refuted — CONFIRMED

My own frontmatter scan (not theirs): **20 agent files, 20 carry `tools:`, 0 missing.** The
`tools` describe() I re-found confirms the inheritance rule verbatim: "Array of allowed tool
names. If omitted, inherits all tools from parent." The `disallowedTools` describe() confirms
the documented removal lever verbatim, including "MCP server-level specs (mcp__server,
mcp__server__*, mcp__*) remove every tool from the named server (or all MCP tools)."
`mcpServers` is in the 61-key array and carries no describe(). **Declining to add an unproven
key to a live config was the correct call**, and a refuted premise is a valid result.

## (d) `effort` / `context: fork` declined — CONFIRMED

Support is real: the skill schema carries `paths`, `hooks`, `context:z(["inline","fork"])`
("`inline` expands into the current conversation; `fork` spawns a subagent") and "Agent type to
spawn when context: fork." `effort` is in the 61-key array, 9 live agents use it, and the parser
emits `` has invalid effort '…'. Valid options: … or an integer `` — three signals. Not
applying it is a judgement call, labelled as one.

## (e) `paths:` gates the LISTING — CONFIRMED

Re-found by pattern (their offset never used). The loader body is verbatim as quoted:

```js
let ze = He.type==="prompt" && !!He.paths && He.paths.length>0;
… if(ze && !je.activatedConditionalSkillNames.has(He.name)) Fe.push(He); else Le.push(He)}
for(let He of Fe) je.conditionalSkills.set(He.name,He);
… return t(`Loaded ${Pe.length} unique skills (…)`), Le
```

`Le` is returned; a skill with non-empty `paths` lands in `Fe` and is **absent from the returned
set** until activated. The lever is real; so is the discoverability cost. Applied to zero live
skills, so there is no live risk to validate. Their refusal to retrofit 468 files on an unsettled
name-invocation question is the correct reading of Hard Rule 3.

---

## (G) The lint gate — OVERCLAIM (works; the sentence and two counts are wider)

### I broke it myself. It fires. Both-states INDEPENDENTLY proven.

I did not re-run their `--selftest`. I authored new inputs:

| My test | Input | Result |
|---|---|---|
| 1 GOOD | 6 supported keys they never exercised (`permissionMode`, `isolation`, `background`, `memory`, `initialPrompt`, `skills`) | `SUCCESS … 0 unsupported keys` **EXIT=0** |
| 2 BROKEN | 4 dead keys they never used (`parallelism`, `timeoutSeconds`, `retryPolicy`, `allowed_tools`) | **4 ERRORs, EXIT=1**, each named with line number |
| 3 EVASION | the *same two* real defect keys, YAML-**quoted** | **0 errors, EXIT=0 — FALSE NEGATIVE** |
| 4 INSTRUMENT | `CLAUDE_BINARY` → a decoy text file | `FAILED … anchor not found` **EXIT=2** |

Tests 1+2 are a genuine both-states proof on inputs of my own construction. Test 4 confirms
"fail closed on the instrument" — a broken detector cannot emit a green.

### Defect I found: quoted frontmatter keys evade the gate

`_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_.-]*)\s*:")` cannot match a key that starts with `"`
or `'`. YAML accepts `"fallbacks": […]` as identical to `fallbacks: […]`, and `Bun.YAML.parse`
would too — so **the exact defect this gate exists to catch passes it under a legal
spelling.** Reproduced above as Test 3.
Severity **LOW, latent not active**: I scanned all 563 live entry points — **0 quoted-key
frontmatter lines**. One-line fix: allow an optional quote in `_KEY` and strip it.
Consequence: *"Retires the entire CLASS of silent-drop frontmatter defect"* is an overclaim.
Correctly scoped: **retires the UNQUOTED spelling of that class.**

### Two numeric provenance errors

- **"scanned 2130 files"** — the *narrowed* gate scans **563** (= 20 agents + 75 commands + 468
  SKILL.md, which sums exactly). 2130 is the pre-narrowing run they themselves fixed. The
  artifact labels it; the summary presents it as the final run's number.
- **"11 dead keys"** is arithmetically impossible against their own account: I measure **10
  ERRORs remaining** and they fixed **3** key occurrences → **13 found / 3 fixed / 10
  remaining**. The 10 remaining match their `not_attempted` list *exactly* (7× `command`,
  `tags`, 2× `category`), so only the headline total is wrong — most likely a mid-sequence
  snapshot taken after the first fix.

### What holds

Anchoring on array literals instead of byte offsets is the right design and it worked on my
run. Zero always-on context cost (manual/CI script, deliberately not a hook) is correct and
consistent with the sweep's purpose. Their self-correction about the first run's false positives
against `skills/*/rules/*.md` is recorded in the artifact, not hidden.

**Residual robustness caveat (mine, new):** `_read_array` takes `data.find(anchor)` — the FIRST
match. At least **two** arrays share the `PARSER_ANCHOR` prefix (`var v`, 61 keys; and a second
`var Vd` = `["name","description","model","allowed-tools","disallowed-tools","disallowedTools",…]`).
Today `var v` is found first and is the right one. A future chunk reordering could silently bind
the gate to the other array — which fails toward **false positives**, not a false green, so it
is a maintenance risk rather than a safety hole.

## (F1) security-reviewer dead keys — OVERCLAIM (the fix is right; the evidence sentence is false)

**The fix is CORRECT.** Neither `fallbacks` nor `server-side-fallback` is in the 61-key array I
read whole, so neither was ever in force. The file now carries 6 keys plus a 5-line provenance
comment naming the guard command; it parses.

**But the evidence as written is false.** Their probes were quote-scoped, which made a real
product feature look byte-absent:

| Their claim | My unquoted measurement |
|---|---|
| `NEEDLE '"server-side-fallback"' COUNT=0` | `server-side-fallback` = **11 hits** — live beta-header names `server-side-fallback-2026-06-01`, `server-side-fallback-2026-07-01` |
| `NEEDLE 'serverSideFallback' COUNT=0` | true for camelCase, but **`server_side_fallback` exists** as a snake_case feature key |
| "the single `"fallbacks"` hit is an unrelated Bun HTTP body builder" | bare `fallbacks` = **33 hits**, including a dedicated API error classifier: `` `fallback` and `fallbacks` cannot both be set ``, `` The `fallbacks?` parameter is not supported ``, `is not a valid fallback target for` |

So the script docstring's *"byte-absent from the 245 MB binary"* (lines 14-15) is wrong, and the
overclaim is **shipped inside the tool**, not only in the report.

**Second, sharper overclaim:** "There is no supported per-agent equivalent; model fallback is
server-side only." The 61-key vocabulary **does contain singular `"fallback"`**. Whether it is
agent-applicable is untested — so the correct statement is *"no per-agent equivalent was found
under these spellings; a singular `fallback` key exists in the parser vocabulary and was not
tested."*

**Correctly-scoped claim:** *`fallbacks` and `server-side-fallback` are absent from the
frontmatter key vocabulary, so both were silently dropped and the intended fallback was never in
force. Server-side model fallback IS a real product feature — it is configured through API beta
headers and a request parameter, not through agent frontmatter. A singular `fallback` key does
appear in the vocabulary and remains untested.*

## (F2) `allowed_tools` typo — OVERCLAIM, severity **INVERTED**

**The rename is CORRECT.** I confirmed the parser reads the hyphen form only:

- skill/command zod schema: `"allowed-tools":yE().optional()…`, `"disallowed-tools"`, plus
  `disallowedTools` explicitly described as "Canonical (normalized) alias of `disallowed-tools`."
  There is **no** alias for the allowed side.
- parser body: `ye = ge ? [] : hy(e["allowed-tools"])` and `ke = w["allowed-tools"]`. Compare the
  disallowed side, which *does* fall back: `hy(e["disallowed-tools"] ?? e.disallowedTools)`.
- `allowed_tools` (underscore) = 47 hits, and **every JS-context one** is either a
  `permissionLayers` discriminator (`kind:"allowed_tools"`) or a **cloud-session wire field**
  (`allowed_tools: e.allowedTools` in a request body). **None is a frontmatter alias.**

**But the severity claim is refuted by the applier's own body.** I read `d()` verbatim:

```js
function d(e,o){if(o.length===0)return e;
  return{...e, alwaysAllowRules:{...e.alwaysAllowRules, command:L([...e.alwaysAllowRules.command||[], ...o])}}}
function u(e,o){if(o.length===0)return e;
  return{...e, alwaysDenyRules:{...e.alwaysDenyRules, command:L([...e.alwaysDenyRules.command||[], ...o])}}}
```

and its call site `case"allowed_tools": if(!n) o=d(o,[...t.allowedTools]); break;`.

`allowed-tools` **appends to `alwaysAllowRules`** — it is an additive **pre-approval /
auto-allow** layer. `disallowedTools` → `alwaysDenyRules` is the restriction lever. `skill-create.md`
is a plain command (no `context:`), so the permission-layer reading applies directly.

Therefore the dropped key made `/skill-create` **prompt** for Bash/Read/Write/Grep/Glob. It did
not let the command escape a 5-tool sandbox. And the rename **widens** auto-approval — including
`Bash` and `Write` on a command that writes files. That is almost certainly what the author
intended, but it must be described in the right direction.

**Correctly-scoped claim:** *`allowed_tools` (underscore) is not a supported key, so the intended
pre-approval layer was silently dropped and `/skill-create` prompted for each of its 5 tools
instead of having them auto-allowed. The rename restores the intended behaviour and, in doing so,
grants Bash/Write auto-approval to that command. It is not a tool-scope escape and not the
highest-impact of the dead keys.* Confidence: almost certain (90-99%) — the applier body is read
verbatim.

---

## Hard-rule audit — 11 of 11 checked, **0 violations**

| Rule | Verdict | Evidence |
|---|---|---|
| 1 authored vs deployed | **CLEAN** | `~/.agents/agents` does not exist; `~/.agents/commands` exists but holds only 5 grill + jailbreak files — **no** `reader`/`docs-lookup`/`security-reviewer`/`skill-create` copy. None under `~/source/agent-skills-toolchain` either (`find`, any depth). `sync-rules.ps1` scopes to `rules/common` only. So these are authored-in-place. Their claim holds; I also checked the `commands` path they did not. |
| 2 `~/.claude.json` | **no evidence of an edit** | mtime 23:15 is recent, but 4 live sessions write it continuously, so mtime cannot attribute. No lane artifact references it. UNVERIFIABLE by mtime; nothing points at this lane. |
| 3 no deletions/disables | **CLEAN** | 20 agents / 75 commands / 468 SKILL.md intact; `deniedMcpServers` still **6** (= briefed baseline); `git status --porcelain` in `~/.agents` shows **no** `D` entries; no branch touched. |
| 4 credentials | **CLEAN** | no credential read, print, or rotation anywhere in the lane's files or the script. |
| 5 no process kills | **CLEAN** | live fleet intact: **4** claude.exe, **199** node, **74** python. This workflow is still running. |
| 6 no commit | **CLEAN** | `scripts/lint-frontmatter-keys.py` is `??` **untracked**. Top commit `e04ffabc4` is the *sibling* context lane's (CLAUDE.md / rules / MEMORY.md) — I read its file list; it contains none of this lane's files. |
| 7 both-states proof | **SATISFIED** | independently reproduced by me (Tests 1-4 above), not taken on trust. |
| 8 Windows shell | **CLEAN** | no `New-Item -Force`, no MSYS path hazard, no truncation; files intact and parsing. |
| 9 write-as-you-go | **SATISFIED** | `native-features.md` exists, 20,092 B, and its content matches the report including the residual-UNVERIFIED section. |
| 10 net-negative | **SATISFIED** | each item names what it retires; the two "nothing retired" items say so explicitly. |
| 11 VERIFIED/INFERRED labels | **SATISFIED with the F1/F2/G corrections above** | bands are attached throughout; the `~10,471` token figure is correctly marked INFERRED arithmetic. |

## Regression hunt — **0 regressions**

- `settings.json` parses: **PASS**, 27,825 B, 35 top-level keys, `skillListingBudgetFraction
  0.04`, `ENABLE_TOOL_SEARCH "true"`. (Its 23:05 mtime and +616 B vs the briefed 27,209 B belong
  to the sibling context lane; this lane changed no settings.)
- `lint-rules-loading.ps1`: **PASS — exit 0**, 23/23 rules `cited=True deployed=True
  loadable=True`. Rules untouched, as claimed.
- The 3 edited config files all still parse as YAML frontmatter with the expected key sets. The
  provenance comment in `security-reviewer.md` does not leak into the key set.
- The gate's own estate run is **EXIT=1 with 10 ERRORs**, i.e. red-by-design on the inert keys
  they deliberately left for the owner. That is an honest red, not a regression.

## Net assessment

Strong lane. Five support questions answered from the product's own code rather than docs, the
loader question in (e) genuinely settled, one premise honestly refuted, two features declined for
stated reasons, and a gate that catches a real class of defect and fails closed on its own
instrument. The failures are all of one kind: **sentences wider than the measurements** — a
quote-scoped needle reported as byte-absence, two counts from superseded runs, an unexamined
severity direction, and one latent false negative. No code is wrong; four sentences are.

Highest-value single correction: **F2's direction.** "Tool-scope escape" and "grants Bash/Write
auto-approval" are opposite security stories about the same one-character edit.
