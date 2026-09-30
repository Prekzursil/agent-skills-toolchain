// Queue-based rate limiter — ensures minimum delay between requests
export class RateLimiter {
    minDelayMs;
    lastRequest = 0;
    queue = [];
    processing = false;
    constructor(minDelayMs) {
        this.minDelayMs = minDelayMs;
    }
    async acquire() {
        return new Promise((resolve) => {
            this.queue.push(resolve);
            if (!this.processing)
                this.processQueue();
        });
    }
    async processQueue() {
        this.processing = true;
        while (this.queue.length > 0) {
            const now = Date.now();
            const elapsed = now - this.lastRequest;
            if (elapsed < this.minDelayMs) {
                await sleep(this.minDelayMs - elapsed);
            }
            this.lastRequest = Date.now();
            const resolve = this.queue.shift();
            resolve?.();
        }
        this.processing = false;
    }
}
function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}
//# sourceMappingURL=rate-limiter.js.map