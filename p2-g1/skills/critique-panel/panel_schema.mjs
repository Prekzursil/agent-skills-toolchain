/**
 * panel_schema.mjs — critique-panel (G3 CRITIQUE) PURE schema + assembly core.
 *
 * Implements the G3 multi-agent named-persona design critique from the design-SOTA
 * spec (DESIGN-WORKFLOW.md G3 + DESIGN-SKILLS-AND-EVAL.md §1.2 + §2). Four named
 * heuristic-persona reviewers each reason over the SAME pre-computed Track-A numbers
 * (ui-audit `audit.json`) + the screenshot, run NN/g "I Like / I Wish / What If",
 * score the DESIGN-EVAL v1 dimensions 0-4 with a critical-error override, and emit a
 * typed verdict. `synthesizePanel` then dedupes + ranks them into one findings list
 * and a weighted composite.
 *
 * PURE module: NO I/O, NO browser, NO model call, and — the hard architecture rule —
 * NO pixel math / geometry estimation / coordinate guessing. The personas REASON over
 * numbers Track-A already measured; this module only routes evidence, builds the per-
 * persona brief, validates the typed verdicts, and aggregates them. (Spec: "Reason over
 * the pre-computed numbers; never pixel-ground.")
 *
 * Sources implemented (cited inline):
 *   - DESIGN-WORKFLOW.md G3 — NN/g Design Critique ritual + "I Like / I Wish / What If"
 *     + named multi-agent panel as TRIAGE (human is decider), not an oracle.
 *   - DESIGN-SKILLS-AND-EVAL.md §1.2 — the four personas
 *     (Nielsen / Refactoring-UI / WCAG-A11y / Brand-Consistency), quota technique.
 *   - DESIGN-SKILLS-AND-EVAL.md §2.1-§2.4 — 0-4 scale, the 9 dimensions + weights +
 *     critical-error triggers, weighted composite, critical-error override + cap.
 *   - DESIGN-SKILLS-AND-EVAL.md §3 — defer DIRECTION to the user; enumerate, don't pick.
 */

// ---------------------------------------------------------------------------
// Vocabulary (single source of truth — schemas + validators all read these)
// ---------------------------------------------------------------------------

/**
 * The four named critique personas (spec §1.2). Each carries the canonical
 * method it evaluates against and the scored dimensions it OWNS. Dimensions are
 * deliberately double-covered on the high-weight / critical-prone axes so the
 * panel cross-checks rather than relying on one judge (kills the halo effect).
 */
export const PERSONAS = {
  'user-advocate': {
    label: 'User Advocate',
    method: "Nielsen's 10 usability heuristics (NN/g heuristic evaluation)",
    question: 'Would a real user accomplish the top job in this flow — does the eye land on the primary action, are controls wired, are empty/error states recoverable?',
    owns: ['visual-hierarchy', 'empty-error-states', 'affordance', 'consistency'],
  },
  'systems-consistency': {
    label: 'Systems / Consistency Reviewer',
    method: 'Refactoring UI + Material 3 / HIG system discipline + Nielsen #4 (consistency & standards)',
    question: 'Is this on-system — on a 4/8px spacing scale, a limited type ramp, shared edges, and the same components/tokens across screens?',
    owns: ['spacing-rhythm', 'type-scale', 'alignment', 'consistency'],
  },
  'a11y': {
    label: 'Accessibility (WCAG) Evaluator',
    method: 'WCAG 2.2 AA + WCAG 3.0 scoring draft',
    question: 'Can everyone use it — does text meet contrast AA, are tap targets >=44px, is focus visible, and does motion honour prefers-reduced-motion?',
    owns: ['color-contrast', 'affordance', 'motion'],
  },
  'brand-aesthetic': {
    label: 'Brand / Aesthetic Reviewer',
    method: 'Refactoring UI colour & personality + Nielsen #8 (aesthetic & minimalist) + brand voice',
    question: 'Does it feel intentional and on-brand — harmonious palette, emphasis by de-emphasis, polished, expressive-not-decorative motion?',
    owns: ['visual-hierarchy', 'color-contrast', 'type-scale', 'motion'],
  },
};

export const PERSONA_IDS = Object.keys(PERSONAS);

/**
 * The nine scored design dimensions (DESIGN-EVAL v1, spec §2.2) with their
 * composite weight and the critical-error trigger that forces the dimension to 0.
 */
