#!/usr/bin/env node
/**
 * layout_lint.mjs — deterministic design heuristics over a capture bundle.
 *
 * CLI usage:
 *   node layout_lint.mjs --bundle ./out/home.bundle.json [--out findings.json]
 *   node layout_lint.mjs --bundle-dir ./out [--out findings.json]
 *
 * Programmatic usage (importable):
 *   import { lintBundle } from './layout_lint.mjs';
 *   const findings = lintBundle(bundle);   // pure sync — no browser needed
 *
 * Bundle shape (produced by capture.mjs):
 *   { screen, url, elements: [{ selector, tagName, textContent, isInteractive, styles }] }
 *   styles includes: marginTop/Bottom/Left/Right, paddingTop/Bottom/Left/Right,
 *     gap, rowGap, columnGap, fontSize, fontWeight, lineHeight, color, backgroundColor,
 *     width, height, and _rect: { width, height, x, y } (bounding box from getBoundingClientRect).
 */

import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { parseArgs } from 'node:util';
import { fileURLToPath } from 'node:url';
import { realpathSync } from 'node:fs';

// ---------------------------------------------------------------------------
// Color utilities (exported for unit tests)
// ---------------------------------------------------------------------------

/**
 * Parse a CSS rgb/rgba color string → {r, g, b} integers [0..255], or null.
 */
export function parseRgb(cssColor) {
  if (!cssColor) return null;
  const m = cssColor.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if (!m) return null;
  return { r: parseInt(m[1], 10), g: parseInt(m[2], 10), b: parseInt(m[3], 10) };
}

/**
 * Extract alpha channel from rgba().  Returns 1 if color is opaque or rgb().
 */
export function parseAlpha(cssColor) {
  if (!cssColor) return 1;
  const m = cssColor.match(/rgba\(.*?,\s*([\d.]+)\s*\)/);
  return m ? parseFloat(m[1]) : 1;
}

/**
 * WCAG relative luminance of an sRGB triplet.
 */
