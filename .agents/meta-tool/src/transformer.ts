/**
 * Result transformer — filters/truncates MCP tool results to stay within token budget.
 */

const DEFAULT_MAX_TOKENS = 2000;
const DEFAULT_TOP_N = 15;
// Rough estimate: 1 token ~= 4 characters of JSON text
const CHARS_PER_TOKEN = 4;

/**
 * Fields considered non-essential during progressive truncation.
 * When over budget, these are stripped from objects before hard-truncating.
 */
const NON_ESSENTIAL_FIELDS = new Set([
  "metadata",
  "meta",
  "_meta",
  "_links",
  "links",
  "debug",
  "trace",
  "raw",
  "rawResponse",
  "headers",
  "requestId",
  "request_id",
  "cursor",
  "pagination",
]);

function estimateTokens(text: string): number {
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

/**
 * Remove non-essential fields from an object (shallow).
 */
function stripNonEssential(obj: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    if (!NON_ESSENTIAL_FIELDS.has(key)) {
      result[key] = value;
    }
  }
  return result;
}

/**
 * Recursively strip non-essential fields from nested objects and arrays.
 */
function deepStripNonEssential(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(deepStripNonEssential);
  }
  if (value !== null && typeof value === "object") {
    const stripped = stripNonEssential(value as Record<string, unknown>);
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(stripped)) {
      result[k] = deepStripNonEssential(v);
    }
    return result;
  }
  return value;
}

/**
 * Transform an MCP tool result to fit within a token budget.
 *
 * Strategy:
 * 1. If result is an array, cap to top_n items (default 15)
 * 2. If still over budget, progressively truncate:
 *    a. Reduce array size by half repeatedly
 *    b. Remove non-essential fields from objects
 *    c. Hard truncate the JSON string with "[... truncated]"
 * 3. Return a JSON string.
 */
export function transformResult(
  result: unknown,
  maxTokens: number = DEFAULT_MAX_TOKENS,
): string {
  let working = result;

  // Step 1: Cap arrays to top_n
  if (Array.isArray(working)) {
    if (working.length > DEFAULT_TOP_N) {
      working = working.slice(0, DEFAULT_TOP_N);
    }
  }

  // Check if we're within budget
  let json = JSON.stringify(working, null, 2);
  if (estimateTokens(json) <= maxTokens) {
    return json;
  }

  // Step 2a: If it's an array, keep halving until within budget
  if (Array.isArray(working)) {
    let arr = working as unknown[];
    while (arr.length > 1 && estimateTokens(JSON.stringify(arr, null, 2)) > maxTokens) {
      arr = arr.slice(0, Math.max(1, Math.floor(arr.length / 2)));
    }
    working = arr;
    json = JSON.stringify(working, null, 2);
    if (estimateTokens(json) <= maxTokens) {
      return json;
    }
  }

  // Step 2b: Strip non-essential fields
  working = deepStripNonEssential(working);
  json = JSON.stringify(working, null, 2);
  if (estimateTokens(json) <= maxTokens) {
    return json;
  }

  // Step 2c: Hard truncate
  const maxChars = maxTokens * CHARS_PER_TOKEN;
  const suffix = "\n[... truncated]";
  return json.slice(0, maxChars - suffix.length) + suffix;
}
