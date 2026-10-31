export const meta = {
  name: 'agentic-repair-reliability',
  description: 'SOTA research + harness audit + gem design: why agentic repair produces green-tested-but-non-functional software, and the external-signal harness upgrades that fix it',
  phases: [
    { title: 'Research-Audit' },
    { title: 'Synthesize' },
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

const PROBLEM = `THE PROBLEM (user's lived pain, verbatim essence): Long, expensive agentic repair sessions on non-trivial apps (beyond CRUD) "barely move an inch." The AI claims "100% tested" and "done" while the app fundamentally does NOT work — features don't function, buttons do nothing or freeze, the core feature (make shorts) doesn't produce output, settings may be ignored, "held together with chewing gum, breakable at almost any click." It fixes a ZONE of the app in vitro (isolated), claims done, but the end-to-end flow A→B→C is completely broken and it dismisses that. It BLINDSPOTS depth + actual functionality: unless the user explicitly names each broken thing, it passes "done" — as if it ignores the app's SCOPE and that it isn't working, despite "100% coverage." It only uses a few of the many available skills, and only when explicitly asked; won't chain skills or "remove the horse blinders." The fix loop is wasteful: edit a few files → rerun the FULL test batch → repeat — repetitive, token-guzzling, ineffective. The user wants: analyze the bugs PROPERLY, then dispatch agents/workflows to fix, then CONFIRM — with independent thinking that understands what needs doing WITHOUT the user naming every defect.`

const HARNESS = `THE USER'S EXISTING HARNESS (do NOT propose from zero — this is already very large; the fix is a FEW high-leverage external-signal gates, not 20 new hooks): agent-skills-toolchain has ~185 skills + 37 claude-only + ~35 hook-groups; global ~/.claude/hooks has ~60 groups incl: claim-guard, dark-surface (GREEN-not-LIVE stub detector), honest-signal, truth-verify, wire-check, stub-ledger, test-tamper-guard, fresh-verify, goal-reinject, harness-bench, harness-trim, iatrogenics, calibrated-silence (anti-nag gate), semantic-router + skill-router (skill auto-suggest), strong-tool-nudge, capability-catalog, verification-before-completion (superpowers skill), ui-audit skill (drives a running app + emits an accessibility/functional audit + a DESIGN-EVAL verdict), reframe/media skills. Plus metaswarm (design/plan/adversarial-review gates, TDD, coverage). 
DESIGN LAW (from ~/.claude/SELF-CALIBRATION-PLAN.md, research-backed): intrinsic SAME-CONTEXT self-correction does NOT work and can DEGRADE reasoning (Huang et al. ICLR 2024 "LLMs Cannot Self-Correct Reasoning Yet"). Every self-check MUST anchor to an EXTERNAL signal the model cannot fake — a tool/execution result, an independently-sampled question, a FRESH-CONTEXT reviewer, or a written rubric. Hooks TRIGGER + supply the signal; only a separate model call JUDGES. A hook that just injects "are you sure?" is a proven placebo. Anti-overfit ceiling: ~6 hooks total, NOT 95 — new hooks must be domain-narrow + fail-open + non-nagging (calibrated-silence gated). The plan ALREADY specced (but did NOT build) a "media/functional output-verification gate": when a rendered artifact is produced or "done" is claimed, BLOCK until the output was actually extracted/viewed + judged — motivated by the exact 2026-06-26 Reframe "declared shorts done without looking" failure.`

const EVIDENCE = `LIVE EVIDENCE (Reframe/Media Studio audit, 2026-07-07, an Electron+Python video app) — a textbook instance of the problem: "100% line+branch coverage" BUT the Electron main/** process is coverage-EXCLUDED; ~288 pragma:no-cover + ~84 v8-ignore carve-outs; TWO real product bugs (privacy: transcript egress without consent; corrupted auth header) hidden from the blocking gate behind @pytest.mark.xfail(strict=True) + addopts -m 'not e2e'; the e2e workflow (the only real end-to-end signal) is RED and effectively ignored; a missing React ErrorBoundary + eager-rpc white-screen P0 shipped; 77 commits "shipped" to the auto-update feed that NEVER ran CI. i.e. the done-signal (coverage) was optimized while the goal (a working app) was not — Goodhart/reward-hacking on a gameable proxy, in-vitro fixes, functional flow unvalidated.`

const HONESTY = `Ground every claim: cite a paper/URL for SOTA claims (use web search — you can ToolSearch for WebSearch/WebFetch/firecrawl/exa/tavily/perplexity), or a file path for harness claims (repo at /c/Users/Prekzursil/source/agent-skills-toolchain and ~/.claude, read-only). If unknown, say UNKNOWN. Be specific and buildable, not generic. Respect the user's anti-overfit philosophy (few high-leverage external-signal gates, not many nags).`

phase('Research-Audit')
const LENS_SCHEMA = {
  type: 'object', additionalProperties: false,
  properties: {
    lens: { type: 'string' },
    key_findings: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      finding: { type: 'string' }, why_it_matters: { type: 'string' }, source: { type: 'string', description: 'paper/URL or file path' } }, required: ['finding','why_it_matters','source'] } },
    actionable_takeaways: { type: 'array', items: { type: 'string' }, description: 'concrete techniques/patterns applicable to this harness' },
  },
  required: ['lens','key_findings','actionable_takeaways'],
}
const LENSES = [
  { key: 'verification-gap', prompt: `${PROBLEM}\n\n${HONESTY}\n\nLENS: **SOTA on the verification gap in agentic coding — why LLM agents produce tests-pass-but-broken software.** Research (2024-2026, real papers/practices): Goodhart's law / reward-hacking on test & coverage metrics; the implementer-writes-the-tests bias; coverage as a proxy that measures line-execution not behavior; SWE-bench / SWE-agent findings on "resolved but wrong"; specification-gap / underspecification; why unit-green ≠ integration-works; test tampering / weakening tests to pass; "LLMs Cannot Self-Correct" and external-signal verification; verifier models & execution-grounded feedback; property-based & metamorphic testing catching what example tests miss. Cite sources. Fill schema.` },
  { key: 'autonomous-depth', prompt: `${PROBLEM}\n\n${HONESTY}\n\nLENS: **SOTA on getting agents to autonomously comprehend WHOLE-app scope + validate end-to-end WITHOUT the human naming every defect.** Research: acceptance-test-driven / behavior-driven development as the "definition of working"; spec-driven development; user-journey / end-to-end-first testing; GUI validation via vision/screenshot + LLM-as-judge (computer-use, WebArena/OSWorld-style functional eval); planner→executor→VERIFIER separation; reflexion / critic loops anchored to EXECUTION (not same-context); multi-agent debate for scope; "red-team your own done" / fresh-context acceptance review; how frontier harnesses (Devin/OpenHands/SWE-agent/Claude Code patterns) achieve breadth. What makes an agent enumerate what SHOULD work and check each, vs fix the named zone. Cite. Fill schema.` },
  { key: 'triage-dispatch-econ', prompt: `${PROBLEM}\n\n${HONESTY}\n\nLENS: **SOTA on efficient bug-fix orchestration — analyze-then-dispatch vs the edit-a-file-rerun-everything churn.** Research: batch bug triage / defect-mapping before fixing; parallel fix agents on independent defects; test impact analysis / selective test execution (run only affected tests, not the full suite each edit); verification pipelines; regression-guard; the token/time economics of myopic edit-rerun loops vs plan-then-parallelize-then-verify-once. Also: why a big up-front functional audit that produces a defect graph is cheaper than incremental blind fixes. Cite. Fill schema.` },
  { key: 'harness-audit', prompt: `${PROBLEM}\n\n${HARNESS}\n\n${HONESTY}\n\nLENS: **Audit the user's OWN harness — why 185 skills + 60 hooks are NOT catching this.** Read agent-skills-toolchain (skills/, skills-claude-only/, hooks/) + ~/.claude/hooks + ~/.claude/SELF-CALIBRATION-PLAN.md + docs/agentic-perfection/. For dark-surface, honest-signal, wire-check, stub-ledger, test-tamper-guard, fresh-verify, verification-before-completion, ui-audit, semantic-router/skill-router: what does each ACTUALLY check, and WHY does none force end-to-end functional validation / block a gameable "done"? Diagnose (a) the SKILL-UNDERUSE mechanism (why only a few fire, why no chaining — is skill-router advisory not enforcing?), (b) which existing pieces are 80% of a fix but unwired/advisory-only, (c) the specific GAP vs the needed external-signal functional-acceptance gate. Be concrete with file evidence. Fill schema.` },
  { key: 'user-side-diagnosis', prompt: `${PROBLEM}\n\n${EVIDENCE}\n\n${HONESTY}\n\nLENS: **Honest diagnosis: what is the USER doing wrong / not providing, vs what is a genuine harness/model limitation.** The user explicitly asked "what am I doing wrong or not providing so the AI can comprehensively audit + handle all errors." Split cleanly: (A) USER-CONTROLLABLE — e.g., no explicit "definition of working" / acceptance criteria; no golden end-to-end user-journey the agent must make pass; accepting "tests pass"/coverage as the done-signal; letting the agent choose its own test surface; not demanding a runnable functional demo/screenshot; not asking for a defect-map before fixes; not forbidding new pragma:no-cover/xfail. (B) HARNESS/MODEL LIMITATION the user CANNOT prompt around and that needs a gate/gem. For each USER item give the exact better instruction/artifact they should provide. Be blunt but fair. Fill schema.` },
  { key: 'red-team-solutions', prompt: `${PROBLEM}\n\n${HARNESS}\n\n${HONESTY}\n\nLENS: **Red-team the obvious fixes BEFORE we recommend them.** Candidate gems: a blocking "functional-acceptance gate" (no "done" on an app repo until an end-to-end user journey was driven + observed); a "coverage-theater detector" (flag NEW pragma:no-cover / xfail(strict) / -m 'not e2e' / coverage-excluded main paths); a "scope/user-journey enumeration" gate; a "run-the-app + screenshot + judge" verification loop generalizing ui-audit; a "triage-then-dispatch" workflow default; making skill-router ENFORCING not advisory. For EACH: how does it fail or become the nagging the user hates? Which are placebos (same-context) vs real (external-signal)? Which violate the ~6-hook anti-overfit ceiling? What is the MINIMUM set that actually moves the needle? What could BACKFIRE (false-blocks, blocking legit work, e2e flakiness making the gate untrustworthy)? Fill schema.` },
]
const research = h6Survivors(await settle(LENSES.map(l => () =>
  agent(l.prompt, { label: `lens:${l.key}`, phase: 'Research-Audit', schema: LENS_SCHEMA, effort: 'high' })
), H6_TIMEOUT_MS))
const dossier = research.filter(Boolean).map(r => `## ${r.lens}\nFINDINGS:\n${(r.key_findings||[]).map(f=>`- ${f.finding} — ${f.why_it_matters} [${f.source}]`).join('\n')}\nTAKEAWAYS: ${(r.actionable_takeaways||[]).join(' | ')}`).join('\n\n')

