// Structured failure envelopes and the CallToolResult projections. Every failure
// travels on the tool output channel with isError:true and a stable reason code;
// an unstructured thrown exception is never returned to the client.

import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { MAX_TEXT_PROJECTION_BYTES } from "./limits.js";

export const ERROR_CODES = [
  "no_match",
  "backend_unavailable",
  "query_invalid",
  "retrieval_failed",
  "content_too_large",
  "retrieval_truncated",
  "section_ambiguous",
  "citation_unverified",
  "provenance_mismatch",
  "stale_source",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export interface Failure {
  ok: false;
  error: {
    code: ErrorCode;
    subcode: string | null;
    message: string;
    retryable: boolean;
    attempts: number;
  };
  receipt: {
    operation: string;
    request_id: string;
    elapsed_ms: number;
  };
}

export function buildFailure(
  operation: string,
  requestId: string,
  elapsedMs: number,
  code: ErrorCode,
  message: string,
  subcode: string | null,
  retryable: boolean,
  attempts: number,
): Failure {
  return {
    ok: false,
    error: { code, subcode, message, retryable, attempts },
    receipt: { operation, request_id: requestId, elapsed_ms: elapsedMs },
  };
}

// Bounded JSON text projection retained only for client compatibility.
export function boundedJson(value: unknown, maxBytes: number): string {
  const s = JSON.stringify(value);
  if (s.length > maxBytes) {
    return s.slice(0, maxBytes);
  }
  return s;
}

export function toolError(failure: Failure): CallToolResult {
  return {
    content: [
      { type: "text", text: boundedJson(failure, MAX_TEXT_PROJECTION_BYTES) },
    ],
    structuredContent: failure as unknown as Record<string, unknown>,
    isError: true,
  };
}

export function toolOk(structured: Record<string, unknown>): CallToolResult {
  return {
    content: [
      { type: "text", text: boundedJson(structured, MAX_TEXT_PROJECTION_BYTES) },
    ],
    structuredContent: structured,
  };
}
