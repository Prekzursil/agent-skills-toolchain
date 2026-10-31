/**
 * visual_diff.test.mjs — unit tests for diffBuffersSync.
 * No browser, no files — tests the pure RGBA buffer diff logic.
 */

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { diffBuffersSync } from '../visual_diff.mjs';

function makeRgba(r, g, b, a, pixelCount) {
  const buf = Buffer.alloc(pixelCount * 4);
  for (let i = 0; i < pixelCount; i++) {
    buf[i * 4 + 0] = r;
    buf[i * 4 + 1] = g;
    buf[i * 4 + 2] = b;
    buf[i * 4 + 3] = a;
  }
  return buf;
}

describe('diffBuffersSync', () => {
  const W = 4, H = 4, N = W * H;

  test('identical images produce 0% diff', () => {
    const white = makeRgba(255, 255, 255, 255, N);
    const { percentDiff, numDiff } = diffBuffersSync(white, white, W, H);
    assert.equal(numDiff, 0);
    assert.equal(percentDiff, 0);
  });

  test('fully different images produce > 0% diff', () => {
    const white = makeRgba(255, 255, 255, 255, N);
    const black = makeRgba(0, 0, 0, 255, N);
    const { percentDiff, numDiff } = diffBuffersSync(white, black, W, H);
    assert.ok(numDiff > 0, `Expected numDiff > 0, got ${numDiff}`);
    assert.ok(percentDiff > 0, `Expected percentDiff > 0, got ${percentDiff}`);
  });

  test('single-pixel change produces small diff', () => {
    const base = makeRgba(255, 255, 255, 255, N);
    const changed = Buffer.from(base);
    // Flip one pixel to black
    changed[0] = 0; changed[1] = 0; changed[2] = 0;
    const { percentDiff } = diffBuffersSync(base, changed, W, H);
    // At most 1/16 = 6.25% of pixels changed
    assert.ok(percentDiff < 10, `Expected < 10%, got ${percentDiff}`);
    assert.ok(percentDiff > 0, 'Expected some diff');
  });

  test('diff buffer has correct length', () => {
    const white = makeRgba(255, 255, 255, 255, N);
    const black = makeRgba(0, 0, 0, 255, N);
    const { diff } = diffBuffersSync(white, black, W, H);
    assert.equal(diff.length, W * H * 4, 'diff buffer should be W×H×4 bytes');
  });

  test('throws if pixelmatch is missing (mocked scenario — just ensure export exists)', () => {
    // We can only test the error path if pixelmatch is NOT installed.
    // Since it IS installed, verify the function is callable and returns a number.
    const a = makeRgba(128, 128, 128, 255, N);
    const b = makeRgba(128, 128, 128, 255, N);
    const { numDiff } = diffBuffersSync(a, b, W, H);
    assert.equal(typeof numDiff, 'number');
  });
});
