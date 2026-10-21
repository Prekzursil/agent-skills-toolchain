// Blockchain Intelligence — Bitcoin address, transaction, and abuse checking
// Tools: btcAddress, btcBalance, btcTx, btcAbuseCheck
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(500);
const cache = new TTLCache(5 * 60 * 1000); // 5 min
// ─── Helpers ───
async function blockchainFetch(url) {
    const cacheKey = `blockchain:${url}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(url, {
        headers: {
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Blockchain API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 1. btcAddress — Get Bitcoin address info with recent transactions ───
export async function btcAddress(address) {
    return blockchainFetch(`https://blockchain.info/rawaddr/${encodeURIComponent(address)}?limit=50`);
}
// ─── 2. btcBalance — Get Bitcoin address balance in satoshi ───
export async function btcBalance(address) {
    return blockchainFetch(`https://blockchain.info/balance?active=${encodeURIComponent(address)}`);
}
// ─── 3. btcTx — Get Bitcoin transaction details ───
export async function btcTx(txhash) {
    return blockchainFetch(`https://blockchain.info/rawtx/${encodeURIComponent(txhash)}`);
}
// ─── 4. btcAbuseCheck — Check address for abuse reports on ChainAbuse ───
export async function btcAbuseCheck(address) {
    const cacheKey = `chainabuse:${address}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const params = new URLSearchParams({ address });
    const response = await fetch(`https://api.chainabuse.com/v0/reports?${params.toString()}`, {
        headers: {
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        // ChainAbuse may return 404 for unknown addresses — treat as empty
        if (response.status === 404) {
            const empty = { reports: [], count: 0 };
            cache.set(cacheKey, empty);
            return empty;
        }
        const body = await response.text().catch(() => "");
        throw new Error(`ChainAbuse API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
//# sourceMappingURL=index.js.map