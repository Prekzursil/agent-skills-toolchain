export const meta = {
  name: 'mcp-tui-audit',
  description: 'Estate-wide MCP/TUI/skills/rules audit — 35 read-only lanes + verify + synthesis, 5-wide concurrency, resumable',
  phases: [{ title: 'Ground' }, { title: 'Lanes' }, { title: 'Verify' }, { title: 'Reprobe' }, { title: 'Synthesize' }],
}

// ---- constants ------------------------------------------------------------
const RUN = 'C:/Users/Prekzursil/source/agent-skills-toolchain/harness-audits/2026-09-19-mcp-tui-audit'
const MANIFEST_CLI = 'C:/Users/Prekzursil/.claude/harness-meta/plan_lint_stage0.py'
const MANIFEST = RUN + '/resume-manifest.jsonl'
const CHUNK = 10         // USER-MANDATED concurrency (5 at 06:16, raised to 10 by owner at 06:44; runtime ceiling is 14)
const LANE_TIMEOUT_MS = 900000  // 15 min per lane; a hung lane drops to a receipt, never stalls the chunk

// ---- schemas (required = FLOOR only; rule 7) ------------------------------
const obj = (properties, required = []) => ({
  type: 'object', additionalProperties: false, required, properties,
})
const LANE_SCHEMA = obj(
  {
    lane: { type: 'string' },
    digest: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
    delivered: { type: 'string' },
    warnings: { type: 'array', items: { type: 'string' } },
    needs_reprobe: { type: 'array', items: { type: 'string' } },
  },
  ['lane', 'digest', 'evidence', 'delivered'],
)
const GROUND_SCHEMA = obj(
  {
    pending: { type: 'array', items: { type: 'string' } },
    existing: { type: 'array', items: { type: 'string' } },
    manifest_used: { type: 'boolean' },
    notes: { type: 'string' },
    warnings: { type: 'array', items: { type: 'string' } },
  },
  ['pending', 'existing', 'manifest_used'],
)
const SYNTH_SCHEMA = obj(
  {
    digest: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
    delivered: { type: 'string' },
    warnings: { type: 'array', items: { type: 'string' } },
  },
  ['digest', 'evidence', 'delivered'],
)

// ---- H6 timeout helper (paste-in; setTimeout IS injected) ------------------
function withTimeout(thunk, ms, label) {
  return new Promise((resolve) => {
    let done = false
    const timer = setTimeout(() => {
      if (!done) { done = true; resolve({ __h6: true, __endReason: 'timeout', label, ms }) }
    }, ms)
    thunk()
      .then((v) => { if (!done) { done = true; clearTimeout(timer); resolve(v ?? { __h6: true, __endReason: 'null', label }) } })
      .catch(() => { if (!done) { done = true; clearTimeout(timer); resolve({ __h6: true, __endReason: 'threw', label }) } })
  })
}

