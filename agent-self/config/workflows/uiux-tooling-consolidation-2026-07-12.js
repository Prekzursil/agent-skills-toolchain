export const meta = {
  name: 'uiux-tooling-consolidation-2026-07-12',
  description: 'Focused UI/UX-tooling deep-dive: consolidate our design skills+MCPs, find SOTA audit/design solutions, design the interactive-modify + app-driver + always-mirror-to-Figma capabilities -> decision-queue for the grill',
  phases: [
    { title: 'Ground', detail: 'inventory our UI/UX skills + Figma MCP + design hooks; map overlaps' },
    { title: 'Fan-out', detail: '~14 Fable lenses: consolidate, SOTA audit, design<->code, Figma-automation, app-driver, figma-mirror, new skills, cross-model, a11y/visual-reg, plug-and-play, architecture' },
    { title: 'Synthesize', detail: 'the CONSOLIDATION architecture + new-capability designs + verify -> decision-queue doc' },
  ],
}

// ---------------------------------------------------------------------------
// H6 — per-agent timeout + stall heartbeat. Paste at the top of the workflow.
// Sandbox-safe: uses only injected globals (setTimeout/clearTimeout/log/parallel).
// No Date.now / Math.random / new Date() -> stays workflow_lint clean.
// SCOPE: unblocks the BARRIER. Does NOT kill the agent -- the dropped agent keeps
// running and keeps its concurrency slot until it dies on its own.
// ---------------------------------------------------------------------------
const H6_TIMEOUT_MS = 1800000; // 30 min; blueprint dispatch_timeout_seconds default
const H6_STALL_MS = 90000; // 90 s; B3 falsifier #22

// A typed drop-receipt (design item H3). NEVER return a bare null from a barrier:
// null is produced for at least three different causes -- user skipped the agent,
// the subagent died on a terminal error, and (here) our own timeout -- and
// .filter(Boolean) throws that distinction away, making "12 of 15 returned"
// unauditable.
function h6Receipt(endReason, label, ms, detail) {
  return {
    __h6: true,
    __endReason: endReason, // 'timeout' | 'threw' | 'null'
    label: label,
    ms: ms,
    detail: detail === undefined ? null : detail,
  };
}

function h6IsDrop(r) {
  return !!r && r.__h6 === true;
}
function h6Survivors(results) {
  return results.filter(function (r) {
    return !h6IsDrop(r);
  });
}
function h6Drops(results) {
  return results.filter(h6IsDrop);
}

// Emit one heartbeat line if the unit is still outstanding at H6_STALL_MS.
// Returns a canceller. This is an OBSERVATION ("still waiting"), not a verdict
// that the agent is hung -- the sandbox cannot see orchestrator state.
function h6Heartbeat(label, stallMs) {
  if (typeof setTimeout !== 'function') return function () {};
  const t = setTimeout(function () {
    if (typeof log === 'function') {
      log('H6 heartbeat: still waiting on ' + label + ' after ' + stallMs + 'ms');
    }
  }, stallMs);
  return function () {
    if (typeof clearTimeout === 'function') clearTimeout(t);
  };
}

// Bound ONE thunk. Always resolves -- never rejects, never returns undefined --
// so a barrier over wrapped thunks can no longer be poisoned by one unit.
async function withTimeout(thunk, ms, label, stallMs) {
  const lbl = label === undefined ? 'unit' : label;
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms;
  // Runtime-drift guard: if a future build stops injecting timers, degrade to a
  // plain await instead of dying with a ReferenceError at fan-out time.
  if (typeof setTimeout !== 'function') {
    try {
      return await thunk();
    } catch (err) {
      return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
    }
  }
  const stopBeat = h6Heartbeat(lbl, stallMs === undefined ? H6_STALL_MS : stallMs);
  let timer = null;
  const expiry = new Promise(function (resolve) {
    timer = setTimeout(function () {
      resolve(h6Receipt('timeout', lbl, budgetMs, null));
    }, budgetMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(thunk), expiry]);
  } catch (err) {
    return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
  } finally {
    // ALWAYS clear on the winning path too: an un-cleared timer stays in the
    // runtime's abort set and can hold the workflow open past its last agent.
    if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
    stopBeat();
  }
}

// A SETTLED barrier: same shape as parallel(), but one hung unit costs you that
// unit instead of the phase. Output is index-aligned with `thunks` and every
// slot is either a real result or a typed drop-receipt -- no nulls, no holes.
async function settle(thunks, ms, labels) {
  const nameOf = function (i) {
    return labels && labels[i] !== undefined ? labels[i] : 'unit-' + i;
  };
  const raw = await parallel(
    thunks.map(function (t, i) {
      return function () {
        return withTimeout(t, ms, nameOf(i));
      };
    }),
  );
  return raw.map(function (r, i) {
    // The runtime still yields null for a cause we never saw (a user skip).
    // Type it rather than filtering it away.
    return r === null || r === undefined ? h6Receipt('null', nameOf(i), ms, null) : r;
  });
}