export const DIMENSION_META = {
  'visual-hierarchy':   { weight: 1.5,  critical: 'no focal point AND primary CTA indistinguishable' },
  'spacing-rhythm':     { weight: 1.0,  critical: 'colliding / overlapping content blocks' },
  'alignment':          { weight: 0.75, critical: null },
  'type-scale':         { weight: 1.0,  critical: 'body text illegibly small or over-set' },
  'color-contrast':     { weight: 2.0,  critical: 'any body text below 4.5:1' },
  'consistency':        { weight: 1.0,  critical: 'same component renders differently across core screens' },
  'empty-error-states': { weight: 1.5,  critical: 'render crash / blank where content expected / dead primary action' },
  'affordance':         { weight: 1.5,  critical: 'primary action gives no signifier or no feedback' },
  'motion':             { weight: 0.75, critical: 'janky/blocking animation or motion with no reduced-motion escape' },
};

/** The 9 scored dimensions (personas grade only these). */
export const DIMENSIONS = Object.keys(DIMENSION_META);

/** Evidence buckets = the 9 dimensions + a holistic `overall` context bucket. */
export const EVIDENCE_BUCKETS = [...DIMENSIONS, 'overall'];

/** Finding severities, most -> least urgent (severity ladder = Nielsen 0-4, spec §1.1). */
export const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];

/** Per-dimension ordinal score band (spec §2.1). */
export const SCORES = [0, 1, 2, 3, 4];

/** How sure the persona is — expect `low` on pure-aesthetic dims (spec §2.5). */
export const CONFIDENCES = ['high', 'medium', 'low'];

/** Panel-level verdict buckets. */
export const VERDICTS = ['good', 'needs-work', 'poor'];

const _SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
/** Numeric rank for a severity (higher = more urgent). Unknown -> 0. */
export function rankSeverity(sev) {
  return _SEV_RANK[sev] || 0;
}

/** Severity (named ladder) -> the 0-4 score band it implies (spec §1.1). */
export const SEVERITY_TO_BAND = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };

// ---------------------------------------------------------------------------
// 1. Evidence routing — Track-A rule/signal -> design dimension (9-dim, spec §2.2)
// ---------------------------------------------------------------------------

const RULE_TO_DIMENSION = {
  'off-scale-spacing': 'spacing-rhythm',
  'wcag-contrast': 'color-contrast',
  'color-inventory-sprawl': 'color-contrast',
  'type-scale-sprawl': 'type-scale',
  'tap-target': 'affordance',
  'focus-visible': 'affordance',
  'motion-duration': 'motion',
  'reduced-motion': 'motion',
  'dropped-frames': 'motion',
};

/** Classify an axe rule id onto a dimension (best-effort, nothing dropped). */
function axeDimension(id = '') {
  if (/contrast/i.test(id)) return 'color-contrast';
  if (/focus|keyboard|tabindex|focusable/i.test(id)) return 'affordance';
  if (/motion|animation|blink|marquee|reduced/i.test(id)) return 'motion';
  if (/heading|landmark|region|list|structure|order|skip-link|bypass/i.test(id)) return 'visual-hierarchy';
  return 'overall';
}

/**
 * Project a Track-A audit.json onto the evidence buckets (9 dims + overall).
 * Returns { [bucket]: Evidence[] } for every bucket (empty arrays allowed).
 * Every item is traceable back to a Track-A finding id / signal.
 */