// ---- lane table (id, wave, targets, notes) --------------------------------
const LANES = [
  // Wave A: 80 registry servers, 4 per lane
  { id: 'A01', wave: 'waveA', targets: 'agent-mail, angr, annas-archive, apify', notes: 'angr: static-check exe only (NEVER spawn RE harness).' },
  { id: 'A02', wave: 'waveA', targets: 'arxiv, basic-memory, bedrock-claude, binary-ninja-mcp', notes: 'bedrock-claude FAILED this session (CONNECTION_CLOSED) — diagnose why. basic-memory: curl http://127.0.0.1:18765 health. binary-ninja: static npm check only.' },
  { id: 'A03', wave: 'waveA', targets: 'biomni-hub, browserstack, burp, cheatengine', notes: 'burp OFF (java -jar) — if jar missing, decommission-candidate. cheatengine static only.' },
  { id: 'A04', wave: 'waveA', targets: 'chrome-devtools, claude-code-mcp, cloud-audit, cloud-audit-hub', notes: 'cloud-audit FAILED (ConnectionRefused) — is its backend lazy-by-design or a wiring defect?' },
  { id: 'A05', wave: 'waveA', targets: 'codacy, codecov, context7, crossref', notes: 'crossref: check CROSSREF_MAILTO env presence (name only).' },
  { id: 'A06', wave: 'waveA', targets: 'cursor-bridge, cve-mcp, cve-mcp-hub, dbx-ai', notes: 'A short-name "cve" variant failed this session — record name mismatch. cursor-bridge :18317 on-demand; note auth2api retire rule G-23/G-34.' },
  { id: 'A07', wave: 'waveA', targets: 'deepscan, deepsource, deepwiki, digitalocean', notes: 'digitalocean = archived MCP — assess decommission. Verify node script paths exist.' },
  { id: 'A08', wave: 'waveA', targets: 'docker, exa, excel, firecrawl', notes: 'firecrawl FAILED (local backend down) + firecrawl-kit variant in ~/.mcp.json = scatter. Is the backend on-demand by design?' },
  { id: 'A09', wave: 'waveA', targets: 'frida-mcp, ghidra-mcp, github, github-security', notes: 'github-security FAILED (local backend down); -hub variant hermes-only. RE harnesses: static only.' },
  { id: 'A10', wave: 'waveA', targets: 'github-security-hub, github_cli, glm53-space, hexstrike-ai', notes: 'glm53-space OFF + qwen-space-tool-api skill DEPRECATED — decommission assessment. github_cli: verify gh-cli-mcp binary.' },
  { id: 'A11', wave: 'waveA', targets: 'hexstrike-ai-hub, huggingface, ida-pro-mcp, kaggle', notes: 'ida-pro-mcp: static check plugin install only. kaggle OFF — assess.' },
  { id: 'A12', wave: 'waveA', targets: 'libgen, linear, linkedin, markitdown', notes: 'linkedin: env vars MISSING (agents doctor) — UNRESOLVED-env, never fabricate creds. libgen OFF placeholder by design (2026-09-21 receipt). markitdown OFF + claude-denied.' },
  { id: 'A13', wave: 'waveA', targets: 'mcp-graphql, meta-tool, mitmproxy, notion', notes: 'meta-tool OFF + claude-denied. mitmproxy static only.' },
  { id: 'A14', wave: 'waveA', targets: 'nuclei, nuclei-hub, openaiDeveloperDocs, openalex', notes: 'nuclei FAILED (backend down) — lazy vs defect. openalex vs openalex-alt name collision.' },
  { id: 'A15', wave: 'waveA', targets: 'openalex-alt, osint, osint-hub, paper-search', notes: 'openalex-alt FAILED (CONNECTION_CLOSED). paper-search exe = D:/ReverseTools/mcp/paper-search-mcp — disk-verify now, classify local-impl-move.' },
  { id: 'A16', wave: 'waveA', targets: 'pdf-reader, playwright, postgres, pubmed', notes: 'playwright ×10 + -cdp ×10 + -extension ×10 process pile-up (ceiling 3) — remediation note, kill NOTHING.' },
  { id: 'A17', wave: 'waveA', targets: 'pubmed-tool, qlty, ralph-orchestrator, repomix', notes: 'pubmed-tool FAILED (CONNECTION_CLOSED; launch-validated 2026-09-21) — uv cache eviction? pubmed vs pubmed-tool which survives.' },
  { id: 'A18', wave: 'waveA', targets: 'scholarly-access, sci-hub, scrapegraph, semgrep', notes: 'scholarly-access = THE repo-housed reference pattern (tools/scholarly-access-mcp) — verify exe resolves to repo, cite as model case. semgrep vs semgrep-hub scatter.' },
  { id: 'A19', wave: 'waveA', targets: 'semgrep-hub, sentry, sonarqube, tavily', notes: 'sentry: SENTRY_AUTH_TOKEN presence only. sonarqube docker static only. tavily: plugin-provided variant dedup question.' },
  { id: 'A20', wave: 'waveA', targets: 'web-reader, web-search-prime, zai-vision, zread', notes: 'zai-vision FAILED (exe:cmd wrapper) — diagnose what it launches and whether target exists. These are the zai-lane servers; curl the http ones.' },
  // Wave B: TUI wiring
  { id: 'B1', wave: 'waveB', targets: 'goose (~/.config/goose/config.yaml + extensions)', notes: 'G-42: HTTP-ONLY extensions (:18765/:18812 hubs + builtin developer). NEVER propose goose mcp serve. Output compliant YAML snippet (do not write).' },
  { id: 'B2', wave: 'waveB', targets: 'agy (AppData/Local/agy + config discovery)', notes: 'G-72: HTTP hubs + vault pointers ONLY; a private agy mcp.json is a VIOLATION (report, never delete/create).' },
  { id: 'B3', wave: 'waveB', targets: 'gemini (~/.gemini/settings.json, 33 mcpServers)', notes: 'Cross-ref all 33 vs SSOT 80: in-ssot / not-in-ssot / name-variants. Health-sample ≤10 via curl/static.' },
  { id: 'B4', wave: 'waveB', targets: 'opencode, aider, grok-agent (~/.grok)', notes: 'Discover each MCP+skills surface. grok: agents=user-settings.agentLibrary.agents, skills=POST /rest/user-skills (estate memory).' },
  { id: 'B5', wave: 'waveB', targets: 'zcode lane (D:/npm-cache/_npx/2f024689b4d0d3b0 @z_ai coding-helper) + hermes (AppData/Local/hermes)', notes: 'Which zcode/hermes-targeted SSOT servers are actually wired vs dropped? Check installed agents CLI package (AppData/Roaming/npm/node_modules/@agents-dev) for the supported-targets enum + whether 0.9.1 adds zcode/hermes.' },
  { id: 'B6', wave: 'waveB', targets: 'core-3 reconcile: claude (86 in ~/.claude.json) vs codex (16 TOML) vs cursor (7) vs SSOT (80)', notes: 'Three-way diff + enabled-drift (registry enabled:false vs claude deniedMcpServers) + READ sync_shared_state.ps1 (.agents/scripts) and summarize what extending it to gemini/opencode/zcode/hermes requires.' },
  { id: 'B7', wave: 'waveB', targets: 'cyberstrike (~/.config/cyberstrike) + fabric (~/.config/fabric)', notes: 'cyberstrike: provider/MCP surface + which session-failing security MCPs (sliver, metasploit, nuclei, cve, hacktricks) it actually needs, prioritized. fabric: no MCP client expected — confirm + note distillery file existence.' },
  // Wave C: skills / rules / paths
  { id: 'C1', wave: 'waveC', targets: 'skills drift: .agents/skills vs ~/.claude/skills vs ~/.codex/skills vs repo skills/ + skills-claude-only/', notes: 'Name-level diff, classify each delta: sync-artifact | drift | stale-dupe | claude-only-by-design.' },
  { id: 'C2', wave: 'waveC', targets: 'unreposed skills: disk-space-manager, estate-offensive-doctrine, fabric-patterns, hosted-model-agents, jailbreak, qwen-space-tool-api (+ discover the rest)', notes: 'git-hygiene flagged 8 live skills absent from every repo tree — locate each canonical copy, recommend repo placement path in agent-skills-toolchain.' },
  { id: 'C3', wave: 'waveC', targets: 'rules tree: ~/.claude/rules vs repo rules/ + guides/', notes: 'Broken relative references, missing files, drift. The ~/.claude/AGENTS.md G-96 pointer chain must resolve.' },
  { id: 'C4', wave: 'waveC', targets: 'registry path canonicality: all 80 servers in ~/.agents/agents.json', notes: 'Python-scan every command/args/url path: absolute? env-stable? 8.3 short-names (PREKZU~1)? C:/D: drive duplication? Quote each offending string verbatim.' },
  { id: 'C5', wave: 'waveC', targets: '~/.mcp.json vs SSOT: 19 undocumented-active servers', notes: 'metasploit, sliver, sliver-full, hacktricks, search-hub, cloud-hub, fiddler, firecrawl-kit, brightdata, tooluniverse, playwright-cdp, playwright-extension, cve, github-security, osint, nuclei, semgrep, angr, agent-mail, apify, cursor-bridge — classify each: SSOT-name-variant | deliberate-fleet-home | rogue.' },
  { id: 'C6', wave: 'waveC', targets: 'script scatter: ~/.local/opt/* vs repo scripts/', notes: 're-harness, monitorcore, mingle, mcp_doctor — inventory each, classify housed-repo vs local-only, recommend placement.' },
  { id: 'C7', wave: 'waveC', targets: 'memory-map + memory-contract vs reality', notes: 'C:/Users/Prekzursil/.agents/memory-map.md + memory-contract.md: every path/port in them exists? (:18765 basic-memory, :18812 agent-mail, :18317 auth2api).' },
  { id: 'C8', wave: 'waveC', targets: 'toolchain repo layout vs live ~/.agents layout', notes: 'Repo platform/ layout vs harness-at-root live layout (estate rule: never check out platform layout into live folder). Map what syncs where; find orphaned either-side artifacts.' },
]

