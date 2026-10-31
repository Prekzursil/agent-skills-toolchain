/**
 * critique_schema.mjs — Track-B (design critique) schema + assembly core.
 *
 * PURE module (no I/O, no browser, no LLM). It does three deterministic jobs so
 * that Claude (the orchestrator) only ever has to REASON, never measure:
 *
 *   1. projectFindingsByDimension(audit) — route Track-A's pre-computed numbers
 *      (run_audit.mjs `audit.json`) onto the eight design dimensions, so every
 *      quantitative claim the critic makes is already grounded + traceable.
 *   2. assembleCritiqueInput(...) / renderPromptMarkdown(...) — marshal the numbers
 *      + the rubric + the screenshot path(s) + the output contract into ONE input
 *      package for the critic to fill in. (It never calls a model.)
 *   3. validateCritique(output) — type-check the verdict Claude produces against the
 *      OUTPUT schema, returning every violation (terminal-state gate).
 *
 * HARD ARCHITECTURE RULE (planner-safe): this file deliberately contains NO pixel
 * math, geometry estimation, or coordinate guessing. Deterministic measurement is
 * Track-A's job (layout_lint/capture); holistic judgment is Claude's. This module is
 * only the contract + the wiring between them.
 */

// ---------------------------------------------------------------------------
// Vocabulary (single source of truth — JSON schema + validator both read these)
// ---------------------------------------------------------------------------

/**
 * DESIGN-EVAL v1 — the nine *scoring* dimensions (each scored 0-4, weighted).
 * Spec: DESIGN-SKILLS-AND-EVAL.md §2.2. `affordance` (#8) and `motion` (#9) are
 * the v1 additions over the original seven.
 */
export const SCORING_DIMENSIONS = [
  'visual-hierarchy',   // does the eye land on the right thing first?
  'spacing-rhythm',     // consistent spacing scale / 4-8px grid, breathing room
  'alignment',          // shared edges/baselines, tidy gutters (screenshot-judged)
  'type-scale',         // limited, deliberate type ramp; clear heading/body split
  'color-contrast',     // palette harmony + WCAG legibility (highest weight)
  'consistency',        // same components/spacing/type across screens
  'empty-error-states', // quality of empty/loading/error/blank-render states
  'affordance',         // signifiers + feedback: tap-targets, dead buttons, focus-visible
  'motion',             // duration band, fps/jank, prefers-reduced-motion honored
];

/**
 * The full dimension enum the critic may emit: the nine scoring dimensions plus
 * `overall` (the holistic verdict line — NOT itself weighted into the composite).
 */
export const DIMENSIONS = [...SCORING_DIMENSIONS, 'overall'];

/**
 * Per-dimension weights for the §2.4 weighted composite. color-contrast carries
 * the highest weight (2.0) because a contrast failure is the least subjective and
 * most legally load-bearing defect; alignment/motion the lowest (0.75).
 * `overall` is intentionally absent (it is the output, not an input).
 */
export const DIMENSION_WEIGHTS = {
  'visual-hierarchy': 1.5,
  'spacing-rhythm': 1.0,
  'alignment': 0.75,
  'type-scale': 1.0,
  'color-contrast': 2.0,
  'consistency': 1.0,
  'empty-error-states': 1.5,
  'affordance': 1.5,
  'motion': 0.75,
};

/** Ordinal score scale every dimension is graded on (§2.1). 0 = critical/fail … 4 = excellent. */
export const MIN_DIM_SCORE = 0;
export const MAX_DIM_SCORE = 4;
/** verdict.score must equal the harness-computed capped composite within this tolerance. */
export const COMPOSITE_TOLERANCE = 2;

/** Finding severities, most → least urgent (drives prioritisation). Maps to Nielsen 0-4. */
export const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'];

/** Overall "does it look good" verdict buckets. */
export const VERDICTS = ['good', 'needs-work', 'poor'];

/** Per-dimension ratings. */
export const RATINGS = ['pass', 'warn', 'fail'];

/** How sure the critic is — `low` when judging a blank/uncertain render. */
export const CONFIDENCES = ['high', 'medium', 'low'];

const _SEV_RANK = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
/** Numeric rank for a severity (higher = more urgent). Unknown → 0. */
export function rankSeverity(sev) {
  return _SEV_RANK[sev] || 0;
}

