# Lane: native-features — Unused native Claude Code features

STATUS: COMPLETE (2026-09-25)
HOST: OFFLOAD-W2025 (Windows Server 2025), profile C:/Users/prekzursil
INSTALLED VERSION: **claude-code 2.1.283**

## Correction to the briefed ground truth (measured, not assumed)

The task stated the CLI is at `C:/Users/prekzursil/.local/bin/claude.exe`. **That is FALSE.**

```
$ Test-Path C:/Users/prekzursil/.local/bin/claude.exe      -> False
$ (Get-Command claude).Source
C:\Users\prekzursil\AppData\Roaming\npm\claude.ps1
```

The real binary is the npm install, a 244,960,928-byte Bun-compiled single file:

```
C:\Users\prekzursil\AppData\Roaming\npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe
package.json version = 2.1.283
```

There is no `cli.js` to read — the vocabulary must be scanned out of the `.exe`
(consistent with the prior `reference_hook_output_schema_binary_2026-09-25` finding).

---

## Step 0 — Feature support matrix (the gate)

Method: scan the installed binary for the frontmatter key vocabulary and the zod
schemas with their `.describe()` text. Confidence **high (90-99%)** on every row —
these are the product's own schema literals, not documentation.

| # | Feature | Verdict | Evidence |
|---|---------|---------|----------|
| a | `omitClaudeMd` on subagents | **SUPPORTED** | agent zod schema + first-party in-binary precedent |
| b | Subagent `maxTurns` | **SUPPORTED** | agent zod schema, `E().int().positive().optional()` |
| c | Per-agent `mcpServers:` | **SUPPORTED key / PREMISE REFUTED** | in vocabulary, but goal already met by `tools:` |
| d | Skill `effort:` / `context: fork` | **SUPPORTED** | skill zod schema; not applied (see below) |
| e | Skill `paths:` glob scoping | **SUPPORTED — and it gates the LISTING** | conditional-skill partition code |

### The authoritative key vocabulary (extracted, offset 0xc2a202d)

```js
v=["name","description","model","allowed-tools","argument-hint","arguments",
   "disable-model-invocation","user-invocable","effort","shell","version","when_to_use",
   "paths","hooks","context","agent","created_by","improved_by","mcpServers","lspServers",
   "agents","outputStyles","themes","workflows","channels","monitors","settings",
   "experimental","commands","skills","dependencies","userConfig","metadata","displayName",
   "defaultEnabled","fallback","evals","author","homepage","repository","license",
   "keywords","compatibility","tools","disallowedTools","color","permissionMode","maxTurns",
   "initialPrompt","memory","background","omitClaudeMd","isolation","observer",
   "observerMessage","observeSubagents","keep-coding-instructions","force-for-plugin",
   "type","originSessionId","hide-from-slash-command-tool"]   // 61 keys
```

Agent-config projection list (offset 0xc27263c), 17 keys:

```js
sp=["name","description","prompt","tools","disallowedTools","model","effort",
    "permissionMode","mcpServers","hooks","maxTurns","skills","initialPrompt","memory",
    "background","omitClaudeMd","isolation"]
```

### Verbatim schema text (offset 0xc10e57d) — the precedent Rule "show a precedent" demands

```
maxTurns: E().int().positive().optional().describe(
  "Maximum number of agentic turns (API round-trips) before stopping")

omitClaudeMd: M().optional().describe(
  "Run this agent without the user, project and local CLAUDE.md instruction files when it
   runs as a subagent; managed policy files are kept. For agents that take everything they
   need from the delegation prompt. No effect on the main session agent.")

effort: $e([z(["low","medium","high","xhigh","max"]),E().int()]).optional()
mcpServers: C(Y0()).optional()        // Y0 = union(string, record(string, McpServerConfig))
disallowedTools: "...MCP server-level specs (mcp__server, mcp__server__*, mcp__*) remove
                  every tool from the named server (or all MCP tools)."
```

Skill schema (offset 0xc694d40):

