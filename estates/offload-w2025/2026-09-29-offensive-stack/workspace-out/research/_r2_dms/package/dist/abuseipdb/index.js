// AbuseIPDB — IP abuse reporting and checking provider
// Tools: abuseipdbCheck, abuseipdbReports, abuseipdbBlacklist, abuseipdbCheckBlock
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
import { requireApiKey } from "../utils/require-key.js";
// ─── Constants ───
const BASE_URL = "https://api.abuseipdb.com/api/v2";
// ─── Rate Limiter & Caches ───
const limiter = new RateLimiter(1000);
const cache = new TTLCache(10 * 60 * 1000); // 10 min
const blacklistCache = new TTLCache(30 * 60 * 1000); // 30 min
// ─── Helpers ───
async function abuseipdbFetch(path, apiKey, useBlacklistCache = false) {
    const cacheKey = `abuseipdb:${path}`;
    const targetCache = useBlacklistCache ? blacklistCache : cache;
    const cached = targetCache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(`${BASE_URL}${path}`, {
        headers: {
            Key: apiKey,
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`AbuseIPDB API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    targetCache.set(cacheKey, data);
    return data;
}
// ─── 1. abuseipdbCheck — Check an IP address for abuse reports ───
export async function abuseipdbCheck(ip, maxAge = 90, verbose = false, apiKey) {
    requireApiKey(apiKey, "AbuseIPDB", "ABUSEIPDB_API_KEY");
    const params = new URLSearchParams({
        ipAddress: ip,
        maxAgeInDays: String(maxAge),
    });
    if (verbose) {
        params.set("verbose", "");
    }
    return abuseipdbFetch(`/check?${params.toString()}`, apiKey);
}
// ─── 2. abuseipdbReports — Get individual abuse reports for an IP ───
export async function abuseipdbReports(ip, maxAge = 90, limit = 25, apiKey) {
    requireApiKey(apiKey, "AbuseIPDB", "ABUSEIPDB_API_KEY");
    const params = new URLSearchParams({
        ipAddress: ip,
        maxAgeInDays: String(maxAge),
        perPage: String(limit),
    });
    return abuseipdbFetch(`/reports?${params.toString()}`, apiKey);
}
// ─── 3. abuseipdbBlacklist — Get AbuseIPDB blacklist of most reported IPs ───
export async function abuseipdbBlacklist(confidence = 90, limit = 100, apiKey) {
    requireApiKey(apiKey, "AbuseIPDB", "ABUSEIPDB_API_KEY");
    const params = new URLSearchParams({
        confidenceMinimum: String(confidence),
        limit: String(limit),
    });
    return abuseipdbFetch(`/blacklist?${params.toString()}`, apiKey, true);
}
// ─── 4. abuseipdbCheckBlock — Check an entire CIDR network block ───
export async function abuseipdbCheckBlock(network, maxAge = 30, apiKey) {
    requireApiKey(apiKey, "AbuseIPDB", "ABUSEIPDB_API_KEY");
    const params = new URLSearchParams({
        network,
        maxAgeInDays: String(maxAge),
    });
    return abuseipdbFetch(`/check-block?${params.toString()}`, apiKey);
}
//# sourceMappingURL=index.js.map