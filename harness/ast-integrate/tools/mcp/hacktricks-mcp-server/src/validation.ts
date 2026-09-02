// Input validation performed BEFORE any I/O. Every rejection is a schema/format
// failure and maps to the `query_invalid` error code. A returned path is still
// untrusted and must pass the same validation on reuse.

import {
  DEFAULT_SEARCH_RESULTS,
  MAX_PATH_CHARS,
  MAX_QUERY_CHARS,
  MAX_SEARCH_RESULTS,
  MAX_SECTION_CHARS,
} from "./limits.js";
import { hasControlOrBidi } from "./text.js";

export interface Invalid {
  ok: false;
  field: string;
  message: string;
}
export interface Valid<T> {
  ok: true;
  value: T;
}
export type Validated<T> = Valid<T> | Invalid;

function invalid(field: string, message: string): Invalid {
  return { ok: false, field, message };
}

const DRIVE_PREFIX = /^[a-zA-Z]:/;
const URI_SCHEME = /^[a-zA-Z][a-zA-Z0-9+.-]*:/;
const PERCENT_TRAVERSAL = /%2e|%2f|%5c/i;

export function validateBoundedText(
  value: unknown,
  field: string,
  maxChars: number,
): Validated<string> {
  if (typeof value !== "string") {
    return invalid(field, "must be a string");
  }
  if (hasControlOrBidi(value)) {
    return invalid(field, "must not contain control or bidi characters");
  }
  if (value.trim().length === 0) {
    return invalid(field, "must not be empty");
  }
  if (value.length > maxChars) {
    return invalid(field, `must be at most ${maxChars} characters`);
  }
  return { ok: true, value };
}

export function validateQuery(value: unknown): Validated<string> {
  return validateBoundedText(value, "query", MAX_QUERY_CHARS);
}

export function validateTopic(value: unknown): Validated<string> {
  return validateBoundedText(value, "topic", MAX_QUERY_CHARS);
}

export function validateSection(value: unknown): Validated<string> {
  return validateBoundedText(value, "section", MAX_SECTION_CHARS);
}

// A page path must be a relative, normalized, `/`-separated markdown path rooted
// at `src/`. Reject absolute/drive/UNC paths, URI schemes, backslashes,
// percent-encoded traversal, `.`/`..`/empty segments, and non-`.md` suffixes.
export function validatePath(value: unknown): Validated<string> {
  if (typeof value !== "string") {
    return invalid("path", "must be a string");
  }
  if (value.length === 0) {
    return invalid("path", "must not be empty");
  }
  if (value.length > MAX_PATH_CHARS) {
    return invalid("path", `must be at most ${MAX_PATH_CHARS} characters`);
  }
  if (hasControlOrBidi(value)) {
    return invalid("path", "must not contain control or bidi characters");
  }
  if (value.includes("\\")) {
    return invalid("path", "must not contain a backslash");
  }
  if (value.startsWith("/")) {
    return invalid("path", "must not be an absolute path");
  }
  if (DRIVE_PREFIX.test(value)) {
    return invalid("path", "must not be a drive path");
  }
  if (URI_SCHEME.test(value)) {
    return invalid("path", "must not contain a URI scheme");
  }
  if (PERCENT_TRAVERSAL.test(value)) {
    return invalid("path", "must not contain percent-encoded traversal");
  }
  const segments = value.split("/");
  for (const segment of segments) {
    if (segment === "" || segment === "." || segment === "..") {
      return invalid("path", "must not contain empty or dot path segments");
    }
  }
  if (!value.startsWith("src/")) {
    return invalid("path", "must be rooted at src/");
  }
  if (!value.endsWith(".md")) {
    return invalid("path", "must be a .md page");
  }
  return { ok: true, value };
}

export function validateCategory(
  value: unknown,
  allowlist: readonly string[],
): Validated<string> {
  if (typeof value !== "string") {
    return invalid("category", "must be a string");
  }
  if (value.length === 0) {
    return invalid("category", "must not be empty");
  }
  if (hasControlOrBidi(value)) {
    return invalid("category", "must not contain control or bidi characters");
  }
  if (!allowlist.includes(value)) {
    return invalid("category", "must be an enumerated category");
  }
  return { ok: true, value };
}

// Optional limit: schema default DEFAULT_SEARCH_RESULTS, runtime maximum
// MAX_SEARCH_RESULTS (clamped, not rejected).
export function validateLimit(value: unknown): Validated<number> {
  if (value === undefined) {
    return { ok: true, value: DEFAULT_SEARCH_RESULTS };
  }
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return invalid("limit", "must be an integer");
  }
  if (value < 1) {
    return invalid("limit", "must be at least 1");
  }
  if (value > MAX_SEARCH_RESULTS) {
    return { ok: true, value: MAX_SEARCH_RESULTS };
  }
  return { ok: true, value };
}