const _round2 = (n) => Math.round(n * 100) / 100;

// ---------------------------------------------------------------------------
// DESIGN-EVAL v1 scoring — weighted composite + critical-error override (§2.3/§2.4)
// ---------------------------------------------------------------------------

/** True if a dimension tripped a critical-error condition (any critical finding or an explicit flag). */
export function isCriticalDimension(dim) {
  if (!dim || typeof dim !== 'object') return false;
  if (dim.criticalError === true) return true;
  return Array.isArray(dim.findings) && dim.findings.some(f => f && f.severity === 'critical');
}

/** How many scoring dimensions tripped a critical-error condition. */
export function countCriticalDimensions(dimensions = []) {
  return (dimensions || []).filter(d => SCORING_DIMENSIONS.includes(d?.dimension) && isCriticalDimension(d)).length;
}

/**
 * §2.4 weighted composite (headline 0-100) over the scoring dimensions that carry
 * a numeric score: `100 * Σ(wᵢ·scoreᵢ) / (4·Σwᵢ)`. Returns null if nothing scored.
 */
export function computeComposite(dimensions = []) {
  let num = 0, den = 0;
  for (const d of (dimensions || [])) {
    if (!SCORING_DIMENSIONS.includes(d?.dimension) || typeof d.score !== 'number') continue;
    const w = DIMENSION_WEIGHTS[d.dimension] ?? 1;
    num += w * d.score;
    den += w;
  }
  if (den === 0) return null;
  return (100 * num) / (4 * den);
}

/**
 * §2.3 critical-error override cap: 1 critical → overall capped at needs-work (≤60);
 * ≥2 critical → poor (≤39). The same condition also zeroes the dimension's score so
 * the composite can't average a catastrophe away (enforced in validateCritique).
 */
export function applyCriticalCap(composite, criticalCount) {
  if (composite == null) return composite;
  if (criticalCount >= 2) return Math.min(composite, 39);
  if (criticalCount >= 1) return Math.min(composite, 60);
  return composite;
}

/**
 * Deterministically derive the whole verdict from the per-dimension scores — the
 * §2.4 composite + §2.3 cap + ship/reference gates (§2.1). The critic fills the
 * per-dimension scores; the HARNESS computes the headline (never free-hand).
 *
 * @returns {{ composite, score, capped, criticalCount, mean, minScore,
 *             shipGate, referenceGate, looksGood }}
 */
export function computeVerdict(dimensions = []) {
  const composite = computeComposite(dimensions);
  const criticalCount = countCriticalDimensions(dimensions);
  const capped = applyCriticalCap(composite, criticalCount);
  const scored = (dimensions || []).filter(d => SCORING_DIMENSIONS.includes(d?.dimension) && typeof d.score === 'number');
  const mean = scored.length ? scored.reduce((a, d) => a + d.score, 0) / scored.length : null;
  const minScore = scored.length ? Math.min(...scored.map(d => d.score)) : null;
  const shipGate = composite != null && mean != null && mean >= 3.0 && minScore >= 2 && criticalCount === 0;
  const referenceGate = composite != null && mean != null && mean >= 3.5 && minScore >= 3 && criticalCount === 0;

  // looksGood bucket: good needs a healthy composite with no dimension below 2 and
  // no criticals; poor is a capped catastrophe (<40); everything else is needs-work.
  let looksGood = 'needs-work';
  if (capped != null) {
    if (capped >= 75 && minScore != null && minScore >= 2 && criticalCount === 0) looksGood = 'good';
    else if (capped < 40) looksGood = 'poor';
  }

  return {
    composite: composite == null ? null : _round2(composite),
    score: capped == null ? null : Math.round(capped),
    capped: capped == null ? null : _round2(capped),
    criticalCount,
    mean: mean == null ? null : _round2(mean),
    minScore,
    shipGate,
    referenceGate,
    looksGood,
  };
}

// ---------------------------------------------------------------------------
// 1. Evidence routing — Track-A rule/signal -> design dimension
// ---------------------------------------------------------------------------

/**
 * Which dimension a layout-lint rule belongs to (DESIGN-EVAL v1 §2.2).
 * tap-target now feeds **affordance** (signifier/feedback), not visual-hierarchy;
 * motion-duration / reduced-motion feed **motion**; missing-focus-visible →
 * **affordance**.
 */