export function projectFindingsByDimension(audit = {}) {
  const out = {};
  for (const d of EVIDENCE_BUCKETS) out[d] = [];
  const push = (dim, ev) => { if (out[dim]) out[dim].push(ev); };

  // merged layout-lint + dead-button findings
  for (const f of (audit.findings || [])) {
    const screen = f.screen || 'unknown';
    if (f.rule && RULE_TO_DIMENSION[f.rule]) {
      push(RULE_TO_DIMENSION[f.rule], {
        ref: f.id || f.rule, gate: f.gate || 'layout-lint', rule: f.rule, screen,
        value: f.value, severity: f.severity || 'info', source: f.gate || 'layout-lint',
        detail: f.message || '',
      });
      continue;
    }
    if (f.effect === 'none' || f.effect === 'error') {
      push('empty-error-states', {
        ref: f.id || f.selector || 'dead', gate: 'dead-button',
        rule: f.effect === 'none' ? 'dead-control' : 'click-error', screen,
        value: f.selector || f.text || '', severity: f.effect === 'none' ? 'high' : 'low',
        source: f.gate || 'dead-button',
        detail: f.effect === 'none'
          ? `${f.selector || ''} ${f.text || ''} has no observable effect`
          : (f.clickError || 'non-actionable click'),
      });
    }
    // effect: nav|dom|network|console|dialog -> wired control, not a defect.
  }

  // axe accessibility violations
  for (const a of (audit.axe || [])) {
    push(axeDimension(a.id), {
      ref: a.id || 'axe', gate: 'axe', rule: a.id || 'axe', screen: a.screen || 'unknown',
      value: `${a.nodes ?? 0} node(s)`, severity: a.impact || 'moderate', source: 'axe',
      detail: a.description || '',
    });
  }

  // uncaught page errors (render/crash)
  for (const e of (audit.pageErrors || [])) {
    push('empty-error-states', {
      ref: `pageerror-${e.screen || 'unknown'}`, gate: 'capture', rule: 'page-error',
      screen: e.screen || 'unknown', value: e.name || 'Error', severity: 'critical',
      source: 'pageError', detail: e.message || '',
    });
  }

  // optional motion collector (spec §1.1 — added to ui-audit Track-A)
  for (const m of (audit.motion || [])) {
    push('motion', {
      ref: m.id || `motion-${m.screen || 'unknown'}`, gate: 'motion', rule: m.rule || 'motion',
      screen: m.screen || 'unknown', value: m.value ?? '', severity: m.severity || 'info',
      source: 'motion', detail: m.message || '',
    });
  }

  // visual regressions (>5% drift) -> cross-screen consistency
  for (const v of (audit.visual || [])) {
    if ((v.percentDiff || 0) > 5) {
      push('consistency', {
        ref: `visual-${v.screen || 'unknown'}`, gate: 'visual-diff', rule: 'visual-regression',
        screen: v.screen || 'unknown', value: `${v.percentDiff}%`, severity: 'medium',
        source: 'visual-diff', detail: `screen drifted ${v.percentDiff}% from baseline`,
      });
    }
  }

  // holistic totals (context for every persona; not a scored dim)
  push('overall', {
    ref: 'summary-totals', gate: 'summary', rule: 'totals', screen: 'all',
    value: summarizeOneLine(audit.summary), severity: 'info', source: 'summary',
    detail: JSON.stringify(audit.summary || {}),
  });

  return out;
}

function summarizeOneLine(s = {}) {
  if (!s || typeof s !== 'object') return 'no summary';
  const sp = s.spacing || {};
  return [
    `screens=${s.screens ?? 0}`,
    `spacingHigh=${sp.high ?? 0}`,
    `axe=${s.axeViolations ?? 0}`,
    `dead=${s.deadControls ?? 0}`,
    `pageErrors=${s.pageErrors ?? 0}`,
    `visualRegressions=${s.visualRegressions ?? 0}`,
  ].join(' ');
}

// ---------------------------------------------------------------------------
// 2. Assemble per-persona briefs (the structured prompts each persona fills)
// ---------------------------------------------------------------------------

const BASE_INSTRUCTIONS = [
  'You are ONE named persona on a design-critique PANEL. Stay in character: judge only through your method/lens and own dimensions — the other personas cover the rest.',
  'REASON over the pre-computed Track-A numbers (evidenceForYou + overallContext) together with the screenshot(s). NEVER pixel-measure, estimate coordinates, or invent geometry — that is Track-A\'s job. Cite numbers by their `ref`.',
  'VIEW every screenshot in `screenshots`. For dimensions with no deterministic signal, judge perceptually and LOWER the confidence; if the render is blank/empty, say so and treat it as an empty/error-state defect.',
  'For EACH of your owned dimensions: give a `score` 0-4 (4 excellent … 0 critical-fail) + a `confidence`, and set `critical: true` only if its critical-error trigger fired (that forces the dimension to 0).',
  'Run "I Like / I Wish / What If": `iLike` = wins to PROTECT, `iWish` = severity-rated defects with grounded evidence + an actionable recommendation, `whatIf` = alternative DIRECTIONS to enumerate (you do NOT pick — the human decides at G4).',
  'QUOTA (anti-tunnel-vision, even solo): at least 2 `iLike` wins and at least 1 `iWish` fix across your dimensions, per screen in scope.',
  'Emit ONLY JSON conforming to `outputSchema`, then gate it: `node critique_panel.mjs validate --input <file>` must print SUCCESS before the persona is done.',
];

/**
 * Build ONE persona's brief from Track-A artefacts + the routed evidence.
 * @param {object} args.audit       - parsed Track-A audit.json
 * @param {string} args.persona     - one of PERSONA_IDS
 * @param {string[]} args.screenshots
 * @param {string} [args.rubricText]
 * @param {string[]} [args.scope]   - screens in scope (defaults to summary.screens / 'all')
 */
