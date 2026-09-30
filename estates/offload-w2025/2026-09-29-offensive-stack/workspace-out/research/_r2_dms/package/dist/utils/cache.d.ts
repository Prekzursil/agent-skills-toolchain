export declare class TTLCache<T> {
    private ttlMs;
    private store;
    constructor(ttlMs: number);
    get(key: string): T | undefined;
    set(key: string, value: T): void;
    has(key: string): boolean;
    clear(): void;
    get size(): number;
}
//# sourceMappingURL=cache.d.ts.map