export declare class RateLimiter {
    private minDelayMs;
    private lastRequest;
    private queue;
    private processing;
    constructor(minDelayMs: number);
    acquire(): Promise<void>;
    private processQueue;
}
//# sourceMappingURL=rate-limiter.d.ts.map