export function assemblePersonaBrief({ audit = {}, persona, screenshots = [], rubricText = '', scope } = {}) {
  if (!PERSONAS[persona]) throw new Error(`unknown persona '${persona}' (expected one of ${PERSONA_IDS.join('|')})`);
  const shots = Array.isArray(screenshots) ? screenshots.filter(Boolean) : (screenshots ? [screenshots] : []);
  const spec = PERSONAS[persona];
  const byDim = projectFindingsByDimension(audit);

  const evidenceForYou = {};
  for (const d of spec.owns) {
    evidenceForYou[d] = { weight: DIMENSION_META[d].weight, criticalTrigger: DIMENSION_META[d].critical, evidence: byDim[d] || [] };
  }

  return {
    task: 'design-critique-panel-persona',
    persona,
    personaLabel: spec.label,
    method: spec.method,
    centralQuestion: spec.question,
    audit_id: audit.id || null,
    generatedAt: new Date().toISOString(),
    scope: scope && scope.length ? scope : ['all'],
    screenshots: shots,
    rubric: rubricText || '',
    ownedDimensions: spec.owns,
    evidenceForYou,
    overallContext: byDim.overall || [],
    summary: audit.summary || {},
    severities: SEVERITIES,
    scores: SCORES,
    confidences: CONFIDENCES,
    instructions: BASE_INSTRUCTIONS,
    outputSchema: PERSONA_JSON_SCHEMA,
  };
}

/** Assemble briefs for all four personas at once. */
export function assemblePanelBriefs(opts = {}) {
  return PERSONA_IDS.map((persona) => assemblePersonaBrief({ ...opts, persona }));
}

/** Render a persona brief as Markdown with a fill-in JSON skeleton. */
export function renderPersonaMarkdown(brief) {
  const runId = (brief.audit_id || 'run').replace(/^ui-audit-/, '') || 'run';
  const L = [];
  L.push(`# Critique panel — ${brief.personaLabel} (\`${brief.persona}\`)`);
  L.push('');
  L.push(`**Method.** ${brief.method}`);
  L.push(`**Central question.** ${brief.centralQuestion}`);
  L.push(`**Scope.** ${brief.scope.join(', ')}`);
  L.push('');
  L.push('## How to critique');
  for (const i of brief.instructions) L.push(`- ${i}`);
  L.push('');
  L.push('## Screenshots to view');
  if (brief.screenshots.length === 0) L.push('- (none supplied — judge from numbers only, confidence low)');
  for (const s of brief.screenshots) L.push(`- \`${s}\``);
  L.push('');
  L.push(`## Track-A summary (\`${brief.audit_id || 'n/a'}\`)`);
  L.push('```json');
  L.push(JSON.stringify(brief.summary, null, 2));
  L.push('```');
  L.push('');
  L.push('## Your dimensions + pre-computed evidence');
  for (const d of brief.ownedDimensions) {
    const blk = brief.evidenceForYou[d] || { evidence: [] };
    L.push(`### ${d}  (weight ${blk.weight}${blk.criticalTrigger ? `; critical if: ${blk.criticalTrigger}` : ''})`);
    if (!blk.evidence.length) {
      L.push('- _no deterministic signal; judge perceptually from the screenshot (lower confidence)._');
    } else {
      for (const e of blk.evidence) {
        L.push(`- \`${e.ref}\` [${e.source}/${e.rule}] (${e.severity}) ${e.screen}: ${e.value ?? ''} ${e.detail ? '— ' + e.detail : ''}`.trim());
      }
    }
    L.push('');
  }
  if (brief.overallContext.length) {
    L.push('## Holistic context (totals)');
    for (const e of brief.overallContext) L.push(`- \`${e.ref}\`: ${e.value}`);
    L.push('');
  }
  L.push('## Output — fill this verdict and validate it');
  L.push('Emit ONLY JSON matching `outputSchema`. Skeleton:');
  L.push('```json');
  L.push(JSON.stringify({
    id: `critique-panel-${brief.persona}-${runId}`,
    persona: brief.persona,
    audit_id: brief.audit_id || 'ui-audit-<id>',
    scope: brief.scope,
    dimensions: [
      {
        dimension: brief.ownedDimensions[0], score: 3, confidence: 'medium', critical: false,
        iLike: ['win to protect #1', 'win to protect #2'],
        iWish: [{ severity: 'high', evidence: 'grounded in a ref or a visual observation', evidenceRefs: ['<track-a id>'], recommendation: 'actionable fix' }],
        whatIf: ['an alternative DIRECTION to enumerate (human decides)'],
      },
    ],
    notes: 'optional persona-level note',
  }, null, 2));
  L.push('```');
  return L.join('\n');
}

