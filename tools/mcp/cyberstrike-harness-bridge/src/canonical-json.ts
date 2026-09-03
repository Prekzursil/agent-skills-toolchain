import { createHash } from "node:crypto";

export function canonicalJson(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("canonical_json_non_finite_number");
    return JSON.stringify(Object.is(value, -0) ? 0 : value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const members = Object.keys(record)
      .sort()
      .map((key) => {
        const item = record[key];
        if (item === undefined || typeof item === "function" || typeof item === "symbol") {
          throw new TypeError(`canonical_json_unsupported_value:${key}`);
        }
        return `${JSON.stringify(key)}:${canonicalJson(item)}`;
      });
    return `{${members.join(",")}}`;
  }
  throw new TypeError("canonical_json_unsupported_value");
}

export function sha256Canonical(value: unknown): string {
  return createHash("sha256").update(canonicalJson(value), "utf8").digest("hex");
}

export function sha256Bytes(value: string | Buffer): string {
  return createHash("sha256").update(value).digest("hex");
}