const RULE_TO_DIMENSION = {
  'off-scale-spacing': 'spacing-rhythm',
  'wcag-contrast': 'color-contrast',
  'color-inventory-sprawl': 'color-contrast',
  'type-scale-sprawl': 'type-scale',
  'tap-target': 'affordance',
  'missing-focus-visible': 'affordance',
  'motion-duration': 'motion',
  'reduced-motion': 'motion',
};

/** Classify an axe rule id onto a dimension (best-effort, nothing dropped). */
function axeDimension(id = '') {
  if (/contrast/i.test(id)) return 'color-contrast';
  if (/focus|keyboard|tabindex|target-size|interactive/i.test(id)) return 'affordance';
  if (/motion|animation|reduced/i.test(id)) return 'motion';
  if (/heading|landmark|region|list|structure|order|skip-link|bypass/i.test(id)) return 'visual-hierarchy';
  return 'overall';
}

/**
 * Project a Track-A audit.json onto the eight dimensions.
 * Returns { [dimension]: Evidence[] } for every dimension (empty arrays allowed).
 *
 * Evidence = { ref, gate, rule, screen, value, severity, source, detail }
 * Every item is traceable back to a Track-A finding id / signal.
 */
export function projectFindingsByDimension(audit = {}) {
  const out = {};
  for (const d of DIMENSIONS) out[d] = [];
  const push = (dim, ev) => { if (out[dim]) out[dim].push(ev); };

  // --- merged layout-lint + dead-button findings ---
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
    // dead-button crawl findings carry `effect`, not `rule`. A control with no
    // observable effect is an AFFORDANCE failure (no feedback to the user).
    if (f.effect === 'none' || f.effect === 'error') {
      push('affordance', {
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

  // --- axe accessibility violations ---
  for (const a of (audit.axe || [])) {
    push(axeDimension(a.id), {
      ref: a.id || 'axe', gate: 'axe', rule: a.id || 'axe', screen: a.screen || 'unknown',
      value: `${a.nodes ?? 0} node(s)`, severity: a.impact || 'moderate', source: 'axe',
      detail: a.description || '',
    });
  }

  // --- uncaught page errors (render/crash) ---
  for (const e of (audit.pageErrors || [])) {
    push('empty-error-states', {
      ref: `pageerror-${e.screen || 'unknown'}`, gate: 'capture', rule: 'page-error',
      screen: e.screen || 'unknown', value: e.name || 'Error', severity: 'critical',
      source: 'pageError', detail: e.message || '',
    });
  }

  // --- visual regressions (>5% drift) -> cross-screen consistency ---
  for (const v of (audit.visual || [])) {
    if ((v.percentDiff || 0) > 5) {
      push('consistency', {
        ref: `visual-${v.screen || 'unknown'}`, gate: 'visual-diff', rule: 'visual-regression',
        screen: v.screen || 'unknown', value: `${v.percentDiff}%`, severity: 'medium',
        source: 'visual-diff', detail: `screen drifted ${v.percentDiff}% from baseline`,
      });
    }
  }

  // --- holistic totals for the overall judgment ---
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
// 2. Assemble the critique INPUT (the structured prompt the orchestrator fills)
// ---------------------------------------------------------------------------

const INSTRUCTIONS = [
  'You are the critic. REASON over the pre-computed Track-A numbers (evidenceByDimension + summary) together with the screenshot(s) — output a structured design verdict on the DESIGN-EVAL v1 rubric.',
  'NEVER pixel-measure, estimate coordinates, or invent geometry: deterministic measurement is Track-A\'s job. Use the supplied numbers as your only quantitative evidence (cite them by ref).',
  'VIEW every screenshot listed in `screenshots` and judge the rendered result perceptually: hierarchy, balance, alignment, type rhythm, colour harmony, affordance, motion, polish.',
  'Score EACH of the nine scoring dimensions 0-4 (0=critical/fail … 4=excellent — see the rubric anchors). Also give a `rating` (pass/warn/fail) + a `confidence`. For dimensions with no deterministic signal (e.g. alignment) judge perceptually from the screenshot and lower the confidence.',
  'CRITICAL-ERROR OVERRIDE (§2.3): if a dimension trips its critical-error condition (e.g. any body text < 4.5:1; render crash/blank; dead primary action with no feedback; motion with no reduced-motion escape) you MUST set that dimension\'s `score` to 0 and add a `critical` finding. One critical caps the verdict at needs-work; two or more → poor.',
  'RELIABILITY (§2.5): assess ONE dimension per reasoning pass to avoid the halo effect; lean on the deterministic Track-A numbers as the spine; on purely perceptual dimensions run it twice and keep the lower score if they disagree. Use the few-shot anchors in the rubric to calibrate.',
  'Do NOT free-hand `verdict.score`: it is the §2.4 weighted composite of the per-dimension scores (color-contrast weight 2.0 is highest), then the §2.3 cap. Run `node critique.mjs compute --input <file>` to fill it deterministically, or match computeVerdict() exactly.',
  'Every finding needs grounded `evidence` (a number-by-ref or an explicit visual observation) and an actionable `recommendation`. Flatten the most important findings into `prioritizedFindings`, ranked by severity.',
  'Emit ONLY JSON conforming to `outputSchema`. Then gate it: `node critique.mjs validate --input <file>` must print SUCCESS before you call the critique done.',
];

/**
 * Build the critique INPUT package from Track-A artefacts.
 * @param {object}        args.audit        - parsed Track-A audit.json
 * @param {string|string[]} args.screenshots - screenshot path(s) the critic must view
 * @param {string}        [args.rubricText] - the rubric doc text (embedded verbatim)
 * @param {object|null}   [args.uiclip]     - optional UIClip numeric prior
 */
export function assembleCritiqueInput({ audit = {}, screenshots = [], rubricText = '', uiclip = null, focusDimension = null } = {}) {
  const shots = Array.isArray(screenshots) ? screenshots.filter(Boolean) : (screenshots ? [screenshots] : []);
  const focus = focusDimension && DIMENSIONS.includes(focusDimension) ? focusDimension : null;
  return {
    task: 'design-critique',
    goal: 'Produce a structured DESIGN-EVAL v1 verdict — score each of nine dimensions 0-4 (visual hierarchy, spacing rhythm, alignment, type scale, colour/contrast, cross-screen consistency, empty/error states, affordance, motion), apply the critical-error override, and report the weighted composite with prioritised, actionable findings.',
    audit_id: audit.id || null,
    generatedAt: new Date().toISOString(),
    summary: audit.summary || {},
    screenshots: shots,
    rubric: rubricText || '',
    uiclip: uiclip ?? null,
    evidenceByDimension: projectFindingsByDimension(audit),
    dimensions: DIMENSIONS,
    scoringDimensions: SCORING_DIMENSIONS,
    dimensionWeights: DIMENSION_WEIGHTS,
    scoreScale: { min: MIN_DIM_SCORE, max: MAX_DIM_SCORE, note: '0=critical/fail, 1=poor, 2=needs-work, 3=good, 4=excellent (ship gate: mean>=3 AND no dim<2 AND zero critical)' },
    focusDimension: focus,                         // set for one-dimension-per-call (§2.5 reliability)
    severities: SEVERITIES,
    verdicts: VERDICTS,
    ratings: RATINGS,
    confidences: CONFIDENCES,
    instructions: INSTRUCTIONS,
    outputSchema: CRITIQUE_JSON_SCHEMA,
  };
}

/**
 * Render the assembled input as a Markdown brief the orchestrator can read
 * alongside the screenshot, with a fill-in JSON skeleton.
 */
export function renderPromptMarkdown(input) {
  const idHint = (input.audit_id || 'ui-audit-run').replace(/^ui-audit-/, '') || 'run';
  const focus = input.focusDimension || null;
  const dimsToShow = focus ? input.dimensions.filter(d => d === focus) : input.dimensions;
  const L = [];
  L.push(focus ? `# Track-B design critique — single dimension: \`${focus}\`` : '# Track-B design critique');
  L.push('');
  L.push(`**Goal.** ${input.goal}`);
  L.push('');
  if (focus) {
    L.push(`**Reliability mode (§2.5).** Assess ONLY \`${focus}\` this pass (one dimension per call kills the halo effect). Weight \`${(input.dimensionWeights || {})[focus] ?? 'n/a'}\`. Emit a single \`dimensions[]\` entry; merge it with the other dimension passes before computing the verdict.`);
    L.push('');
  }
  L.push('## How to do this');
  for (const i of input.instructions) L.push(`- ${i}`);
  L.push('');
  L.push('## Scoring (DESIGN-EVAL v1)');
  L.push('- Every scoring dimension gets a `score` 0-4: **0**=critical/fail · **1**=poor · **2**=needs-work · **3**=good · **4**=excellent.');
  L.push('- **Critical-error override:** a tripped critical condition forces that dimension\'s `score` to **0** and adds a `critical` finding. 1 critical caps the verdict ≤60 (needs-work); ≥2 → poor (≤39).');
  L.push('- **Weighted composite** (the harness computes `verdict.score`, do not free-hand it): `100 * Σ(wᵢ·scoreᵢ) / (4·Σwᵢ)` then the cap. Weights:');
  L.push('  ```json');
  L.push('  ' + JSON.stringify(input.dimensionWeights || {}));
  L.push('  ```');
  L.push('');
  L.push('## Screenshots to view');
  if (input.screenshots.length === 0) L.push('- (none supplied — judge from numbers only, confidence low)');
  for (const s of input.screenshots) L.push(`- \`${s}\``);
  L.push('');
  if (input.uiclip && input.uiclip.score != null) {
    L.push(`**UIClip prior:** design-quality score \`${input.uiclip.score}\` (status: ${input.uiclip.status || 'ok'}). Treat as a weak prior, not ground truth.`);
    L.push('');
  }
  L.push(`## Track-A summary (\`${input.audit_id || 'n/a'}\`)`);
  L.push('```json');
  L.push(JSON.stringify(input.summary, null, 2));
  L.push('```');
  L.push('');
  L.push('## Pre-computed evidence, by dimension');
  for (const d of dimsToShow) {
    const ev = input.evidenceByDimension[d] || [];
    const w = (input.dimensionWeights || {})[d];
    L.push(`### ${d}${w != null ? ` (weight ${w})` : ''} — ${ev.length} signal(s)`);
    if (ev.length === 0) {
      L.push('- _no deterministic signal; judge perceptually from the screenshot._');
    } else {
      for (const e of ev) {
        L.push(`- \`${e.ref}\` [${e.source}/${e.rule}] (${e.severity}) ${e.screen}: ${e.value ?? ''} ${e.detail ? '— ' + e.detail : ''}`.trim());
      }
    }
    L.push('');
  }
  L.push('## Output — fill this verdict and validate it');
  L.push('Emit ONLY JSON matching `outputSchema`. Skeleton:');
  L.push('```json');
  L.push(JSON.stringify({
    id: `ui-critique-${idHint}`,
    audit_id: input.audit_id || 'ui-audit-<id>',
    verdict: { looksGood: 'good|needs-work|poor', score: '<harness-computed composite, see compute>', headline: '…', summary: '…' },
    dimensions: [
      { dimension: focus || '<one of scoringDimensions>', score: '0-4 (0 if a critical condition tripped)', rating: 'pass|warn|fail', confidence: 'high|medium|low',
        findings: [{ severity: 'critical|high|medium|low|info', evidence: 'grounded in a ref or a visual observation', evidenceRefs: ['<track-a id>'], recommendation: 'actionable fix' }] },
    ],
    prioritizedFindings: [
      { rank: 1, dimension: '<dimension>', severity: 'critical', evidence: '…', recommendation: '…' },
    ],
    uiclip: input.uiclip ?? null,
  }, null, 2));
  L.push('```');
  return L.join('\n');
}

// ---------------------------------------------------------------------------
// 3. Validate the OUTPUT verdict
// ---------------------------------------------------------------------------

const isNonEmptyStr = (v) => typeof v === 'string' && v.trim().length > 0;

/**
 * Validate a Track-B critique object against the OUTPUT schema.
 * Collects ALL violations (does not throw on the first).
 * @returns {{ valid: boolean, errors: string[], id: (string|null) }}
 */
export function validateCritique(output) {
  const errors = [];
  if (!output || typeof output !== 'object' || Array.isArray(output)) {
    return { valid: false, errors: ['critique must be a JSON object'], id: null };
  }

  if (!isNonEmptyStr(output.id) || !/^ui-critique-/.test(output.id)) {
    errors.push("id must be a non-empty string namespaced 'ui-critique-<id>'");
  }

  // verdict (shape) — the composite-consistency check runs after dimensions, below.
  const v = output.verdict;
  if (!v || typeof v !== 'object') {
    errors.push('verdict is required (object with looksGood/score/headline/summary)');
  } else {
    if (!VERDICTS.includes(v.looksGood)) errors.push(`verdict.looksGood must be one of ${VERDICTS.join('|')}`);
    if (typeof v.score !== 'number' || v.score < 0 || v.score > 100) errors.push('verdict.score must be a number in [0,100]');
    if (!isNonEmptyStr(v.headline)) errors.push('verdict.headline must be a non-empty string');
    if (!isNonEmptyStr(v.summary)) errors.push('verdict.summary must be a non-empty string');
  }

  // dimensions (validated before the verdict so the composite check can use them)
  if (!Array.isArray(output.dimensions) || output.dimensions.length === 0) {
    errors.push('dimensions must be a non-empty array (assess at least one dimension)');
  } else {
    output.dimensions.forEach((d, i) => {
      const at = `dimensions[${i}]`;
      if (!d || typeof d !== 'object') { errors.push(`${at} must be an object`); return; }
      if (!DIMENSIONS.includes(d.dimension)) errors.push(`${at}.dimension '${d.dimension}' is not a known dimension`);
      if (!RATINGS.includes(d.rating)) errors.push(`${at}.rating must be one of ${RATINGS.join('|')}`);
      if (!CONFIDENCES.includes(d.confidence)) errors.push(`${at}.confidence must be one of ${CONFIDENCES.join('|')}`);
      // DESIGN-EVAL v1: every SCORING dimension needs a numeric 0-4 score; `overall` may omit it.
      const isScoring = SCORING_DIMENSIONS.includes(d.dimension);
      if (isScoring) {
        if (typeof d.score !== 'number' || d.score < MIN_DIM_SCORE || d.score > MAX_DIM_SCORE) {
          errors.push(`${at}.score must be a number in [${MIN_DIM_SCORE},${MAX_DIM_SCORE}] for scoring dimension '${d.dimension}'`);
        } else if (isCriticalDimension(d) && d.score !== 0) {
          // §2.3 critical-error override: a tripped critical condition forces score 0.
          errors.push(`${at}.score must be 0 — '${d.dimension}' has a critical finding (critical-error override)`);
        }
      } else if (d.score != null && (typeof d.score !== 'number' || d.score < MIN_DIM_SCORE || d.score > MAX_DIM_SCORE)) {
        errors.push(`${at}.score, when present, must be a number in [${MIN_DIM_SCORE},${MAX_DIM_SCORE}]`);
      }
      if (!Array.isArray(d.findings)) { errors.push(`${at}.findings must be an array`); return; }
      d.findings.forEach((f, j) => {
        const fat = `${at}.findings[${j}]`;
        if (!f || typeof f !== 'object') { errors.push(`${fat} must be an object`); return; }
        if (!SEVERITIES.includes(f.severity)) errors.push(`${fat}.severity '${f.severity}' is not one of ${SEVERITIES.join('|')}`);
        if (!isNonEmptyStr(f.evidence)) errors.push(`${fat}.evidence must be a non-empty string (grounded in a number or a visual observation)`);
        if (!isNonEmptyStr(f.recommendation)) errors.push(`${fat}.recommendation must be a non-empty, actionable string`);
        if (f.evidenceRefs != null && !(Array.isArray(f.evidenceRefs) && f.evidenceRefs.every(r => typeof r === 'string'))) {
          errors.push(`${fat}.evidenceRefs must be an array of strings when present`);
        }
      });
    });

    // §2.4 composite consistency: verdict.score must equal the harness-computed
    // weighted composite (after the §2.3 cap), within COMPOSITE_TOLERANCE. This is
    // what stops the headline from being free-handed.
    if (v && typeof v.score === 'number') {
      const cv = computeVerdict(output.dimensions);
      if (cv.score != null) {
        if (Math.abs(v.score - cv.score) > COMPOSITE_TOLERANCE) {
          errors.push(`verdict.score ${v.score} != weighted composite ${cv.score} (±${COMPOSITE_TOLERANCE}); use computeVerdict / 'critique.mjs compute' — do not free-hand it`);
        }
        if (VERDICTS.includes(v.looksGood) && v.looksGood !== cv.looksGood) {
          errors.push(`verdict.looksGood '${v.looksGood}' != computed '${cv.looksGood}' (composite ${cv.score}, ${cv.criticalCount} critical dimension(s))`);
        }
      }
    }
  }

  // prioritizedFindings
  if (!Array.isArray(output.prioritizedFindings)) {
    errors.push('prioritizedFindings must be an array (the flattened, ranked action list)');
  } else {
    output.prioritizedFindings.forEach((p, i) => {
      const at = `prioritizedFindings[${i}]`;
      if (!p || typeof p !== 'object') { errors.push(`${at} must be an object`); return; }
      if (!DIMENSIONS.includes(p.dimension)) errors.push(`${at}.dimension '${p.dimension}' is not a known dimension`);
      if (!SEVERITIES.includes(p.severity)) errors.push(`${at}.severity '${p.severity}' invalid`);
      if (!isNonEmptyStr(p.evidence)) errors.push(`${at}.evidence required`);
      if (!isNonEmptyStr(p.recommendation)) errors.push(`${at}.recommendation required`);
    });
  }

  // uiclip (optional)
  if (output.uiclip != null) {
    const u = output.uiclip;
    if (typeof u !== 'object' || Array.isArray(u)) {
      errors.push('uiclip must be an object or null');
    } else {
      if (!(u.score === null || typeof u.score === 'number')) errors.push('uiclip.score must be a number or null');
      if (u.status != null && typeof u.status !== 'string') errors.push('uiclip.status must be a string when present');
    }
  }

  return { valid: errors.length === 0, errors, id: typeof output.id === 'string' ? output.id : null };
}

// ---------------------------------------------------------------------------
// JSON Schema (draft-07) — mirror of validateCritique, for docs/external tooling.
// `node critique.mjs schema` writes this to critique.schema.json so it can't drift.
// ---------------------------------------------------------------------------

const findingSchema = {
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

export const CRITIQUE_JSON_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  $id: 'https://claude.skills/ui-audit/critique.schema.json',
  title: 'ui-audit Track-B design critique',
  type: 'object',
  required: ['id', 'verdict', 'dimensions', 'prioritizedFindings'],
  additionalProperties: true,
  properties: {
    id: { type: 'string', pattern: '^ui-critique-' },
    audit_id: { type: 'string' },
    verdict: {
      type: 'object',
      required: ['looksGood', 'score', 'headline', 'summary'],
      properties: {
        looksGood: { enum: VERDICTS },
        score: { type: 'number', minimum: 0, maximum: 100 },
        headline: { type: 'string', minLength: 1 },
        summary: { type: 'string', minLength: 1 },
      },
    },
    dimensions: {
      type: 'array',
      minItems: 1,
      items: {
        type: 'object',
        required: ['dimension', 'rating', 'confidence', 'findings'],
        properties: {
          dimension: { enum: DIMENSIONS },
          // DESIGN-EVAL v1: 0-4 ordinal score (required for the 9 scoring dimensions;
          // the JS validator enforces presence + the critical-error override). 0=fail … 4=excellent.
          score: { type: 'number', minimum: MIN_DIM_SCORE, maximum: MAX_DIM_SCORE },
          criticalError: { type: 'boolean' },
          rating: { enum: RATINGS },
          confidence: { enum: CONFIDENCES },
          findings: { type: 'array', items: findingSchema },
        },
      },
    },
    prioritizedFindings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['dimension', 'severity', 'evidence', 'recommendation'],
        properties: {
          rank: { type: 'number' },
          dimension: { enum: DIMENSIONS },
          severity: { enum: SEVERITIES },
          evidence: { type: 'string', minLength: 1 },
          recommendation: { type: 'string', minLength: 1 },
        },
      },
    },
    uiclip: {
      oneOf: [
        { type: 'null' },
        { type: 'object', properties: { score: { type: ['number', 'null'] }, status: { type: 'string' } } },
      ],
    },
  },
};
