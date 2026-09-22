// Hermetic unit suite for the injected page scripts. They are plain source
// strings executed inside the inspected page, so the unit contract is their
// SHAPE: constants, ref validation, and correct interpolation of the two
// parameterised templates. Their in-page behaviour is exercised by the live
// smoke/e2e lanes against real Chrome.
import test from "node:test";
import assert from "node:assert/strict";

import {
  FAVICON_BADGE_SCRIPT,
  OVERLAY_ROOT_ID,
  REF_PATTERN,
  RESOLVE_REF_SCRIPT,
  SELECT_ALL_SCRIPT,
  SNAPSHOT_SCRIPT,
  TEXT_SCRIPT,
} from "../dist/pagescript.js";

test("pagescript: refs follow the epoch-element shape", () => {
  assert.match("k3f9a1-e12", REF_PATTERN);
  assert.match("abcdef-e1", REF_PATTERN);
  assert.doesNotMatch("k3f9a1", REF_PATTERN, "missing element part");
  assert.doesNotMatch("-e12", REF_PATTERN, "missing epoch");
  assert.doesNotMatch("K3F9A1-e12", REF_PATTERN, "uppercase epochs are rejected");
  assert.doesNotMatch("k3f9a1-e12 extra", REF_PATTERN, "trailing junk is rejected");
  assert.doesNotMatch("../../../etc-e1", REF_PATTERN, "path fragments are rejected");
});

test("pagescript: snapshot and text scripts exclude the agent overlay", () => {
  assert.ok(OVERLAY_ROOT_ID.startsWith("__cb-agent-overlay-root"));
  assert.ok(SNAPSHOT_SCRIPT.includes(JSON.stringify(OVERLAY_ROOT_ID)));
  assert.ok(TEXT_SCRIPT.includes(JSON.stringify(OVERLAY_ROOT_ID)));
  assert.ok(SNAPSHOT_SCRIPT.startsWith("(() => {"));
  assert.ok(TEXT_SCRIPT.startsWith("(() => {"));
  assert.ok(SELECT_ALL_SCRIPT.startsWith("(() => {"));
});

test("pagescript: the ref resolver embeds the ref and both stale-ref hints", () => {
  const script = RESOLVE_REF_SCRIPT("k3f9a1-e12");
  assert.ok(script.includes('"k3f9a1-e12"'), "the ref is embedded as a JSON string");
  assert.ok(script.includes("Unknown ref."), "missing-ref hint present");
  assert.ok(script.includes("removed from the page"), "removed-element hint present");
});

test("pagescript: the favicon badge template has distinct active and inactive forms", () => {
  const active = FAVICON_BADGE_SCRIPT(true);
  const inactive = FAVICON_BADGE_SCRIPT(false);
  assert.notEqual(active, inactive);
  assert.ok(active.includes("if (!true)"), "active template interpolates the boolean true");
  assert.ok(inactive.includes("if (!false)"), "inactive template interpolates the boolean false");
  assert.ok(inactive.includes("restored: true"), "inactive template restores icons");
  assert.ok(active.includes("data:image/svg+xml"), "active template badges the icon");
});
