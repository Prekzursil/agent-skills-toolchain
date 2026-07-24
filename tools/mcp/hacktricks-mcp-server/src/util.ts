// Small shared utilities.

export function byteLength(value: string): number {
  return Buffer.byteLength(value, "utf8");
}

// Safe access to a regex capture group under noUncheckedIndexedAccess: a group
// that did not participate (optional group) yields "" rather than undefined.
export function matchGroup(match: RegExpExecArray, index: number): string {
  const value = match[index];
  if (value === undefined) {
    return "";
  }
  return value;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === "object" && value !== null) {
    return value as Record<string, unknown>;
  }
  return null;
}

// Is `target` the same as, or nested under, `root`? Separator-normalized so it
// is correct for both POSIX and Windows realpath output.
export function withinRoot(root: string, target: string): boolean {
  const r = root.replace(/\\/g, "/").replace(/\/+$/, "");
  const t = target.replace(/\\/g, "/");
  return t === r || t.startsWith(`${r}/`);
}