// ---------------------------------------------------------------------------
// 3. Validate a single persona OUTPUT verdict (incl. the quota gate)
// ---------------------------------------------------------------------------

const isNonEmptyStr = (v) => typeof v === 'string' && v.trim().length > 0;

/**
 * Validate one persona critique object against the persona OUTPUT schema.
 * Collects ALL violations (does not throw on the first). Enforces the quota.
 * @returns {{ valid: boolean, errors: string[], id: (string|null), persona: (string|null) }}
 */
export function validatePersona(output) {
  const errors = [];
  if (!output || typeof output !== 'object' || Array.isArray(output)) {
    return { valid: false, errors: ['persona critique must be a JSON object'], id: null, persona: null };
  }

  if (!isNonEmptyStr(output.id) || !/^critique-panel-/.test(output.id)) {
    errors.push("id must be a non-empty string namespaced 'critique-panel-<persona>-<id>'");
  }
  if (!PERSONA_IDS.includes(output.persona)) {
    errors.push(`persona must be one of ${PERSONA_IDS.join('|')}`);
  }

  const owned = PERSONAS[output.persona] ? PERSONAS[output.persona].owns : DIMENSIONS;
  const nScreens = Array.isArray(output.scope) && output.scope.length
    ? Math.max(1, output.scope.filter((s) => s && s !== 'all').length || 1)
    : 1;

  let likeCount = 0;
  let wishCount = 0;

  if (!Array.isArray(output.dimensions) || output.dimensions.length === 0) {
    errors.push('dimensions must be a non-empty array (score at least one owned dimension)');
  } else {
    output.dimensions.forEach((d, i) => {
      const at = `dimensions[${i}]`;
      if (!d || typeof d !== 'object') { errors.push(`${at} must be an object`); return; }
      if (!DIMENSIONS.includes(d.dimension)) errors.push(`${at}.dimension '${d.dimension}' is not a known dimension`);
      else if (output.persona && !owned.includes(d.dimension)) {
        errors.push(`${at}.dimension '${d.dimension}' is not owned by persona '${output.persona}' (owns: ${owned.join(', ')})`);
      }
      if (!(typeof d.score === 'number' && Number.isInteger(d.score) && d.score >= 0 && d.score <= 4)) {
        errors.push(`${at}.score must be an integer 0..4`);
      }
      if (!CONFIDENCES.includes(d.confidence)) errors.push(`${at}.confidence must be one of ${CONFIDENCES.join('|')}`);
      if (d.critical != null && typeof d.critical !== 'boolean') errors.push(`${at}.critical must be a boolean when present`);
      if (d.critical === true && d.score !== 0) errors.push(`${at}.critical is true so score must be 0 (critical-error override)`);

      if (d.iLike != null && !(Array.isArray(d.iLike) && d.iLike.every(isNonEmptyStr))) {
        errors.push(`${at}.iLike must be an array of non-empty strings when present`);
      } else if (Array.isArray(d.iLike)) likeCount += d.iLike.length;

      if (d.whatIf != null && !(Array.isArray(d.whatIf) && d.whatIf.every(isNonEmptyStr))) {
        errors.push(`${at}.whatIf must be an array of non-empty strings when present`);
      }

      if (d.iWish != null) {
        if (!Array.isArray(d.iWish)) { errors.push(`${at}.iWish must be an array`); }
        else {
          wishCount += d.iWish.length;
          d.iWish.forEach((f, j) => {
            const fat = `${at}.iWish[${j}]`;
            if (!f || typeof f !== 'object') { errors.push(`${fat} must be an object`); return; }
            if (!SEVERITIES.includes(f.severity)) errors.push(`${fat}.severity '${f.severity}' is not one of ${SEVERITIES.join('|')}`);
            if (!isNonEmptyStr(f.evidence)) errors.push(`${fat}.evidence must be a non-empty string (a number-by-ref or an explicit visual observation)`);
            if (!isNonEmptyStr(f.recommendation)) errors.push(`${fat}.recommendation must be a non-empty, actionable string`);
            if (f.evidenceRefs != null && !(Array.isArray(f.evidenceRefs) && f.evidenceRefs.every((r) => typeof r === 'string'))) {
              errors.push(`${fat}.evidenceRefs must be an array of strings when present`);
            }
          });
        }
      }
    });
  }

  // QUOTA gate (spec §1.2 / §3.4): >=2 wins + >=1 fix per screen in scope.
  const needLike = 2 * nScreens;
  const needWish = 1 * nScreens;
  if (likeCount < needLike) errors.push(`quota: need >=${needLike} iLike wins (2/screen x ${nScreens}), got ${likeCount}`);
  if (wishCount < needWish) errors.push(`quota: need >=${needWish} iWish fixes (1/screen x ${nScreens}), got ${wishCount}`);

  return {
    valid: errors.length === 0,
    errors,
    id: typeof output.id === 'string' ? output.id : null,
    persona: typeof output.persona === 'string' ? output.persona : null,
  };
}