const HOME = 'C:/Users/Prekzursil'
const OUT = `${HOME}/.claude/gem-hunt-2026-07-12`

phase('Ground')
const GS = { type:'object', additionalProperties:false, required:['inventory','overlaps','figmaMcp','gaps'], properties:{ inventory:{type:'string'}, overlaps:{type:'string'}, figmaMcp:{type:'string'}, gaps:{type:'string'} } }
const ground = await agent(`GROUND for a UI/UX-tooling consolidation hunt. Inventory the workspace CURRENT UI/UX design tooling so the lenses dedup + propose real merges. Read (Read/Glob; PowerShell for shell — Bash broken):
- Our UI/UX SKILLS SKILL.md under ${HOME}/.claude/skills/: ui-audit, ui-ux-pro-max, transpose-to-figma, design-review-loop, design-system, figma, figma-implement-design (if present), visual-review, artifact-design. Summarize what EACH does + its inputs/outputs/deps.
- The Figma MCP: the mcp__figma__* tool surface (from ${HOME}/.mcp.json + memory reference_figma_mcp_and_seat) — what it can/cannot do (design context, generate_figma_design/transpose, screenshots, variables, code-connect).
- The design HOOK + memory: ${HOME}/.claude/projects/C--Users-Prekzursil/memory/feedback_uiux_figma_first.md + the DesignToolReminderModule in ${HOME}/.agents/harness/modules.py (just added).

Produce: inventory (each skill: what/in/out/deps), overlaps (where 2+ skills duplicate — e.g. ui-audit vs visual-review; transpose-to-figma vs figma generate; design-review-loop wrapping several), figmaMcp (the MCP capabilities + limits), gaps (what is MISSING for the owner asks: interactive-live-modify with an assisting Claude/Codex, an app/GUI DRIVER, always-mirror-built-UI-to-Figma, SOTA audit).`, { label:'ground', phase:'Ground', schema: GS })