const ALL_IDS = LANES.map((l) => l.id)

// ---- shared prompt prefix (byte-stable across ALL lanes; rule 8) ----------
const CONTEXT = [
  'You are one lane of the 2026-09-19 estate-wide MCP/TUI/skills audit. Owner-directed. READ-ONLY mandate: no config edits, no commits, no process kills, no writes anywhere EXCEPT your own verdict file and the resume manifest marks.',
  '',
  'VERIFIED GROUND TRUTH (established by direct inspection before this workflow; each tagged [probe]):',
  '  1. SSOT registry ~/.agents/agents.json holds 80 servers under mcp.servers; syncMode=source-only. [probe: python parse 2026-09-19 05:41, registry-inventory.json in the run dir]',
  '  2. Config surfaces and counts: ~/.claude.json 86 mcpServers, ~/.codex/config.toml 16, ~/.cursor/mcp.json 7, ~/.gemini/settings.json 33, ~/.mcp.json 19+ active-but-undocumented. [probe: python sweep 05:41, tui-inventory.json]',
  '  3. These FAILED to connect in the live Claude session: bedrock-claude, cloud-audit, cloud-hub, cve, fiddler, firecrawl, firecrawl-kit, github-security, hacktricks, metasploit, nuclei, openalex-alt, osint, pubmed-tool, search-hub, sliver, sliver-full, tooluniverse, zai-vision. Claude-targeted servers NOT listed connected fine. [probe: session-start MCP banner 05:16 + transcript]',
  '  4. Process pile-ups: playwright/-cdp/-extension ×10 each (ceiling 3), angr ×6, cloud-hub ×6. [probe: mcp_doctor.py audit 05:41]',
  '  5. agents CLI 0.8.10 silently DROPS registry targets zcode/hermes (30+ warnings). Update 0.9.1 held until post-audit. [probe: agents doctor 05:41]',
  'To confirm or refute any claim you MUST use a mechanically DIFFERENT probe than the one tagged. Report every reconciliation in your verdict.',
  '',
  'ACCESS METHODS: run dir = ' + RUN + ' (registry-inventory.json, tui-inventory.json, agents-doctor.txt already there — Read them). ~/.claude.json is HUGE: extract only your entries via python/jq, never dump the file.',
  '',
  'OUTPUT-SIZE DISCIPLINE (API-limit guard — a lane already died to this, 400 Invalid API parameter): NEVER print raw contents of large configs. Filter IN-CODE and print only the distilled entries for YOUR items, capped at 100 lines / 10KB per command output; if you need more, write the extraction to a temp file and Read a line range. NEVER load a whole big file into a shell variable to echo it. NEVER call ToolSearch or attach/use MCP tools — your toolset is Read/Grep/Glob/Bash(python/jq/curl)/Write ONLY. curl for HTTP servers is fine; MCP clients are not.',
  '',
  'SPAWN POLICY (box has ~5GB free RAM; be gentle): static checks first (path exists? package dir? config parses?). Spawn at most ONE server at a time, kill within 15s, only cheap stdio python/node. NEVER spawn: docker-based, schrodinger, hexstrike-ai, mitmproxy, playwright, frida-mcp, ida-pro-mcp, ghidra-mcp, angr, binary-ninja-mcp, cheatengine, nuclei — static-check those. HTTP: curl -m 5. NEVER print credential values — names/presence only.',
  '',
  'HONESTY CONTRACT (applies here or not at all):',
  '- Tag UNVERIFIED INLINE on the sentence it qualifies; every UNVERIFIED names the settling experiment.',
  '- "Absent/not found/broken" is a claim, not an observation — validate your detector finds a known-present item before reporting any absence.',
  '- Do not report CONFIRMED via the same mechanism being checked. If a tool is denied, do not stop — record the gap, use an alternative, report it.',
  '',
  'OUTPUT CONTRACT:',
  '  1. FIRST run: python "' + MANIFEST_CLI + '" --manifest "' + MANIFEST + '" --mark-partial <YOUR-LANE-ID>',
  '  2. Write your FULL verdict with the Write tool to the exact path given in YOUR TASK below. JSON object/array as specified there. If a single call is too large, chunk with Add-Content (Windows 32,767-char limit — never build multi-KB literals inside a shell string).',
  '  3. THEN run: python "' + MANIFEST_CLI + '" --mark-done <YOUR-LANE-ID>',
  '  4. Return a <=300-word digest: lead with ground-truth corrections, then findings. Append EVIDENCE: 3-5 file:line / path / command anchors (exempt from the cap). Final line: DELIVERED: <abs path>.',
  '',
  '=== YOUR TASK ===',
].join('\n')