```
paths:   yE().optional().describe("Glob patterns this skill applies to. The skill only
                                   loads when the model touches matching files.")
context: z(["inline","fork"]).nullable().optional().describe("Where the skill runs:
          `inline` expands into the current conversation; `fork` spawns a subagent.")
agent:   Yc().optional().describe("Agent type to spawn when `context: fork`.")
effort:  Yc().optional().describe("Thinking effort for the model: low/medium/high/max, or an integer")
```

**Second, independent precedent for `omitClaudeMd`** (not just the schema): Anthropic's own
`claude-test` plugin ships it on two bundled agents, embedded in the binary at offsets
0x66dd965 and 0x66decec — e.g. `name: runner` … `omitClaudeMd: true`, `model: inherit`,
`tools: Read, Edit, Write, Bash, ToolSearch, …`. Note this first-party usage puts it on a
**write-capable** agent; I still chose not to (see (a) below) for an estate-specific reason.

---

## The defect found first: unsupported frontmatter live in a shipped agent

`~/.claude/agents/security-reviewer.md` carried, at lines 8-9:

```yaml
fallbacks: [claude-opus-4-8]
server-side-fallback: true
```

**Neither key exists in the product.** VERIFIED:

```
NEEDLE '"server-side-fallback"'  COUNT=0
NEEDLE 'serverSideFallback'      COUNT=0
NEEDLE '"fallbacks"'             COUNT=1   <- unrelated: a Bun HTTP request-body builder
                                              ("system":[ "model":" "fallbacks":[ ), not
                                              frontmatter parsing
```

So the intended server-side fallback to opus-4-8 **was never in force** — silently dropped,
no error, author believes it is configured. This is the exact defect class the verification
lens flagged. Confidence **almost certain (90-99%)**.

There is **no supported per-agent equivalent**; model fallback is server-side only. The keys
are removed and the intent recorded as a YAML comment in place (comments are safe: the
product's own frontmatter normalizer regexes `^([a-zA-Z_-]+):\s+(.+)$` per line and passes
non-matching lines through untouched — and the post-edit parse confirms 6 keys, no comment
leakage).

---

## Step 3 — What was implemented

### (a) `omitClaudeMd: true` on cheap read-only leaves — DONE

Measured corpus injected into every subagent today:

```
    9406  C:\Users\prekzursil\CLAUDE.md
    9384  C:\Users\prekzursil\.claude\CLAUDE.md
   21962  C:\Users\prekzursil\.claude\AGENTS-RUNTIME.md
    1132  C:\Users\Prekzursil\AGENTS.md
--------
TOTAL 41,884 bytes  ~= 10,471 tokens
```

(`~/.claude/AGENTS.md` does not exist — the `@AGENTS.md` import resolves to `AGENTS-RUNTIME.md`
plus the home `AGENTS.md`. Also note a sibling lane grew `~/.claude/CLAUDE.md` mid-run by
adding the `# Compact instructions` block, so this figure is a point-in-time floor and the
corpus is **growing** — which strengthens the case.)

Applied to the two agents that **cannot mutate anything**:

| Agent | tools | Added |
|---|---|---|
| `reader` | Read, Grep, Glob | `omitClaudeMd: true`, `maxTurns: 30` |
| `docs-lookup` | Read, Grep, 2x context7 MCP | `omitClaudeMd: true`, `maxTurns: 20` |

Both already restate in their own body everything the corpus would have given them that
matters to them: `reader` mandates evidence discipline, scope discipline, UNVERIFIED tagging
and `SUCCESS:`/`FAILED:` terminal states; `docs-lookup` carries its own prompt-injection
clause for untrusted fetched docs. This is precisely the schema's stated use case ("agents
that take everything they need from the delegation prompt").

**Saving: ~10,471 tokens per spawn of either agent**, INFERRED from the byte count (high
confidence on the arithmetic; I did not instrument a live spawn to count the delta — that is
the residual, and the settling experiment is a `/context`-style read inside a spawned reader).