phase('Fan-out')
const DEDUP = (JSON.stringify(ground) || '').slice(0, 7000)
const CTX = `Workspace = Claude Code (Opus) + Codex CLI (mingle) + a Figma FULL/expert seat + these UI/UX skills already present: ui-audit (deterministic live-app audit + Track-B critique rubric), ui-ux-pro-max (67 styles/96 palettes/57 font-pairings DB), transpose-to-figma (code->canvas), design-review-loop (G0-G7 TCR loop orchestrator), design-system, figma (design->code MCP flow), figma-implement-design, visual-review, artifact-design. Owner wants: (A) CONSOLIDATE/AGGREGATE these into a coherent unified pipeline (they overlap); (B) SOTA best-of-the-best UI/UX AUDIT solutions; (C) an INTERACTIVE-MODIFY workflow where the owner + an assisting model session (Claude/Codex) iterate on a live GUI WITH suggestions, and the audit handles it; (D) a build/DRIVE skill that drives apps/GUIs; (E) ALWAYS mirror every built UI/UX into Figma (or Claude Code) so it is documentable + modifiable anytime; (F) upgrade/expand the Figma MCP or build a NEW design MCP if warranted. Owner values plug-and-play, honesty, exhaustive-parallel. CURRENT-TOOLING DEDUP-SET (do NOT just re-list; propose MERGES/UPGRADES vs these): ${DEDUP}`
const RUBRIC = `Per find: name, what, why-for-owner, how-to-build/adopt/merge, source(CITE repo/paper/URL), value×effort, NATIVE-vs-BUILD, confidence. Anti-overfit: ride the existing skill/MCP/harness bus; prefer merge/enable-native over new-runtime; be honest (already-built or vaporware = say so). 5-12 concrete finds.`
const FS = { type:'object', additionalProperties:false, required:['lens','findings_markdown'], properties:{ lens:{type:'string'}, findings_markdown:{type:'string'} } }
const LENSES = [
  { key:'consolidate-arch', focus:'CONSOLIDATION architecture (the owner INSISTS on this): design how to AGGREGATE ui-audit + ui-ux-pro-max + transpose-to-figma + design-review-loop + design-system + figma + visual-review into ONE coherent unified UI/UX pipeline (a meta-skill or a clean staged flow) that eliminates the overlaps. Concrete: which merge into which, the unified entry point, what each stage owns.' },
  { key:'sota-uiux-audit', focus:'SOTA best-of-the-best UI/UX AUDIT tools/methods (2025-2026): visual-regression, a11y (axe/pa11y/Playwright), design-QA, LLM/multimodal design-critique (UIClip, GPT-vision design scoring), heuristic eval automation. What beats/upgrades our ui-audit? Cite tools/papers/repos.' },
  { key:'sota-design-to-code', focus:'SOTA design<->code + code<->design skills/tools (2025-2026): the best design-to-code (Figma->code) + code-to-design (transpose) tools beyond the Figma MCP — v0, Builder.io, Anima, html.to.design, story.to.design, Locofy, tempo. What to adopt/upgrade our transpose-to-figma + figma-implement-design?' },
  { key:'sota-figma-automation', focus:'Figma MCP UPGRADE / new-MCP: the official Figma MCP capabilities we under-use + third-party Figma automation (figma-rest, figma plugins, variables/tokens sync, code-connect). Should we EXPAND the Figma MCP integration or build a NEW design-mirror MCP? Grade honestly.' },
  { key:'app-driver-capability', focus:'The owner wants a BUILD/DRIVE skill: SOTA live-app / GUI DRIVING agent patterns (Playwright/CDP/computer-use, hot-reload-in-the-loop, browser-in-the-loop). Design a ui-drive skill that drives a live app/GUI so the owner + an assisting model can INTERACTIVELY modify the UI, with the audit + revert-gate handling it. How to build on our ui-audit + claude-in-chrome + visual-review?' },
  { key:'interactive-modify', focus:'INTERACTIVE-MODIFY workflow: the owner + an assisting model session (Claude AND Codex via mingle) iterating on a live GUI WITH suggestions + a running audit. SOTA human-in-the-loop + multi-agent design-iteration patterns. Design the loop (drive -> audit -> suggest -> owner-selects -> apply-as-reversible-commit -> re-audit).' },
  { key:'figma-mirror-practice', focus:'ALWAYS-MIRROR-TO-FIGMA: the owner wants every built UI/UX auto-documented/mirrored into Figma (or Claude Code) so it is modifiable anytime. Design a standing PRACTICE/hook/skill: auto-transpose built UI to the canvas on change (or a design-mirror layer that keeps Figma and code in sync). Reliability of the code-to-Figma round-trip (what survives). Cite.' },
  { key:'new-uiux-skills', focus:'NEW / undiscovered high-value OSS UI/UX skills to ADOPT (GitHub awesome-lists, Anthropic skills, high-star): design skills we lack. Cite + value×effort.' },
  { key:'merge-upgrade', focus:'MERGE/UPGRADE ideas for our existing UI/UX skills: concrete upgrades to ui-audit (more gates?), ui-ux-pro-max (newer DB?), design-review-loop (better G0-G7?), transpose-to-figma (better path selection?). What each is missing vs SOTA.' },
  { key:'cross-model-design', focus:'CROSS-MODEL (Claude+Codex) collaborative interactive UI/UX design via the mingle channel: how do the two models best COLLABORATE on live UI iteration (one drives, one critiques; parallel variants; consensus)? SOTA multi-agent design + our mcp_agent_mail bus.' },
  { key:'design-tokens-system', focus:'SOTA design-SYSTEM / TOKENS / theming tooling (2025-2026): DTCG tokens, Style Dictionary, Tokens Studio, tokens<->Figma-variables sync, theme generation. Upgrade our design-system skill + the tokens.css<->Figma bridge.' },
  { key:'a11y-visual-reg', focus:'SOTA A11Y + VISUAL-REGRESSION gates (2025-2026): axe-core, Playwright a11y, Chromatic/Percy/Loki, Storybook test-runner, the best automated visual+a11y CI gates to make UI/UX quality enforceable. What to wire as gates.' },
  { key:'plug-and-play-uiux', focus:'PLUG-AND-PLAY UI/UX pipeline (owner values turnkey): a zero-config / self-healing design pipeline — auto-detect the app, auto-run the audit, auto-mirror to Figma, one-command. What makes the whole UI/UX flow turnkey?' },
  { key:'llm-design-critique', focus:'SOTA LLM / multimodal DESIGN-CRITIQUE + generation (2025-2026): vision-model design scoring, UIClip, design-quality models, Claude/GPT design critique prompts, AI design-review benchmarks. Upgrade our Track-B critique rubric with the best.' },
  { key:'wildcard-uiux', focus:'WILDCARD: the genuinely novel UI/UX-tooling gem nobody would prompt for — a mechanism/tool/pattern that could be a step-change for the owner design workflow (e.g. bidirectional live Figma<->code sync, a design-diff reviewer, an autonomous UX-tester). Be creative; cite; grade.' },
]
const findings = h6Survivors(await settle(LENSES.map(l => () =>
  agent(`You are ONE lens of a FOCUSED UI/UX-tooling consolidation hunt. Lens: ${l.key}.

FOCUS: ${l.focus}

${CTX}

${RUBRIC}

Use ToolSearch->WebSearch/firecrawl/exa/github/context7 for SOTA (2025-2026); Read the live skill files under ${HOME}/.claude/skills/ where relevant. Return findings_markdown = a concise markdown list. This lens is BLIND to the others.`, { label:`ux:${l.key}`, phase:'Fan-out', schema: FS, model: 'fable' })
), H6_TIMEOUT_MS))