function lanePrompt(l) {
  const verdictPath = RUN + '/' + l.wave + '/' + l.id + '.json'
  let task
  if (l.wave === 'waveA') {
    task = 'Lane ' + l.id + ' — MCP health/disposition for EXACTLY these registry servers: ' + l.targets + '. ' + (l.notes || '') +
      '\nVerdict file = JSON array, one object per server: {name, health, disposition, why, paths, scatter}. health: LIVE-SESSION | SPAWN-OK | STATIC-OK | UNRESOLVED | UNREACHABLE | OFF-BY-DESIGN. disposition: registry-pinned | vendor-source | local-impl-move | decommission-candidate. paths: canonical or AMBIGUOUS + the offending string verbatim. scatter: which surfaces it appears in + name variants.'
  } else if (l.wave === 'waveB') {
    task = 'Lane ' + l.id + ' — TUI wiring audit for: ' + l.targets + '. ' + (l.notes || '') +
      '\nVerdict file = JSON object: {surface, current_state, violations, health_sample?, gap_list, max_legal_plan, notes}. REPORT plans and snippets — never write config.'
  } else {
    task = 'Lane ' + l.id + ' — estate hygiene audit for: ' + l.targets + '. ' + (l.notes || '') +
      '\nVerdict file = JSON object: {scope, findings: [{item, classification, evidence, recommendation}], summary}.'
  }
  return CONTEXT + task + '\nVerdict path: ' + verdictPath + '\nLane id for manifest marks: ' + l.id + '\nBe concrete about measured state on THIS box, not generic advice.'
}