// ---------------------------------------------------------------------------
// 4. Synthesis — dedupe + rank + weighted composite over the persona verdicts
// ---------------------------------------------------------------------------

function normEvidence(s = '') {
  return String(s).toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 80);
}

function bandFromComposite(composite, criticalCount, minDim) {
  // Ship gate (spec §2.1): mean>=3 AND no dim<2 AND zero critical -> good.
  if (criticalCount >= 2) return 'poor';
  if (criticalCount >= 1) return composite >= 50 ? 'needs-work' : 'poor';
  if (composite >= 75 && minDim >= 2) return 'good';
  if (composite < 40) return 'poor';
  return 'needs-work';
}

/**
 * Synthesize the panel: merge the four persona verdicts into one ranked findings
 * list + a weighted composite (spec §2.4) with the critical-error override + cap
 * (spec §2.3). Pure aggregation of the personas' ordinal scores — NO measurement.
 *
 * @param {object[]} personaOutputs - validated persona critique objects
 * @param {object}   [opts.summary] - Track-A summary, carried through for context
 * @returns {object} a typed synthesis result (see SYNTHESIS_JSON_SCHEMA)
 */
export function synthesizePanel(personaOutputs = [], { auditId = null, summary = {}, runId = null } = {}) {
  const panel = personaOutputs.filter((p) => p && typeof p === 'object');

  // --- per-dimension score aggregation (a dim may be scored by several personas) ---
  const dimScores = {}; // dim -> { scores:[], criticals:[], confidences:[] }
  for (const p of panel) {
    for (const d of (p.dimensions || [])) {
      if (!DIMENSIONS.includes(d.dimension)) continue;
      const slot = (dimScores[d.dimension] ||= { scores: [], critical: false, byPersona: {} });
      if (typeof d.score === 'number') slot.scores.push(d.score);
      slot.byPersona[p.persona] = { score: d.score, confidence: d.confidence, critical: !!d.critical };
      if (d.critical === true) slot.critical = true;
    }
  }

  const dimensionScores = [];
  let weightedNum = 0;
  let weightTotal = 0;
  let criticalCount = 0;
  let minDim = 4;
  const means = [];
  for (const dim of DIMENSIONS) {
    const slot = dimScores[dim];
    if (!slot || slot.scores.length === 0) continue; // not-applicable: drop from composite
    const w = DIMENSION_META[dim].weight;
    const rawMean = slot.scores.reduce((a, b) => a + b, 0) / slot.scores.length;
    const score = slot.critical ? 0 : Math.round(rawMean);
    if (slot.critical) criticalCount += 1;
    weightedNum += w * score;
    weightTotal += w;
    means.push(score);
    minDim = Math.min(minDim, score);
    dimensionScores.push({
      dimension: dim, weight: w, score, rawMean: Number(rawMean.toFixed(2)),
      critical: slot.critical, byPersona: slot.byPersona,
    });
  }

  let composite = weightTotal > 0 ? Math.round((100 * weightedNum) / (4 * weightTotal)) : 0;
  // critical-error cap (spec §2.3): 1 critical -> <=60; 2+ -> poor (<=39).
  if (criticalCount >= 2) composite = Math.min(composite, 39);
  else if (criticalCount >= 1) composite = Math.min(composite, 60);
  const meanScore = means.length ? Number((means.reduce((a, b) => a + b, 0) / means.length).toFixed(2)) : 0;
  if (!means.length) minDim = 0;

  // --- dedupe + rank iWish findings across personas ---
  const fmap = new Map();
  for (const p of panel) {
    for (const d of (p.dimensions || [])) {
      for (const f of (d.iWish || [])) {
        const refKey = (Array.isArray(f.evidenceRefs) && f.evidenceRefs[0]) || normEvidence(f.evidence);
        const key = `${d.dimension}|${refKey}`;
        const cur = fmap.get(key);
        if (!cur) {
          fmap.set(key, {
            dimension: d.dimension, severity: f.severity, evidence: f.evidence,
            recommendation: f.recommendation, evidenceRefs: Array.isArray(f.evidenceRefs) ? [...f.evidenceRefs] : [],
            raisedBy: [p.persona], recommendations: [f.recommendation],
          });
        } else {
          if (rankSeverity(f.severity) > rankSeverity(cur.severity)) cur.severity = f.severity;
          if (!cur.raisedBy.includes(p.persona)) cur.raisedBy.push(p.persona);
          if (f.recommendation && !cur.recommendations.includes(f.recommendation)) cur.recommendations.push(f.recommendation);
          for (const r of (f.evidenceRefs || [])) if (!cur.evidenceRefs.includes(r)) cur.evidenceRefs.push(r);
        }
      }
    }
  }

  const findings = [...fmap.values()].map((f) => ({
    dimension: f.dimension, severity: f.severity, evidence: f.evidence,
    recommendation: f.recommendation, evidenceRefs: f.evidenceRefs,
    raisedBy: f.raisedBy, consensus: f.raisedBy.length,
  }));
  findings.sort((a, b) =>
    rankSeverity(b.severity) - rankSeverity(a.severity) ||
    b.consensus - a.consensus ||
    DIMENSION_META[b.dimension].weight - DIMENSION_META[a.dimension].weight ||
    a.dimension.localeCompare(b.dimension));
  const prioritizedFindings = findings.map((f, i) => ({ rank: i + 1, ...f }));

  // --- dedupe protected wins (iLike) + enumerated directions (whatIf) ---
  const winsSet = new Map();
  const dirSet = new Map();
  for (const p of panel) {
    for (const d of (p.dimensions || [])) {
      for (const w of (d.iLike || [])) {
        const k = normEvidence(w);
        const cur = winsSet.get(k);
        if (cur) { if (!cur.raisedBy.includes(p.persona)) cur.raisedBy.push(p.persona); }
        else winsSet.set(k, { dimension: d.dimension, win: w, raisedBy: [p.persona] });
      }
      for (const wi of (d.whatIf || [])) {
        const k = normEvidence(wi);
        if (!dirSet.has(k)) dirSet.set(k, { dimension: d.dimension, direction: wi, raisedBy: [p.persona] });
        else { const c = dirSet.get(k); if (!c.raisedBy.includes(p.persona)) c.raisedBy.push(p.persona); }
      }
    }
  }
  const protectedWins = [...winsSet.values()].sort((a, b) => b.raisedBy.length - a.raisedBy.length);
  const directions = [...dirSet.values()];

  const looksGood = bandFromComposite(composite, criticalCount, minDim);
  const counts = SEVERITIES.reduce((o, s) => (o[s] = findings.filter((f) => f.severity === s).length, o), {});

  return {
    id: `critique-panel-${runId || (auditId || 'run').replace(/^ui-audit-/, '') || 'run'}`,
    audit_id: auditId,
    generatedAt: new Date().toISOString(),
    personas: panel.map((p) => p.persona),
    verdict: {
      looksGood, composite, meanScore, criticalErrors: criticalCount,
      shipGate: looksGood === 'good' && criticalCount === 0,
      headline: synthHeadline(looksGood, criticalCount, prioritizedFindings),
    },
    dimensionScores,
    prioritizedFindings,
    severityCounts: counts,
    protectedWins,
    directions,
    decision: 'TRIAGE ONLY — the panel enumerates + ranks; the HUMAN decides direction at G4 (spec §3.2).',
    summary,
  };
}