**Deliberately NOT applied** to `writer`, `loop-operator`, `intent-drift-sentinel`,
`security-reviewer` and the other 16. Reason: each holds `Edit`/`Write`/`Bash`, so stripping
the corpus removes the §9 security non-negotiables (no credential rotation, no force-push,
no `--no-verify`) from a mutation-capable context. AGENTS-RUNTIME §10 says a lower layer may
be stricter but never laxer than a §9 non-negotiable, so that trade is not mine to make
silently. To extend the win there, restate the §9 floor in each agent body FIRST, then set
the flag — a clean follow-up, not a blocker.

### (b) `maxTurns` — DONE (on the same two leaves)

Bounds a runaway leaf. 30 / 20 are generous for Read/Grep/Glob-only and MCP-doc lookup
respectively; they are a **policy choice, freely tunable**. Residual UNVERIFIED: whether
hitting the cap returns partial output or an error — the schema says only "before stopping".
Low risk at these values; I did not burn a live spawn to find out.

### (c) Per-agent `mcpServers:` scoping — PREMISE REFUTED, no change made

Three findings, in order of importance:

1. **The goal is already achieved.** All **20/20** live agents already carry a `tools:`
   allowlist, and the schema says "Array of allowed tool names. **If omitted, inherits all
   tools from parent**." Since every agent enumerates its tools, no agent is inheriting 80
   MCP servers' schemas. The lens's "no" was wrong about the outcome.
2. `ENABLE_TOOL_SEARCH="true"` defers MCP schemas globally anyway, so the residual prefix
   cost this item targets is largely already gone.
3. The documented removal lever is **`disallowedTools`**, not `mcpServers` — its own
   `.describe()` states that `mcp__*` "remove[s] every tool from the named server (or all
   MCP tools)".

`mcpServers` on an agent is `Array<string | Record<string, McpServerConfig>>` and carries
**no `.describe()`**. Whether a bare string entry *filters* to that server or *adds* a
definition is **UNPROVEN**. Per the lane's own hard rule ("a feature you cannot prove exists
must NOT be added to a live config"), I did not add it anywhere. Settling experiment: set
`mcpServers: ["context7"]` on a throwaway agent and count its MCP tools.

### (d) Skill `effort:` / `context: fork` — SUPPORTED, deliberately NOT applied

Both keys are in the skill schema (quoted above), and `effort` has strong precedent — 9 live
agents already use it (`build-error-resolver`, `code-reviewer`, `doc-updater`, `e2e-runner`,
`harness-optimizer`, `python-reviewer`, `refactor-cleaner`, `security-reviewer`,
`typescript-reviewer`).

Not applied because `context: fork` **changes execution semantics** — it stops expanding the
skill inline and spawns a subagent instead. Choosing which of 415 skills is "heavy enough"
needs per-skill judgement, and a wrong pick silently re-routes a working skill through a
subagent boundary. Mass-applying on a guess is the kind of change that looks like a win and
lands as a regression. Left as a per-skill decision with the schema now documented.

### (e) Skill `paths:` glob scoping — SUPPORTED, and it gates the LISTING (the big one)

This was the load-bearing open question in the lane: does `paths:` only gate *loading* the
body (no listing saving), or does it remove the skill from the listed set (real saving)?
**Resolved from the product's own code**, offset 0xc8d4b13:

```js
for (let He of Pe) {
  let ze = He.type === "prompt" && !!He.paths && He.paths.length > 0;
  ...
  if (ze && !je.activatedConditionalSkillNames.has(He.name)) Fe.push(He);
  else Le.push(He)
}
for (let He of Fe) je.conditionalSkills.set(He.name, He);
if (Fe.length > 0) t(`[skills] ${Fe.length} conditional skills stored (activated when matching files are touched)`);
return t(`Loaded ${Pe.length} unique skills (${Le.length} unconditional, ${Fe.length} conditional, ...)`), Le
```

The loader **returns `Le` only**. A skill with a non-empty `paths` goes to `Fe`, is stashed in
`conditionalSkills`, and is **absent from the returned set** until its name lands in
`activatedConditionalSkillNames`. So `paths:` does cut the listing — the lever against the
measured 136,778 B / ~34,194 tokens of local skill frontmatter is **real**. Confidence
**almost certain (90-99%)**.