const groundPrompt = [
  'You are the GROUND stage of the mcp-tui-audit workflow. Two jobs, read-only:',
  '1. Resume manifest: run `python "' + MANIFEST_CLI + '" --manifest "' + MANIFEST + '" --ids ' + ALL_IDS.join(',') + ' --next`. If the CLI or manifest file errors, manifest_used=false and derive pending WITHOUT it. If the manifest does not exist yet, this command creates it — that is expected on first run.',
  '2. Belt-and-braces: list existing verdict files (waveA/*.json, waveB/*.json, waveC/*.json) under ' + RUN + ' and return their basenames in existing[].',
  'Return: pending = lane ids still to run (manifest --next output, intersected with ids whose verdict file is ABSENT; if manifest unusable, pending = all ids with no verdict file). existing = verdict filenames present. manifest_used = whether the CLI call succeeded. notes = one line.',
  'Lane id universe: ' + ALL_IDS.join(', '),
].join('\n')

// ---- workflow body --------------------------------------------------------
phase('Ground')
// DEADLOCK GUARD: EVERY agent() in this workflow is withTimeout-bounded, including the
// singletons — a hung ground/synthesis degrades to a typed receipt instead of stalling
// the run forever. ground=300s (it is a 2-minute task); synthesis=900s (reads ~40 files).
const ground = await withTimeout(() => agent(groundPrompt, { label: 'ground', phase: 'Ground', schema: GROUND_SCHEMA, effort: 'max' }), 300000, 'ground')
const existing = new Set((ground?.existing || []).map((f) => String(f).split('/').pop().split('\\').pop().replace(/\.json$/, '')))
const manifestPending = new Set(ground?.pending || ALL_IDS)
// DETERMINISTIC RESUME (owner-directed 2026-09-19): when args.pending is provided it is the
// EXACT lane list to run, computed by the orchestrator from on-disk verdict files. Ground's
// runtime listing can fail (manifest file locked by marking agents; listing timeouts) and its
// null-fallback then re-runs completed lanes — args.pending overrides that permanently.
const a = (typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch { return {} } })() : args) ?? {}
const argPending = Array.isArray(a.pending) && a.pending.length > 0 ? new Set(a.pending) : null
const pending = argPending
  ? LANES.filter((l) => argPending.has(l.id))
  : LANES.filter((l) => manifestPending.has(l.id) && !existing.has(l.id))