export function relLuminance(r, g, b) {
  const lin = (c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/**
 * WCAG contrast ratio between two sRGB colors.
 * Returns a value in [1, 21].
 */
export function contrastRatio(c1, c2) {
  const l1 = relLuminance(c1.r, c1.g, c1.b);
  const l2 = relLuminance(c2.r, c2.g, c2.b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// ---------------------------------------------------------------------------
// Spacing utilities (exported for unit tests)
// ---------------------------------------------------------------------------

/**
 * Parse a CSS px value → number or null.
 * Returns null for 'auto', 'normal', non-px values.
 */
export function parsePx(cssVal) {
  if (!cssVal || cssVal === 'auto' || cssVal === 'normal') return null;
  const m = String(cssVal).match(/^([\d.]+)px$/);
  return m ? parseFloat(m[1]) : null;
}

/**
 * Parse a CSS time value → milliseconds. Handles `0s`, `300ms`, `0.3s`, and
 * comma-lists (`0.2s, 0.4s` → the MAX, the slowest leg the user waits on).
 * Returns 0 for none/empty. Used by the Track-A motion collector.
 */
export function parseDurationMs(cssVal) {
  if (!cssVal || cssVal === 'none' || cssVal === 'normal') return 0;
  const parts = String(cssVal).split(',').map(s => s.trim()).filter(Boolean);
  let max = 0;
  for (const p of parts) {
    const m = p.match(/^([\d.]+)(ms|s)$/);
    if (!m) continue;
    const ms = m[2] === 's' ? parseFloat(m[1]) * 1000 : parseFloat(m[1]);
    if (ms > max) max = ms;
  }
  return max;
}

/**
 * Classify a motion duration against the SOTA 200-500ms band (DESIGN-EVAL v1 #9).
 * 0 = no motion (fine). A nonzero duration that is too fast (<100ms, perceived as a
 * jump) or too slow (>500ms, perceived as sluggish) is flagged.
 * @returns {null | { ms:number, band:'too-fast'|'too-slow' }}
 */
export function classifyMotion(ms) {
  if (!ms || ms <= 0) return null;
  if (ms < 100) return { ms, band: 'too-fast' };
  if (ms > 500) return { ms, band: 'too-slow' };
  return null;
}

/**
 * True if px is 0 or an integer multiple of `grid` (within 0.5px tolerance).
 */
export function isOnGrid(px, grid = 4) {
  if (px === 0) return true;
  return Math.abs(px % grid) < 0.5 || Math.abs(px % grid - grid) < 0.5;
}

/**
 * Classify an off-grid spacing value (BUG 2 — Tailwind/headless sub-pixel noise).
 *
 * Headless Chromium renders fractional-utility spacing (py-2.5, text-sm
 * line-heights, rem→px conversions) as sub-pixel values (10.5px, 22.5px,
 * 13.333px) that are NOT authored errors. We therefore:
 *   - treat anything within 0.5px of a 4px multiple as on-grid (returns null);
 *   - classify clearly off-grid INTEGERS (13px, 10px, 30px) as confidence 'high'
 *     (a real authored decision worth surfacing);
 *   - classify off-grid SUB-PIXEL values as confidence 'low' (computed artifact).
 *
 * @returns {null | { rounded:number, confidence:'high'|'low' }}
 */
export function classifySpacing(rawPx, grid = 4) {
  if (rawPx === null || rawPx === undefined || rawPx <= 0) return null;
  if (isOnGrid(rawPx, grid)) return null;                 // within 0.5px of a multiple → fine
  const rounded = Math.round(rawPx * 2) / 2;              // display value, nearest 0.5px
  const nearestInt = Math.round(rawPx);
  const isInteger = Math.abs(rawPx - nearestInt) < 0.1;   // 10.0 vs 10.5 / 13.333
  return { rounded, confidence: isInteger ? 'high' : 'low' };
}

/**
 * Heuristic: is a spacing property explicitly authored via the element's inline
 * style? Authored values are real decisions even when sub-pixel, so they keep
 * 'high' confidence. `inlineStyle` is the element's raw `style` attribute string
 * (captured by capture.mjs); absent on older bundles → returns false.
 */
export function isAuthoredSpacing(inlineStyle, prop) {
  if (!inlineStyle || typeof inlineStyle !== 'string') return false;
  const s = inlineStyle.toLowerCase();
  const kebab = prop.replace(/[A-Z]/g, m => '-' + m.toLowerCase());   // marginTop → margin-top
  if (s.includes(kebab)) return true;
  const base = kebab.startsWith('margin') ? 'margin'
    : kebab.startsWith('padding') ? 'padding'
    : kebab.includes('gap') ? 'gap'
    : kebab;
  // nosemgrep: javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp -- regex built from an internal allow-list (margin/padding/gap), not untrusted input
  return new RegExp('(^|;|\\s)' + base + '\\s*:').test(s);            // shorthand (margin:/padding:/gap:)
}

// ---------------------------------------------------------------------------
// Core lint logic
// ---------------------------------------------------------------------------

const SPACING_PROPS = [
  'marginTop', 'marginBottom', 'marginLeft', 'marginRight',
  'paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
  'gap', 'rowGap', 'columnGap',
];

const INTERACTIVE_TAGS = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']);

/**
 * Lint a single bundle (screen evidence) and return typed findings[].
 *
 * Each finding: { id, severity, rule, selector, property?, value, screen, message,
 *                 confidence?, rounded? }
 * severity: 'error' | 'warning' | 'info'
 *
 * @param {object} bundle
 * @param {object} [opts]
 * @param {boolean} [opts.includeLowConfidence=false] - also emit low-confidence
 *        (sub-pixel) off-scale-spacing findings. Off by default to drastically cut
 *        Tailwind/headless fractional-spacing noise.
 */
export function lintBundle(bundle, opts = {}) {
  const { includeLowConfidence = false } = opts;
  const findings = [];
  let idCounter = 0;
  const nextId = (prefix) => `${prefix}-${idCounter++}`;

  const { screen = 'unknown', elements = [] } = bundle;

  // Accumulators for post-scan checks
  const typeTriples = new Set();
  const greyColors = [];
  let pageHasMotion = false;                 // any nonzero transition/animation duration
  let interactiveNoFocusOutline = 0;         // interactive els that suppress the focus outline

  for (const el of elements) {
    const { selector = '?', tagName = '', styles = {}, isInteractive = false, textContent = '', inlineStyle = '' } = el;

    // --- 1. Off-scale spacing (confidence-graded; sub-pixel noise suppressed) ---
    for (const prop of SPACING_PROPS) {
      const raw = styles[prop];
      const cls = classifySpacing(parsePx(raw), 4);
      if (!cls) continue;

      // Authored (inline-style) values are real decisions even when sub-pixel.
      let confidence = cls.confidence;
      if (confidence === 'low' && isAuthoredSpacing(inlineStyle, prop)) confidence = 'high';

      if (confidence === 'low' && !includeLowConfidence) continue;   // drop computed sub-pixel noise

      findings.push({
        id: nextId('spacing'),
        severity: confidence === 'high' ? 'warning' : 'info',
        rule: 'off-scale-spacing',
        selector,
        property: prop,
        value: raw,
        rounded: cls.rounded,
        confidence,
        screen,
        message: `${selector} ${prop}: ${raw} is not on a 4px grid` +
          (confidence === 'low' ? ' (sub-pixel — low confidence)' : ''),
      });
    }

    // --- 2. Type-scale triple collection ---
    if (styles.fontSize && styles.fontWeight) {
      typeTriples.add(`${styles.fontSize}|${styles.fontWeight}|${styles.lineHeight || 'normal'}`);
    }

    // --- 3. WCAG contrast (text-bearing elements only) ---
    const hasText = textContent && textContent.trim().length > 0;
    if (hasText && styles.color && styles.backgroundColor) {
      const fg = parseRgb(styles.color);
      const bg = parseRgb(styles.backgroundColor);
      const bgAlpha = parseAlpha(styles.backgroundColor);

      if (fg && bg && bgAlpha > 0.1) {
        const ratio = contrastRatio(fg, bg);
        if (ratio < 4.5) {
          findings.push({
            id: nextId('contrast'),
            severity: 'error',
            rule: 'wcag-contrast',
            selector,
            value: ratio.toFixed(2) + ':1',
            screen,
            message: `${selector} contrast ${ratio.toFixed(2)}:1 < 4.5:1 (WCAG AA). fg=${styles.color} bg=${styles.backgroundColor}`,
          });
        }
      }
    }

    // --- 4. Tap targets ---
    const rect = styles._rect || {};
    const elW = typeof rect.width === 'number' ? rect.width : parsePx(styles.width);
    const elH = typeof rect.height === 'number' ? rect.height : parsePx(styles.height);
    const isClickable = isInteractive || INTERACTIVE_TAGS.has(tagName?.toUpperCase?.());

    if (isClickable && elW !== null && elH !== null && (elW < 44 || elH < 44)) {
      findings.push({
        id: nextId('tap'),
        severity: 'warning',
        rule: 'tap-target',
        selector,
        value: `${elW}×${elH}`,
        screen,
        message: `${selector} is ${elW}×${elH}px — below 44×44px minimum tap target`,
      });
    }

    // --- 5. Grey color collection (for sprawl check) ---
    if (styles.color) {
      const c = parseRgb(styles.color);
      if (c) {
        const chroma = Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b);
        if (chroma < 20) greyColors.push({ selector, cssColor: styles.color, c });
      }
    }

    // --- 6. Motion duration (per-element; motion dimension) ---
    const durMs = Math.max(parseDurationMs(styles.transitionDuration), parseDurationMs(styles.animationDuration));
    if (durMs > 0) pageHasMotion = true;
    const motionCls = classifyMotion(durMs);
    if (motionCls) {
      findings.push({
        id: nextId('motion'),
        severity: 'info',
        rule: 'motion-duration',
        selector,
        value: `${motionCls.ms}ms`,
        screen,
        message: `${selector} animation/transition ${motionCls.ms}ms is ${motionCls.band} (outside the 200-500ms band)`,
      });
    }

    // --- 7. Focus-visible signifier (affordance dimension) ---
    if (isInteractive || INTERACTIVE_TAGS.has(tagName?.toUpperCase?.())) {
      const outlineOff = styles.outlineStyle === 'none' ||
        (parsePx(styles.outlineWidth) === 0 && styles.outlineStyle !== 'auto');
      if (outlineOff) interactiveNoFocusOutline++;
    }
  }

  // --- Post-scan: type-scale sprawl ---
  if (typeTriples.size > 6) {
    findings.push({
      id: nextId('typescale'),
      severity: 'warning',
      rule: 'type-scale-sprawl',
      selector: 'document',
      value: `${typeTriples.size} triples`,
      screen,
      message: `${typeTriples.size} distinct (fontSize/fontWeight/lineHeight) triples found (> 6 recommended max)`,
    });
  }

  // --- Post-scan: near-duplicate greys ---
  let greyDupCount = 0;
  for (let i = 0; i < greyColors.length; i++) {
    for (let j = i + 1; j < greyColors.length; j++) {
      const a = greyColors[i].c;
      const b = greyColors[j].c;
      if (a.r === b.r && a.g === b.g && a.b === b.b) continue; // exact dupe, not near
      const dist = Math.sqrt((a.r - b.r) ** 2 + (a.g - b.g) ** 2 + (a.b - b.b) ** 2);
      if (dist < 20) greyDupCount++;
    }
  }
  if (greyDupCount > 3) {
    findings.push({
      id: nextId('color'),
      severity: 'warning',
      rule: 'color-inventory-sprawl',
      selector: 'document',
      value: `${greyDupCount} near-dup grey pairs`,
      screen,
      message: `${greyDupCount} near-duplicate grey color pairs — consolidate to design tokens`,
    });
  }

  // --- Post-scan: page-level motion + affordance signals (from capture's pageSignals) ---
  const sig = bundle.pageSignals || {};

  // reduced-motion (motion): the page animates but ships no prefers-reduced-motion
  // escape hatch. Critical-error trigger for the motion dimension (no reduced-motion escape).
  if (pageHasMotion && sig.hasReducedMotionRule === false) {
    findings.push({
      id: nextId('motion'),
      severity: 'error',
      rule: 'reduced-motion',
      selector: 'document',
      value: 'no prefers-reduced-motion rule',
      screen,
      message: 'page uses animation/transition but defines no prefers-reduced-motion media rule (no reduced-motion escape)',
    });
  }

  // missing-focus-visible (affordance): interactive controls suppress the focus
  // outline and the page defines no :focus-visible rule → no keyboard-focus signifier.
  if (interactiveNoFocusOutline > 0 && sig.hasFocusVisibleRule === false) {
    findings.push({
      id: nextId('focus'),
      severity: 'warning',
      rule: 'missing-focus-visible',
      selector: 'document',
      value: `${interactiveNoFocusOutline} control(s) with outline:none`,
      screen,
      message: `${interactiveNoFocusOutline} interactive control(s) suppress the focus outline and the page has no :focus-visible rule — keyboard focus has no signifier`,
    });
  }

  return findings;
}

// ---------------------------------------------------------------------------
// CLI entrypoint
// ---------------------------------------------------------------------------

async function main() {
  const { values } = parseArgs({
    options: {
      bundle: { type: 'string' },
      'bundle-dir': { type: 'string' },
      out: { type: 'string' },
      'include-low-confidence': { type: 'boolean', default: false },
    },
    strict: false,
  });

  const lintOpts = { includeLowConfidence: !!values['include-low-confidence'] };
  let bundles = [];

  if (values.bundle) {
    bundles.push(JSON.parse(readFileSync(resolve(values.bundle), 'utf8')));
  } else if (values['bundle-dir']) {
    const dir = resolve(values['bundle-dir']);
    for (const f of readdirSync(dir).filter(f => f.endsWith('.bundle.json'))) {
      bundles.push(JSON.parse(readFileSync(join(dir, f), 'utf8')));
    }
  } else {
    console.error('[layout_lint] ERROR: provide --bundle <path> or --bundle-dir <dir>');
    process.exit(1);
  }

  const allFindings = [];
  for (const bundle of bundles) {
    allFindings.push(...lintBundle(bundle, lintOpts));
  }

  const output = { findings: allFindings, count: allFindings.length };
  if (values.out) {
    writeFileSync(resolve(values.out), JSON.stringify(output, null, 2));
    console.log(`[layout_lint] wrote ${allFindings.length} findings → ${values.out}`);
  }

  for (const f of allFindings) {
    const tag = f.severity === 'error' ? 'ERR ' : f.severity === 'info' ? 'INFO' : 'WARN';
    console.log(`[${tag}] ${f.rule}: ${f.message}`);
  }
  console.log(`\nTotal: ${allFindings.length} finding(s)`);
  if (!lintOpts.includeLowConfidence) {
    console.log('(low-confidence sub-pixel spacing suppressed — pass --include-low-confidence to include)');
  }
  console.log('SUCCESS:layout-lint');
}

// Run if this is the entry point
const __filename = fileURLToPath(import.meta.url);
// Junction/symlink-safe main-module check. `~/.claude/skills` is a junction to
// `skills.daily`; Node resolves symlinks for ESM so import.meta.url reports the REAL
// path while resolve(argv[1]) stays lexical. A lexical compare therefore NEVER matched
// on the documented `~/.claude/skills/...` invocation and main() silently never ran
// (exit 0, no output, no artifacts). realpathSync.native also collapses 8.3 short
// names (PREKZU~1), which realpathSync does not.
const __isMain = (a, b) => {
  try { return realpathSync.native(a) === realpathSync.native(b); }
  catch { return resolve(a) === resolve(b); }
};
if (process.argv[1] && __isMain(process.argv[1], __filename)) {
  main().catch(err => {
    console.error(`FAILED:layout-lint ${err.message}`);
    process.exit(1);
  });
}