phase('Synthesize')
const SS = { type:'object', additionalProperties:false, required:['docPath','consolidationPlan','newCapabilities','topGems','summary'], properties:{ docPath:{type:'string'}, consolidationPlan:{type:'string'}, newCapabilities:{type:'array',items:{type:'string'}}, topGems:{ type:'array', items:{ type:'object', additionalProperties:false, required:['name','tier','rec','valueEffort'], properties:{ name:{type:'string'}, tier:{type:'string'}, rec:{type:'string'}, valueEffort:{type:'string'} } } }, summary:{type:'string'} } }
const synth = await agent(`Synthesize ${findings.length} UI/UX-tooling lens findings into a decision-queue, with the owner INSISTED deliverable front and center: a concrete CONSOLIDATION plan. Steps: (1) dedup + note cross-lens convergence. (2) consolidationPlan = the concrete architecture to AGGREGATE our overlapping UI/UX skills (ui-audit/ui-ux-pro-max/transpose-to-figma/design-review-loop/design-system/figma/visual-review) into ONE coherent pipeline — say exactly which merge, the unified entry, and what to retire. (3) newCapabilities = the designs for the owner new asks: the app/GUI DRIVER (ui-drive), the INTERACTIVE-MODIFY loop (owner + Claude/Codex + live audit), and ALWAYS-MIRROR-TO-FIGMA (auto-document built UI on the canvas) — each with a concrete build sketch on the existing bus. (4) TIER the finds (TIER-0, consolidate-now, new-capabilities, tooling/MCP, SOTA-audit-upgrades, new-skills, prune, skip) with per-item rec + value×effort + NATIVE-vs-BUILD + citation. (5) Write the FULL decision-queue to ${OUT}/UIUX-CONSOLIDATION-DECISION-QUEUE.md (create dir; Write). Return docPath + the consolidationPlan + newCapabilities + top ~12 gems + a 4-sentence summary.

Lens findings (JSON): ${JSON.stringify(findings).slice(0, 240000)}

Insist on the CONSOLIDATION (the owner explicit ask); prefer merge/enable-native over new-build; ride the existing skill/MCP/harness bus.`, { label:'synthesize', phase:'Synthesize', schema: SS, model:'opus' })

const VS = { type:'object', additionalProperties:false, required:['notes','refuted','confirmed'], properties:{ notes:{type:'string'}, refuted:{type:'array',items:{type:'string'}}, confirmed:{type:'array',items:{type:'string'}} } }
const verify = await agent(`ADVERSARIALLY VERIFY the UI/UX consolidation plan + top gems. Check: (a) does the consolidation plan actually match what our skills DO (read ${HOME}/.claude/skills/ui-audit, ui-ux-pro-max, transpose-to-figma, design-review-loop SKILL.md)? (b) are the cited tools/repos real + as-claimed (spot-check 3-4)? (c) do the new capabilities (ui-drive, interactive-modify, figma-mirror) violate the anti-overfit gate or duplicate an existing skill? (d) is the code-to-Figma round-trip claim (always-mirror) realistic — what actually survives the round-trip? Report notes + refuted + confirmed. Default skeptical.

Consolidation plan: ${(synth.consolidationPlan||'').slice(0,4000)}
New capabilities: ${JSON.stringify(synth.newCapabilities||[])}
Top gems: ${JSON.stringify(synth.topGems||[])}`, { label:'verify', phase:'Synthesize', schema: VS, model:'opus' })

log(`UIUX consolidation: ${findings.length} lenses; verify confirmed ${(verify.confirmed||[]).length}, refuted ${(verify.refuted||[]).length}`)
return { decisionDoc: synth.docPath, consolidationPlan: synth.consolidationPlan, newCapabilities: synth.newCapabilities, topGems: synth.topGems, summary: synth.summary, verify: { refuted: verify.refuted, confirmed: verify.confirmed }, lensesRun: findings.length }