if (argPending) log('DETERMINISTIC resume: running exactly ' + pending.length + ' lanes from args.pending')
log('ground: manifest_used=' + (ground?.manifest_used) + ' existing=' + existing.size + ' pending=' + pending.length + '/' + LANES.length)

phase('Lanes')
// ROLLING 5-slot worker pool (owner-directed 2026-09-19): a finished lane's slot immediately
// takes the next pending lane — no batch barrier, no 4-slots-idle tail waiting for the slowest
// lane of a chunk. Each agent is still individually bounded by withTimeout; workers exit when
// the queue drains, so the phase barrier only waits for the final in-flight lane.
const receipts = []
const queue = pending.slice()
const slotCount = Math.min(CHUNK, queue.length)
const doneCount = { n: 0 }
async function laneWorker() {
  while (queue.length > 0) {
    const l = queue.shift()
    const r = await withTimeout(() => agent(lanePrompt(l), { label: l.id, phase: 'Lanes', schema: LANE_SCHEMA, effort: 'max' }), LANE_TIMEOUT_MS, l.id)
    receipts.push(r ?? { __h6: true, __endReason: 'null', label: l.id })
    doneCount.n += 1
    log('lane done: ' + l.id + ' ' + doneCount.n + '/' + pending.length + (r && r.__h6 ? ' (dropped:' + r.__endReason + ')' : ''))
  }
}
await parallel(Array.from({ length: slotCount }, () => () => laneWorker()))

phase('Verify')
// Deterministic sample (no Math.random allowed): every lane whose receipt dropped, plus a fixed
// re-verify spread. Verifiers read the verdict files themselves (auto-discovery).
const droppedIds = receipts.filter((r) => r && r.__h6).map((r) => r.label)
const verifyTasks = [
  { id: 'V1', note: 'Re-verify with MECHANICALLY DIFFERENT probes every waveA verdict whose health is UNRESOLVED/UNREACHABLE or disposition is decommission-candidate/vendor-source (read ' + RUN + '/waveA/*.json, pick those rows, re-check each with a different instrument than the lane used — e.g. PowerShell Test-Path vs bash ls, curl vs python urllib).' },
  { id: 'V2', note: 'Adversarially re-check the 6 registry servers with the highest blast-radius dispositions in waveA verdicts (local-impl-move and decommission-candidate rows): is the recommended move SAFE (no lost config, no broken symlink consumers)? Name every consumer of each moved path.' },
  { id: 'V3', note: 'Cross-lane contradiction hunt: read ALL waveB/*.json verdicts; flag any pair that proposes conflicting wiring for the same server/TUI (e.g. B6 sync-extension plan vs B3 gemini plan vs B1 goose plan) and adjudicate with evidence.' },
  { id: 'V4', note: 'Cross-lane contradiction hunt: read ALL waveC/*.json verdicts; flag overlaps/conflicts (C1 skills drift vs C2 unreposed vs C8 layout) and adjudicate.' },
  { id: 'V5', note: 'Path-canonicality spot-check: take 10 AMBIGUOUS path strings quoted across waveA+C4 verdicts and independently re-derive each with PowerShell (Resolve-Path) — do they resolve? Quote before/after.' },
]
const verifyReceiptsRaw = await parallel(verifyTasks.map((v) => () =>
  withTimeout(() => agent(CONTEXT + 'Lane ' + v.id + ' — adversarial verification. ' + v.note +
    (droppedIds.length ? '\nALSO: these lanes dropped with receipts (' + droppedIds.join(',') + ') — note them as gaps in your verdict.' : '') +
    '\nVerdict file = JSON object {verifications: [{claim, verdict: CONFIRMED|REFUTED|UNVERIFIED, settling_probe, evidence}], contradictions: [...], gaps: [...]} to ' + RUN + '/waveD/' + v.id + '.json — create waveD. Lane id: ' + v.id,
    { label: v.id, phase: 'Verify', schema: LANE_SCHEMA, effort: 'max' }), LANE_TIMEOUT_MS, v.id)))