function synthHeadline(looksGood, crit, ranked) {
  const top = ranked[0];
  const lead = top ? `Top fix: ${top.evidence}` : 'No defects raised by the panel.';
  if (crit >= 2) return `POOR — ${crit} critical errors. ${lead}`;
  if (crit >= 1) return `Capped at needs-work — 1 critical error. ${lead}`;
  return `${looksGood.toUpperCase()} — ${lead}`;
}

/** Validate a synthesis OUTPUT object (the marker-bearing artefact). */
export function validateSynthesis(output) {
  const errors = [];
  if (!output || typeof output !== 'object' || Array.isArray(output)) {
    return { valid: false, errors: ['synthesis must be a JSON object'], id: null };
  }
  if (!isNonEmptyStr(output.id) || !/^critique-panel-/.test(output.id)) errors.push("id must be 'critique-panel-<id>'");
  const v = output.verdict;
  if (!v || typeof v !== 'object') errors.push('verdict object required');
  else {
    if (!VERDICTS.includes(v.looksGood)) errors.push(`verdict.looksGood must be one of ${VERDICTS.join('|')}`);
    if (typeof v.composite !== 'number' || v.composite < 0 || v.composite > 100) errors.push('verdict.composite must be 0..100');
  }
  if (!Array.isArray(output.dimensionScores)) errors.push('dimensionScores must be an array');
  if (!Array.isArray(output.prioritizedFindings)) errors.push('prioritizedFindings must be an array');
  return { valid: errors.length === 0, errors, id: typeof output.id === 'string' ? output.id : null };
}

