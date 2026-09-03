type PendingEntry = { hash: string; state: "pending"; expiresAt: number };
type CompleteEntry = { hash: string; state: "complete"; expiresAt: number; value: unknown };
type Entry = PendingEntry | CompleteEntry;

export class IdempotencyLedger {
  readonly maxEntries: number;
  readonly ttlMs: number;
  readonly now: () => number;
  #entries = new Map<string, Entry>();

  constructor(options: { maxEntries?: number; ttlMs?: number; now?: () => number } = {}) {
    this.maxEntries = Math.max(1, options.maxEntries ?? 4096);
    this.ttlMs = Math.max(1000, options.ttlMs ?? 15 * 60_000);
    this.now = options.now ?? Date.now;
  }

  get size(): number {
    this.#prune();
    return this.#entries.size;
  }

  begin(key: string, hash: string):
    | { state: "new" }
    | { state: "in_progress" }
    | { state: "conflict" }
    | { state: "full" }
    | { state: "replay"; value: unknown } {
    this.#prune();
    const existing = this.#entries.get(key);
    if (existing) {
      if (existing.hash !== hash) return { state: "conflict" };
      if (existing.state === "pending") return { state: "in_progress" };
      return { state: "replay", value: structuredClone(existing.value) };
    }
    if (this.#entries.size >= this.maxEntries && !this.#evictOldestComplete()) {
      return { state: "full" };
    }
    this.#entries.set(key, { hash, state: "pending", expiresAt: this.now() + this.ttlMs });
    return { state: "new" };
  }

  commit(key: string, hash: string, value: unknown, expiresAt?: number): void {
    const existing = this.#entries.get(key);
    if (!existing || existing.hash !== hash) throw new Error("idempotency_reservation_missing");
    const defaultExpiry = this.now() + this.ttlMs;
    this.#entries.set(key, {
      hash,
      state: "complete",
      expiresAt: Math.min(defaultExpiry, expiresAt ?? defaultExpiry),
      value: structuredClone(value),
    });
  }

  abandon(key: string, hash: string): void {
    const existing = this.#entries.get(key);
    if (existing?.state === "pending" && existing.hash === hash) this.#entries.delete(key);
  }

  #prune(): void {
    const now = this.now();
    for (const [key, entry] of this.#entries) {
      if (entry.expiresAt <= now) this.#entries.delete(key);
    }
  }

  #evictOldestComplete(): boolean {
    for (const [key, entry] of this.#entries) {
      if (entry.state !== "complete") continue;
      this.#entries.delete(key);
      return true;
    }
    return false;
  }
}