const verifyReceipts = verifyReceiptsRaw.map((r, j) => r ?? { __h6: true, __endReason: 'null', label: verifyTasks[j].id })

phase('Reprobe')
// Bounded verify->fix->re-verify loop (max ONE round, max 5 units): critics return needs_reprobe
// claims they could not settle; a third, mechanically different instrument closes each. Never unbounded.
const reprobeItems = verifyReceipts
  .filter((r) => r && !r.__h6)
  .flatMap((r) => (r.needs_reprobe || []).map((q) => ({ src: r.lane, q })))
  .slice(0, 5)
const reprobeReceipts = reprobeItems.length
  ? (await parallel(reprobeItems.map((it, idx) => () => {
      const rid = 'R' + (idx + 1)
      return withTimeout(() => agent(CONTEXT + 'Re-probe unit ' + rid + ' (from verifier ' + it.src + '). CLAIM TO SETTLE: ' + it.q + ' — settle it with an instrument DIFFERENT from both the original lane and the verifier (third mechanism). Verdict file = JSON {claim, verdict: CONFIRMED|REFUTED|UNVERIFIED, settling_probe, evidence} written to ' + RUN + '/waveD/' + rid + '.json. Manifest marks: try lane id ' + rid + ' — if the CLI rejects an R-id (not in the manifest universe), record it as a warning and CONTINUE; the verdict file is the source of truth.', { label: rid, phase: 'Reprobe', schema: LANE_SCHEMA, effort: 'max' }), LANE_TIMEOUT_MS, rid)
    }))).map((r, j) => r ?? { __h6: true, __endReason: 'null', label: 'R' + (j + 1) })
  : []
log('reprobe: ' + reprobeItems.length + ' claims, ' + reprobeReceipts.filter((r) => r && !r.__h6).length + ' settled')

phase('Synthesize')
const synthPrompt = CONTEXT + 'You are the SYNTHESIS stage. Read EVERY verdict file under ' + RUN + '/waveA, waveB, waveC, waveD (JSON; parse with python if large). Produce the audit master report and Write it to ' + RUN + '/AUDIT-SUMMARY.md with sections: 1) Health scoreboard (80 servers, health + disposition table). 2) Scatter map (surface-by-surface, name variants, the 19 undocumented ~/.mcp.json actives). 3) Consolidation plan (per-server disposition → toolchain tools/ placement, ordered, with the scholarly-access pattern as reference). 4) Cross-TUI wiring plan (all 12 CLIs + zcode/hermes lanes, max-legal per tool, sync-script extension outline). 5) Skills/rules hygiene (C1-C8 folded in). 6) Adversarial-verification results (V1-V5: refuted/confirmed/unverified counts + contradictions resolved). 7) Owner decision list (everything needing your approval, with recommendation each). End with DELIVERED line. Also write ' + RUN + '/scoreboard.json {servers: [{name, health, disposition}], tuis: [{name, wired, plan_ready}], open_decisions: [...]}. Final digest <=300 words + EVIDENCE block.'
const synth = await withTimeout(() => agent(synthPrompt, { label: 'synthesis', phase: 'Synthesize', schema: SYNTH_SCHEMA, effort: 'max' }), 900000, 'synthesis')

const allReceipts = [...receipts, ...verifyReceipts, ...reprobeReceipts]
const ok = allReceipts.filter((r) => r && !r.__h6).length
const dropped = allReceipts.filter((r) => r && r.__h6).length
return {
  envelope: true,
  ok,
  dropped,
  total: allReceipts.length,
  pending_before_run: pending.length,
  synthesis_delivered: synth?.delivered ?? null,
  dropped_labels: allReceipts.filter((r) => r && r.__h6).map((r) => r.label + ':' + r.__endReason),
}
