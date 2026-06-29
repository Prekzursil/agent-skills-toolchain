/**
 * layout_lint.test.mjs — unit tests for layout_lint pure functions.
 * No browser needed — all tests operate on hand-crafted bundle objects.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import {
  parsePx, isOnGrid, classifySpacing,
  parseRgb, parseAlpha, relLuminance, contrastRatio,
  lintBundle,
} from '../layout_lint.mjs';

// ---------------------------------------------------------------------------
// parsePx
// ---------------------------------------------------------------------------
describe('parsePx', () => {
  test('extracts positive integer pixel values', () => {
    assert.equal(parsePx('13px'), 13);
    assert.equal(parsePx('8px'), 8);
    assert.equal(parsePx('16px'), 16);
  });

  test('returns 0 for 0px', () => {
    assert.equal(parsePx('0px'), 0);
  });

  test('returns null for non-px / keyword values', () => {
    assert.equal(parsePx('auto'), null);
    assert.equal(parsePx('normal'), null);
    assert.equal(parsePx(null), null);
    assert.equal(parsePx(undefined), null);
    assert.equal(parsePx('50%'), null);
    assert.equal(parsePx('2em'), null);
  });
});

// ---------------------------------------------------------------------------
// isOnGrid
// ---------------------------------------------------------------------------
describe('isOnGrid', () => {
  test('accepts 0 (always on grid)', () => {
    assert.equal(isOnGrid(0, 4), true);
  });

  test('accepts exact multiples of 4', () => {
    for (const px of [4, 8, 12, 16, 24, 32, 48]) {
      assert.equal(isOnGrid(px, 4), true, `${px}px should be on 4px grid`);
    }
  });

  test('rejects off-scale values', () => {
    for (const px of [1, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15, 17]) {
      assert.equal(isOnGrid(px, 4), false, `${px}px should NOT be on 4px grid`);
    }
  });
});

// ---------------------------------------------------------------------------
// parseRgb
// ---------------------------------------------------------------------------
describe('parseRgb', () => {
  test('parses rgb()', () => {
    assert.deepEqual(parseRgb('rgb(0, 0, 0)'), { r: 0, g: 0, b: 0 });
    assert.deepEqual(parseRgb('rgb(255, 255, 255)'), { r: 255, g: 255, b: 255 });
    assert.deepEqual(parseRgb('rgb(204, 204, 204)'), { r: 204, g: 204, b: 204 });
  });

  test('parses rgba()', () => {
    const c = parseRgb('rgba(204, 204, 204, 0.5)');
    assert.deepEqual(c, { r: 204, g: 204, b: 204 });
  });

  test('returns null for invalid input', () => {
    assert.equal(parseRgb('#ccc'), null);
    assert.equal(parseRgb('transparent'), null);
    assert.equal(parseRgb(null), null);
  });
});

// ---------------------------------------------------------------------------
// relLuminance + contrastRatio
// ---------------------------------------------------------------------------
describe('WCAG luminance and contrast', () => {
  test('white has luminance 1.0', () => {
    const l = relLuminance(255, 255, 255);
    assert.ok(Math.abs(l - 1.0) < 0.001, `Expected ~1.0, got ${l}`);
  });

  test('black has luminance ~0.0', () => {
    const l = relLuminance(0, 0, 0);
    assert.ok(l < 0.001, `Expected ~0, got ${l}`);
  });

  test('white-on-black contrast is 21:1', () => {
    const ratio = contrastRatio({ r: 255, g: 255, b: 255 }, { r: 0, g: 0, b: 0 });
    assert.ok(Math.abs(ratio - 21) < 0.1, `Expected ~21, got ${ratio}`);
  });

  test('#ccc on #fff gives ~1.6:1 (fails WCAG AA)', () => {
    const ratio = contrastRatio(
      { r: 204, g: 204, b: 204 },
      { r: 255, g: 255, b: 255 },
    );
    assert.ok(ratio > 1.5 && ratio < 1.7, `Expected ~1.6, got ${ratio}`);
    assert.ok(ratio < 4.5, 'Should fail WCAG AA (< 4.5:1)');
  });

  test('dark grey #767676 on white just passes 4.5:1', () => {
    const ratio = contrastRatio(
      { r: 118, g: 118, b: 118 },
      { r: 255, g: 255, b: 255 },
    );
    assert.ok(ratio >= 4.4, `Expected ≥ 4.4, got ${ratio}`);
  });
});

// ---------------------------------------------------------------------------
// lintBundle — off-scale spacing
// ---------------------------------------------------------------------------
describe('lintBundle — off-scale-spacing', () => {
  function makeEl(overrides = {}) {
    return {
      selector: 'div.test',
      tagName: 'DIV',
      textContent: '',
      isInteractive: false,
      styles: {
        marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
        paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
        gap: 'normal', rowGap: 'normal', columnGap: 'normal',
        fontSize: '16px', fontWeight: '400', lineHeight: '24px',
        color: 'rgb(0, 0, 0)', backgroundColor: 'rgb(255, 255, 255)',
        width: '200px', height: '40px',
        _rect: { width: 200, height: 40, x: 0, y: 0 },
        ...overrides.styles,
      },
      ...overrides,
    };
  }

  test('flags 13px marginTop as off-scale', () => {
    const bundle = { screen: 'test', elements: [makeEl({ styles: { marginTop: '13px' } })] };
    const findings = lintBundle(bundle);
    assert.ok(
      findings.some(f => f.rule === 'off-scale-spacing' && f.property === 'marginTop'),
      `Expected off-scale-spacing for marginTop:13px. Got: ${JSON.stringify(findings.map(f => f.rule))}`,
    );
  });

  test('does not flag 8px marginTop', () => {
    const bundle = { screen: 'test', elements: [makeEl({ styles: { marginTop: '8px' } })] };
    const findings = lintBundle(bundle);
    assert.ok(
      !findings.some(f => f.rule === 'off-scale-spacing'),
      '8px should be on-grid — no spacing finding expected',
    );
  });

  test('does not flag 0px spacing', () => {
    const bundle = { screen: 'test', elements: [makeEl()] };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'off-scale-spacing'));
  });

  test('flags off-scale gap', () => {
    const bundle = { screen: 'test', elements: [makeEl({ styles: { gap: '5px' } })] };
    const findings = lintBundle(bundle);
    assert.ok(findings.some(f => f.rule === 'off-scale-spacing' && f.property === 'gap'));
  });
});

// ---------------------------------------------------------------------------
// classifySpacing (BUG 2 — sub-pixel noise vs authored off-grid)
// ---------------------------------------------------------------------------
describe('classifySpacing', () => {
  test('returns null for on-grid, zero, and null values', () => {
    assert.equal(classifySpacing(0), null);
    assert.equal(classifySpacing(8), null);
    assert.equal(classifySpacing(16), null);
    assert.equal(classifySpacing(null), null);
  });

  test('near-grid sub-pixel values are treated as on-grid (tolerance)', () => {
    assert.equal(classifySpacing(11.6), null, '11.6 is within 0.5 of 12');
    assert.equal(classifySpacing(8.25), null, '8.25 is within 0.5 of 8');
    assert.equal(classifySpacing(15.75), null, '15.75 is within 0.5 of 16');
  });

  test('integer off-grid values are HIGH confidence', () => {
    assert.equal(classifySpacing(13)?.confidence, 'high');
    assert.equal(classifySpacing(10)?.confidence, 'high');   // Tailwind py-2.5
    assert.equal(classifySpacing(30)?.confidence, 'high');
  });

  test('sub-pixel off-grid values are LOW confidence', () => {
    assert.equal(classifySpacing(22.5)?.confidence, 'low');  // text-sm line-height artifact
    assert.equal(classifySpacing(10.5)?.confidence, 'low');
    assert.equal(classifySpacing(13.333)?.confidence, 'low');
  });
});

// ---------------------------------------------------------------------------
// lintBundle — off-scale-spacing confidence + noise suppression (BUG 2)
// ---------------------------------------------------------------------------
describe('lintBundle — off-scale-spacing noise suppression', () => {
  function elWith(prop, val) {
    return {
      selector: 'div.tw', tagName: 'DIV', textContent: '', isInteractive: false,
      styles: {
        marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
        paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
        gap: 'normal', rowGap: 'normal', columnGap: 'normal',
        fontSize: '16px', fontWeight: '400', lineHeight: '24px',
        color: 'rgb(0,0,0)', backgroundColor: 'rgb(255,255,255)',
        width: '200px', height: '40px', _rect: { width: 200, height: 40, x: 0, y: 0 },
        [prop]: val,
      },
    };
  }

  test('integer off-grid (13px) is flagged with confidence:high, severity:warning', () => {
    const findings = lintBundle({ screen: 't', elements: [elWith('marginTop', '13px')] });
    const f = findings.find(x => x.rule === 'off-scale-spacing');
    assert.ok(f, 'expected a spacing finding for 13px');
    assert.equal(f.confidence, 'high');
    assert.equal(f.severity, 'warning');
  });

  test('sub-pixel fractional (22.5px) is SUPPRESSED by default', () => {
    const findings = lintBundle({ screen: 't', elements: [elWith('paddingTop', '22.5px')] });
    assert.ok(!findings.some(x => x.rule === 'off-scale-spacing'),
      `22.5px should be suppressed by default. Got: ${JSON.stringify(findings)}`);
  });

  test('sub-pixel fractional (10.5px gap) is SUPPRESSED by default', () => {
    const findings = lintBundle({ screen: 't', elements: [elWith('gap', '10.5px')] });
    assert.ok(!findings.some(x => x.rule === 'off-scale-spacing'));
  });

  test('near-grid sub-pixel (11.6px) is never flagged', () => {
    const findings = lintBundle({ screen: 't', elements: [elWith('marginLeft', '11.6px')] });
    assert.ok(!findings.some(x => x.rule === 'off-scale-spacing'));
  });

  test('includeLowConfidence surfaces sub-pixel findings as confidence:low, severity:info', () => {
    const findings = lintBundle(
      { screen: 't', elements: [elWith('paddingTop', '22.5px')] },
      { includeLowConfidence: true },
    );
    const f = findings.find(x => x.rule === 'off-scale-spacing');
    assert.ok(f, 'expected a low-confidence finding when opted in');
    assert.equal(f.confidence, 'low');
    assert.equal(f.severity, 'info');
  });

  test('authored inline-style value is flagged HIGH even when sub-pixel', () => {
    // A fractional value that is explicitly authored (inline style) is a real
    // decision, not a computed rounding artifact — surface it.
    const el = elWith('marginTop', '13.5px');
    el.inlineStyle = 'margin-top: 13.5px';
    const findings = lintBundle({ screen: 't', elements: [el] });
    const f = findings.find(x => x.rule === 'off-scale-spacing');
    assert.ok(f, 'authored sub-pixel value should still be flagged by default');
    assert.equal(f.confidence, 'high');
  });

  test('a wall of Tailwind fractional spacing collapses to near-zero noise', () => {
    // Simulate the real-app blowup: many sub-pixel computed values.
    const fractionals = ['22.5px', '13.333px', '10.5px', '18.75px', '6.5px', '26.5px'];
    const elements = fractionals.map((v, i) => ({
      selector: `div.f${i}`, tagName: 'DIV', textContent: '', isInteractive: false,
      styles: {
        marginTop: v, marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
        paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
        gap: 'normal', rowGap: 'normal', columnGap: 'normal',
        fontSize: '16px', fontWeight: '400', lineHeight: '24px',
        color: 'rgb(0,0,0)', backgroundColor: 'rgb(255,255,255)',
        width: '10px', height: '10px', _rect: { width: 10, height: 10, x: 0, y: 0 },
      },
    }));
    const noisy = lintBundle({ screen: 't', elements });
    assert.equal(noisy.filter(f => f.rule === 'off-scale-spacing').length, 0,
      'default lint should suppress all sub-pixel spacing noise');
    const full = lintBundle({ screen: 't', elements }, { includeLowConfidence: true });
    assert.equal(full.filter(f => f.rule === 'off-scale-spacing').length, fractionals.length,
      'opt-in lint should surface them all as low-confidence');
  });
});

// ---------------------------------------------------------------------------
// lintBundle — WCAG contrast
// ---------------------------------------------------------------------------
describe('lintBundle — wcag-contrast', () => {
  test('flags #ccc on #fff as low-contrast', () => {
    const bundle = {
      screen: 'test',
      elements: [{
        selector: 'p.low-contrast',
        tagName: 'P',
        textContent: 'Low contrast text',
        isInteractive: false,
        styles: {
          marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
          paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
          gap: 'normal', rowGap: 'normal', columnGap: 'normal',
          fontSize: '14px', fontWeight: '400', lineHeight: '21px',
          color: 'rgb(204, 204, 204)',
          backgroundColor: 'rgb(255, 255, 255)',
          width: '200px', height: '20px',
          _rect: { width: 200, height: 20, x: 0, y: 0 },
        },
      }],
    };
    const findings = lintBundle(bundle);
    assert.ok(
      findings.some(f => f.rule === 'wcag-contrast'),
      `Expected wcag-contrast finding. Got: ${JSON.stringify(findings.map(f => f.rule))}`,
    );
    const cf = findings.find(f => f.rule === 'wcag-contrast');
    const ratio = parseFloat(cf.value);
    assert.ok(ratio < 4.5, `Contrast ratio ${ratio} should be < 4.5`);
  });

  test('does not flag #000 on #fff (21:1)', () => {
    const bundle = {
      screen: 'test',
      elements: [{
        selector: 'p.good',
        tagName: 'P',
        textContent: 'Good contrast',
        isInteractive: false,
        styles: {
          marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
          paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
          gap: 'normal', rowGap: 'normal', columnGap: 'normal',
          fontSize: '14px', fontWeight: '400', lineHeight: '21px',
          color: 'rgb(0, 0, 0)',
          backgroundColor: 'rgb(255, 255, 255)',
          width: '200px', height: '20px',
          _rect: { width: 200, height: 20, x: 0, y: 0 },
        },
      }],
    };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'wcag-contrast'));
  });

  test('does not flag elements with no text content', () => {
    const bundle = {
      screen: 'test',
      elements: [{
        selector: 'div.icon',
        tagName: 'DIV',
        textContent: '',    // no text
        isInteractive: false,
        styles: {
          marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
          paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
          gap: 'normal', rowGap: 'normal', columnGap: 'normal',
          fontSize: '14px', fontWeight: '400', lineHeight: '21px',
          color: 'rgb(204, 204, 204)',
          backgroundColor: 'rgb(255, 255, 255)',
          width: '24px', height: '24px',
          _rect: { width: 24, height: 24, x: 0, y: 0 },
        },
      }],
    };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'wcag-contrast'));
  });
});

// ---------------------------------------------------------------------------
// lintBundle — tap-target
// ---------------------------------------------------------------------------
describe('lintBundle — tap-target', () => {
  function makeBtn(w, h, extra = {}) {
    return {
      selector: `#btn-${w}x${h}`,
      tagName: 'BUTTON',
      textContent: 'Click',
      isInteractive: true,
      styles: {
        marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
        paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
        gap: 'normal', rowGap: 'normal', columnGap: 'normal',
        fontSize: '14px', fontWeight: '400', lineHeight: '21px',
        color: 'rgb(255, 255, 255)', backgroundColor: 'rgb(0, 112, 243)',
        width: `${w}px`, height: `${h}px`,
        _rect: { width: w, height: h, x: 0, y: 0 },
        ...extra,
      },
    };
  }

  test('flags 30×30 button', () => {
    const bundle = { screen: 'test', elements: [makeBtn(30, 30)] };
    const findings = lintBundle(bundle);
    assert.ok(
      findings.some(f => f.rule === 'tap-target'),
      `Expected tap-target finding for 30×30 button. Got: ${JSON.stringify(findings.map(f => f.rule))}`,
    );
  });

  test('flags 44×30 button (height too small)', () => {
    const bundle = { screen: 'test', elements: [makeBtn(44, 30)] };
    const findings = lintBundle(bundle);
    assert.ok(findings.some(f => f.rule === 'tap-target'));
  });

  test('does not flag 44×44 button', () => {
    const bundle = { screen: 'test', elements: [makeBtn(44, 44)] };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'tap-target'));
  });

  test('does not flag 48×48 button', () => {
    const bundle = { screen: 'test', elements: [makeBtn(48, 48)] };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'tap-target'));
  });

  test('uses _rect dimensions when available', () => {
    // _rect overrides styles.width/height (actual rendered size vs CSS)
    const el = makeBtn(44, 44);
    el.styles._rect = { width: 30, height: 30, x: 0, y: 0 };  // rendered smaller
    const bundle = { screen: 'test', elements: [el] };
    const findings = lintBundle(bundle);
    assert.ok(findings.some(f => f.rule === 'tap-target'),
      'Should use _rect size (30×30) over CSS size (44×44)');
  });
});

// ---------------------------------------------------------------------------
// lintBundle — type-scale sprawl
// ---------------------------------------------------------------------------
describe('lintBundle — type-scale-sprawl', () => {
  function makeText(fs, fw, lh) {
    return {
      selector: `span.t${fs}`,
      tagName: 'SPAN',
      textContent: 'text',
      isInteractive: false,
      styles: {
        marginTop: '0px', marginBottom: '0px', marginLeft: '0px', marginRight: '0px',
        paddingTop: '0px', paddingBottom: '0px', paddingLeft: '0px', paddingRight: '0px',
        gap: 'normal', rowGap: 'normal', columnGap: 'normal',
        fontSize: fs, fontWeight: fw, lineHeight: lh,
        color: 'rgb(0,0,0)', backgroundColor: 'rgb(255,255,255)',
        width: '100px', height: '20px',
        _rect: { width: 100, height: 20, x: 0, y: 0 },
      },
    };
  }

  test('flags when > 6 distinct type triples', () => {
    const elements = [
      makeText('12px', '400', '18px'),
      makeText('14px', '400', '21px'),
      makeText('16px', '400', '24px'),
      makeText('18px', '600', '27px'),
      makeText('20px', '700', '30px'),
      makeText('24px', '700', '36px'),
      makeText('32px', '800', '48px'),  // 7th triple — exceeds limit
    ];
    const bundle = { screen: 'test', elements };
    const findings = lintBundle(bundle);
    assert.ok(findings.some(f => f.rule === 'type-scale-sprawl'));
  });

  test('does not flag 6 or fewer distinct type triples', () => {
    const elements = [
      makeText('14px', '400', '21px'),
      makeText('16px', '400', '24px'),
      makeText('18px', '600', '27px'),
      makeText('20px', '700', '30px'),
      makeText('24px', '700', '36px'),
      makeText('32px', '800', '48px'),
    ];
    const bundle = { screen: 'test', elements };
    const findings = lintBundle(bundle);
    assert.ok(!findings.some(f => f.rule === 'type-scale-sprawl'));
  });
});
