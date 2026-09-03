import { canonicalJson, sha256Bytes } from "./canonical-json.ts";

const SENSITIVE_KEYS = new Set([
  "authorization",
  "auth",
  "body",
  "command",
  "cookie",
  "environment",
  "env",
  "exception",
  "filecontent",
  "headers",
  "output",
  "password",
  "prompt",
  "provideroptions",
  "rawheaders",
  "stderr",
  "stdin",
  "stdout",
]);

function isSensitiveKey(key: string): boolean {
  const normalized = key.replace(/[_-]/g, "").toLowerCase();
  if (SENSITIVE_KEYS.has(normalized)) return true;
  if (normalized.endsWith("password") || normalized.endsWith("secret")) return true;
  if (normalized.endsWith("token") && normalized !== "tokenlength") return true;
  if (normalized.endsWith("cookie") || normalized.endsWith("authorization")) return true;
  return false;
}

export function deepRedact(value: unknown, depth = 0): any {
  if (depth > 32) return "[REDACTED:DEPTH]";
  if (Array.isArray(value)) return value.map((item) => deepRedact(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        isSensitiveKey(key) ? "[REDACTED]" : deepRedact(item, depth + 1),
      ]),
    );
  }
  return value;
}

function fingerprint(value: unknown): { length: number; sha256: string } {
  if (value === undefined) return { length: 0, sha256: sha256Bytes("") };
  const serialized = canonicalJson(deepRedact(value));
  return { length: Buffer.byteLength(serialized, "utf8"), sha256: sha256Bytes(serialized) };
}

type AuditInput = {
  utc: string;
  requestId: string;
  correlationId: string;
  engagementId?: string;
  capability: string;
  decision: string;
  reasonCode: string;
  durationMs: number;
  arguments?: unknown;
  result?: unknown;
};

export function createAuditRecord(input: AuditInput) {
  const argumentsFingerprint = fingerprint(input.arguments);
  const resultFingerprint = fingerprint(input.result);
  return Object.freeze({
    utc: input.utc,
    requestId: input.requestId,
    correlationId: input.correlationId,
    ...(input.engagementId === undefined ? {} : { engagementId: input.engagementId }),
    capability: input.capability,
    decision: input.decision,
    reasonCode: input.reasonCode,
    durationMs: input.durationMs,
    argumentsSha256: argumentsFingerprint.sha256,
    argumentsLength: argumentsFingerprint.length,
    resultSha256: resultFingerprint.sha256,
    resultLength: resultFingerprint.length,
  });
}

export type AuditRecord = ReturnType<typeof createAuditRecord>;

export interface AuditSink {
  append(record: AuditRecord): Promise<void>;
}

export class MemoryAuditSink implements AuditSink {
  readonly maxEntries: number;
  readonly records: AuditRecord[] = [];

  constructor(maxEntries = 1024) {
    this.maxEntries = Math.max(1, maxEntries);
  }

  async append(record: AuditRecord): Promise<void> {
    this.records.push(structuredClone(record));
    while (this.records.length > this.maxEntries) this.records.shift();
  }
}
