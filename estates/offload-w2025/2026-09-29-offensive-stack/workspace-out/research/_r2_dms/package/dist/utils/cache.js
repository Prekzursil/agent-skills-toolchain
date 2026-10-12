// Simple in-memory TTL cache
export class TTLCache {
    ttlMs;
    store = new Map();
    constructor(ttlMs) {
        this.ttlMs = ttlMs;
    }
    get(key) {
        const entry = this.store.get(key);
        if (!entry)
            return undefined;
        if (Date.now() > entry.expires) {
            this.store.delete(key);
            return undefined;
        }
        return entry.value;
    }
    set(key, value) {
        this.store.set(key, { value, expires: Date.now() + this.ttlMs });
    }
    has(key) {
        return this.get(key) !== undefined;
    }
    clear() {
        this.store.clear();
    }
    get size() {
        for (const [key, entry] of this.store) {
            if (Date.now() > entry.expires)
                this.store.delete(key);
        }
        return this.store.size;
    }
}
//# sourceMappingURL=cache.js.map