/**
 * The ONE closed failure taxonomy — the JS mirror of `agentspec/taxonomy.py`.
 *
 * `REASONS` is NOT retyped by hand as an independent decision: `test/crosslang.test.mjs` parses
 * the Python module and fails if the two tuples differ in members or order, so the Python
 * package stays the single source of truth and this file cannot silently drift from it.
 *
 * Members are *segment*-shaped so a parametrised code (`rail-exit-137`, `timeout-1800s`) is
 * recognised by prefix WITHOUT `startsWith` accepting a near-miss like `rail-exiting`.
 */

/** Sorted, unique and CLOSED. Growing it is a reviewed diff on the PYTHON side, never here. */
export const REASONS = Object.freeze([
  "budget-exhausted",
  "env-missing",
  "policy-violation",
  "progress-stream",
  "rail-exit",
  "rate-limited",
  "receipt-empty",
  "receipt-incomplete",
  "receipt-missing",
  "receipt-unparseable",
  "schema-invalid",
  "severed-stream",
  "spawn-failed",
  "timeout",
  "win-arg-limit",
]);

/**
 * The taxonomy MEMBER behind a bare-or-parametrised `code`; `""` when there is none.
 *
 * The hyphen boundary is REQUIRED, so `rail-exiting` resolves to `""` even though `rail-exit`
 * is a member. One implementation, so a second copy cannot drift and accept a near-miss.
 */
export function family(code) {
  for (const member of REASONS) {
    if (code === member || code.startsWith(`${member}-`)) {
      return member;
    }
  }
  return "";
}

/** True when `code` is a taxonomy member, bare or parametrised. */
export function isReason(code) {
  return family(code) !== "";
}

/** Render the `rail-exit-<n>` reason for a NON-ZERO rail exit. */
export function railExit(exitCode) {
  if (exitCode === 0) {
    throw new RangeError("railExit: exit 0 is never a rail failure (SEVERED or SUCCESS)");
  }
  return `rail-exit-${exitCode}`;
}

/** Render the `timeout-<n>s` reason. A dispatch has no implicit timeout. */
export function timeout(seconds) {
  if (seconds <= 0) {
    throw new RangeError("timeout: seconds must be positive (an explicit budget is mandatory)");
  }
  return `timeout-${seconds}s`;
}

/**
 * Render the `rate-limited-<status>` reason for a 429/529-class refusal.
 *
 * Only a 4xx/5xx status is accepted — `rate-limited-200` would be a reason nobody can act on,
 * and minting an unusable code is how a closed taxonomy stops being closed in practice.
 */
export function rateLimited(status) {
  if (status < 400 || status > 599) {
    throw new RangeError(`rateLimited: ${status} is not a 4xx/5xx status`);
  }
  return `rate-limited-${status}`;
}

/** Render the `env-missing-<NAME>` reason. Never carries the variable's VALUE. */
export function envMissing(name) {
  if (name === "") {
    throw new RangeError("envMissing: name must be non-empty");
  }
  return `env-missing-${name}`;
}