// ---------------------------------------------------------------------------
// JSON Schemas (draft-07) — mirrors of the validators, for docs/external tooling.
// `node critique_panel.mjs schema` writes these so they can't drift.
// ---------------------------------------------------------------------------

const iWishSchema = {
  type: 'object',
  required: ['severity', 'evidence', 'recommendation'],
  additionalProperties: true,
  properties: {
    severity: { enum: SEVERITIES },
    evidence: { type: 'string', minLength: 1 },
    evidenceRefs: { type: 'array', items: { type: 'string' } },
    recommendation: { type: 'string', minLength: 1 },
  },
};

export const PERSONA_JSON_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  $id: 'https://claude.skills/critique-panel/persona.schema.json',
  title: 'critique-panel persona verdict',
  type: 'object',
  required: ['id', 'persona', 'dimensions'],
  additionalProperties: true,
  properties: {
    id: { type: 'string', pattern: '^critique-panel-' },
    persona: { enum: PERSONA_IDS },
    audit_id: { type: 'string' },
    scope: { type: 'array', items: { type: 'string' } },
    dimensions: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['dimension', 'score', 'confidence'],
        properties: {
          dimension: { enum: DIMENSIONS },
          score: { type: 'integer', minimum: 0, maximum: 4 },
          confidence: { enum: CONFIDENCES },
          critical: { type: 'boolean' },
          iLike: { type: 'array', items: { type: 'string', minLength: 1 } },
          iWish: { type: 'array', items: iWishSchema },
          whatIf: { type: 'array', items: { type: 'string', minLength: 1 } },
        },
      },
    },
    notes: { type: 'string' },
  },
};

export const SYNTHESIS_JSON_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  $id: 'https://claude.skills/critique-panel/synthesis.schema.json',
  title: 'critique-panel synthesis',
  type: 'object',
  required: ['id', 'verdict', 'dimensionScores', 'prioritizedFindings'],
  additionalProperties: true,
  properties: {
    id: { type: 'string', pattern: '^critique-panel-' },
    audit_id: { type: ['string', 'null'] },
    personas: { type: 'array', items: { enum: PERSONA_IDS } },
    verdict: {
      type: 'object',
      required: ['looksGood', 'composite', 'meanScore', 'criticalErrors'],
      properties: {
        looksGood: { enum: VERDICTS },
        composite: { type: 'number', minimum: 0, maximum: 100 },
        meanScore: { type: 'number', minimum: 0, maximum: 4 },
        criticalErrors: { type: 'integer', minimum: 0 },
        shipGate: { type: 'boolean' },
        headline: { type: 'string' },
      },
    },
    dimensionScores: {
      type: 'array',
      items: {
        type: 'object',
        required: ['dimension', 'weight', 'score'],
        properties: {
          dimension: { enum: DIMENSIONS },
          weight: { type: 'number' },
          score: { type: 'integer', minimum: 0, maximum: 4 },
          rawMean: { type: 'number' },
          critical: { type: 'boolean' },
        },
      },
    },
    prioritizedFindings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['rank', 'dimension', 'severity', 'evidence', 'recommendation'],
        properties: {
          rank: { type: 'number' },
          dimension: { enum: DIMENSIONS },
          severity: { enum: SEVERITIES },
          evidence: { type: 'string', minLength: 1 },
          recommendation: { type: 'string', minLength: 1 },
          raisedBy: { type: 'array', items: { enum: PERSONA_IDS } },
          consensus: { type: 'number' },
        },
      },
    },
    protectedWins: { type: 'array' },
    directions: { type: 'array' },
  },
};