phase('Synthesize')
const SYNTH = {
  type: 'object', additionalProperties: false,
  properties: {
    root_cause: { type: 'string', description: 'the ONE core mechanism, stated crisply (why green-but-broken happens)' },
    root_causes_detailed: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { cause: { type: 'string' }, mechanism: { type: 'string' }, external_signal_that_fixes_it: { type: 'string' } }, required: ['cause','mechanism','external_signal_that_fixes_it'] } },
    what_user_should_change: { type: 'array', items: { type: 'object', additionalProperties: false, properties: { change: { type: 'string' }, exact_artifact_or_instruction: { type: 'string' }, why: { type: 'string' } }, required: ['change','exact_artifact_or_instruction','why'] } },
    harness_gems: { type: 'array', items: { type: 'object', additionalProperties: false, properties: {
      name: { type: 'string' }, type: { type: 'string', enum: ['hook','skill','mcp','workflow-pattern','config'] }, what_it_does: { type: 'string' }, external_signal: { type: 'string', description: 'the ungameable signal it anchors to' }, trigger: { type: 'string' }, judge: { type: 'string', description: 'who/what judges (must be a separate model call or a tool result, not same-context)' }, anti_nag: { type: 'string' }, priority: { type: 'string', enum: ['P0','P1','P2'] }, effort: { type: 'string', enum: ['S','M','L'] } }, required: ['name','type','what_it_does','external_signal','trigger','judge','anti_nag','priority','effort'] } },
    north_star_repair_flow: { type: 'string', description: 'how a repair session on a non-CRUD app SHOULD flow, end to end, to be reliable + token-efficient' },
    reframe_recipe: { type: 'string', description: 'the concrete first thing to do differently on Reframe specifically to prove the new approach' },
    honest_caveats: { type: 'array', items: { type: 'string' } },
  },
  required: ['root_cause','root_causes_detailed','what_user_should_change','harness_gems','north_star_repair_flow','reframe_recipe','honest_caveats'],
}
const result = await withTimeout(() => agent(`${PROBLEM}\n\n${HARNESS}\n\n${EVIDENCE}\n\n${HONESTY}\n\nSynthesize the research/audit dossier into a decisive, buildable answer to the user's real question ("what am I doing wrong / what harness upgrade makes agentic repair reliable instead of a token-wasting green-but-broken loop"). Anchor everything to the SELF-CALIBRATION design law (external signal, not same-context; hooks trigger, separate model judges) and the ~6-hook anti-overfit ceiling. Prioritize the MINIMUM high-leverage set. Distinguish clearly what the USER must provide vs what a GEM must enforce. Every gem must name its ungameable external signal + a real judge + an anti-nag gate. Be specific to this harness and the Reframe evidence — not generic advice.\n\nDOSSIER:\n${dossier}`, { label: 'synthesize', phase: 'Synthesize', schema: SYNTH, effort: 'high' }), 1500000, 'synthesize')

return result