**But I applied it to zero existing skills, on purpose.** The same code proves the cost: a
conditional skill is genuinely *not loaded*, so until a matching file is touched it cannot be
listed and (unproven, but implied) cannot be invoked by name. Retrofitting `paths:` onto
existing skills is therefore a **discoverability regression** — functionally a hide — which
Hard Rule 3 puts out of my reach unilaterally. Recommended instead: use `paths:` on
**newly authored** file-type-specific skills, and settle the name-invocation question
(does typing a conditional skill's name activate it?) before any retrofit.

---

## Step 4 — Both-states proof (Hard Rule 7)

New gate: `C:/Users/prekzursil/.agents/scripts/lint-frontmatter-keys.py`

It validates agent/skill/command frontmatter against the vocabulary **scanned live out of the
installed binary** — no hardcoded allowlist, anchored on an array literal rather than a byte
offset, so a version bump re-resolves instead of going stale. If the anchor stops matching it
exits 2 (fail closed on the instrument), never a green from a broken detector.

**Proof 1 — synthetic pair (`--selftest`):**

```
GOOD state (only supported keys): 0 error(s) -- PASS (expected 0)
BROKEN state (real defect keys):  2 error(s) -- PASS (fires)
   ERROR unknown frontmatter key 'fallbacks' ...
   ERROR unknown frontmatter key 'server-side-fallback' ...
SUCCESS:lint-frontmatter-keys-selftest both states proven (fires on broken, silent on good)
EXIT=0
```

**Proof 2 — the REAL estate, before vs after the fix** (this is the stronger proof: the broken
state was a genuine live defect, not one I planted):

```
BEFORE  $ python lint-frontmatter-keys.py ~/.claude/agents
  security-reviewer.md:8: ERROR unknown frontmatter key 'fallbacks' ...
  security-reviewer.md:9: ERROR unknown frontmatter key 'server-side-fallback' ...
  FAILED:lint-frontmatter-keys 2 unsupported key(s), 2 warning(s)
  EXIT=1

AFTER   $ python lint-frontmatter-keys.py ~/.claude/agents
  scanned: 20 file(s)
  harness-optimizer.md:8: WARN 'color' is parsed but not in the agent-config projection list
  loop-operator.md:6:     WARN 'color' is parsed but not in the agent-config projection list
  SUCCESS:lint-frontmatter-keys 0 unsupported keys, 2 warning(s)
  EXIT=0
```

The two-tier severity is deliberate: `color` is in the parser vocabulary but not the agent
projection list, and two working agents use it — so it WARNs and does not fail. A gate that
reddens on working config gets disabled; this one does not.

**Proof 3 — a second real defect, found by running the gate estate-wide** (`allowed_tools`
underscore vs `allowed-tools` hyphen in `~/.claude/commands/skill-create.md`):

```
BEFORE  skill-create.md:4: ERROR unknown frontmatter key 'allowed_tools' ...  EXIT=1
AFTER   SUCCESS:lint-frontmatter-keys 0 unsupported keys, 0 warning(s)        EXIT=0
```

### The gate's own first run was wrong — and that is recorded, not hidden

The first estate-wide run emitted a **wall of false positives** against
`skills/code-security/rules/*.md`, which are reference DATA files with their own domain schema
(`title` / `impact` / `impactDescription` / `tags`) sitting inside a skill directory. They are
not config and Claude Code never parses them as frontmatter. Two fixes landed:

1. **Scope to config entry points.** Inside `skills/`, only `SKILL.md` is linted; `agents/` and
   `commands/` files are entry points directly. An explicitly-named file is always honoured.
2. **An `ESTATE_METADATA` WARN tier** for keys this estate deliberately writes as its own
   provenance — currently `{"origin"}`, measured on **59 of 468** local `SKILL.md` files
   (`origin: ECC`). The product drops them, but nothing is lost: estate tooling reads them, not
   Claude Code. They WARN instead of failing, because a permanently-red gate is ignored just as
   surely as a never-red one — the same rot in the opposite direction.

Both changes narrow the gate's claim to what it can actually justify, which is the point.

### What the corrected gate found estate-wide: 11 real dead keys

`scanned: 2130 → SUCCESS on entry points`, **11 ERROR / 60 WARN**:

| File(s) | Dead key | Harm |
|---|---|---|
| `commands/skill-create.md` | `allowed_tools` (should be `allowed-tools`) | **REAL — FIXED.** The 5-tool allowlist was silently dropped, so the command inherited **all** tools instead of `Bash, Read, Write, Grep, Glob`. A scope escape, not cosmetics. |
| `commands/{evolve,instinct-export,instinct-import,instinct-status,projects,promote,skill-health}.md` | `command: true` | Inert. A no-op flag — a file's presence in `commands/` already makes it a command. Reported, not edited (8 files, zero behaviour recovered). |
| `skills/jailbreak/SKILL.md` | `tags`, `category` | Inert metadata. Reported, not edited. |
| `skills/estate-offensive-doctrine/SKILL.md` | `category` | Inert metadata. Reported, not edited. |

I fixed only the one with real behavioural impact and left the 10 inert ones for the owner —
mass-editing files to silence a gate is how a gate stops meaning anything.

Post-edit YAML parse check on all three edited files: **all OK**, `security-reviewer` back to
6 keys with the comment block correctly ignored.

---

## Net-negative ledger (Hard Rule 10)

| Added | Retires |
|---|---|
| `omitClaudeMd: true` x2 | Retires ~10,471 tokens of CLAUDE.md corpus per spawn of those agents. Net **negative** context. |
| `maxTurns` x2 | Retires the unbounded-turn failure mode on those leaves. No context cost (2 lines). |
| `lint-frontmatter-keys.py` (~270 lines, offline, not a hook) | Retires the *class* of silent-drop defect, and retires the need for a hand-maintained key list — nothing on this estate validated frontmatter against the product before. Costs **zero always-on context**: it is a manual/CI script, not a hook, and adds no per-turn tokens. |
| 5 comment lines in `security-reviewer.md` | Retires 2 dead keys + the false belief that a fallback was configured. Net −2 functional lines. |

**Nothing is added that I could not retire something for**, and the one genuine addition (the
lint) is deliberately kept out of the per-turn hook path so it cannot become the very
always-on bloat this sweep exists to cut.

---

## Files changed (all authored, none deployed-copy)

Checked first: `~/.agents/agents/` does not exist and `sync-rules.ps1` scopes only to
`rules/common`, so `~/.claude/agents/` **is** the authored location for agents — Hard Rule 1's
authored-vs-deployed split applies to rules, not agents. The only other `security-reviewer.md`
on the box is a test fixture under `platform/routing/fixtures/`.

| File | Change |
|---|---|
| `C:/Users/prekzursil/.agents/scripts/lint-frontmatter-keys.py` | NEW — the gate |
| `C:/Users/prekzursil/.claude/agents/reader.md` | +`omitClaudeMd: true`, +`maxTurns: 30` |
| `C:/Users/prekzursil/.claude/agents/docs-lookup.md` | +`omitClaudeMd: true`, +`maxTurns: 20` |
| `C:/Users/prekzursil/.claude/agents/security-reviewer.md` | −2 dead keys, +5 comment lines |
| `C:/Users/prekzursil/.claude/commands/skill-create.md` | `allowed_tools` → `allowed-tools` (restores the dropped 5-tool allowlist) |
| `C:/Users/prekzursil/.agents/knowledge/.../native-features.md` | this report |

Nothing committed (Hard Rule 6). No MCP server, plugin, skill or branch touched. No credential
read, written or rotated. No process killed. `~/.claude.json` untouched.

## Residual UNVERIFIED (inline, per fan-out contract)

1. The ~10,471-token saving is arithmetic from byte counts, **not** an instrumented live spawn.
   Settling experiment: spawn `reader` and read its actual context composition.
2. Whether `maxTurns` exhaustion returns partial output or an error — UNVERIFIED, low risk at 30/20.
3. Whether `mcpServers: ["name"]` filters or adds — UNVERIFIED, which is why it was not used.
4. Whether a `paths:`-conditional skill can still be invoked by name before activation —
   UNVERIFIED, and it is the blocker on any `paths:` retrofit.
