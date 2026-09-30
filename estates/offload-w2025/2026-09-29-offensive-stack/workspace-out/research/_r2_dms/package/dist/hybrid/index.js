// Hybrid Analysis — Malware sandbox analysis provider
// Tools: malwareSearch, malwareOverview, malwareFeed
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
import { requireApiKey } from "../utils/require-key.js";
// ─── Constants ───
const BASE_URL = "https://hybrid-analysis.com/api/v2";
const USER_AGENT = "Falcon Sandbox";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(1000);
const cache = new TTLCache(15 * 60 * 1000); // 15 min
// ─── Helpers ───
function hybridHeaders(apiKey) {
    return {
        "api-key": apiKey,
        "User-Agent": USER_AGENT,
        Accept: "application/json",
    };
}
// ─── 1. malwareSearch — Search by file hash ───
export async function malwareSearch(hash, apiKey) {
    requireApiKey(apiKey, "Hybrid Analysis", "HYBRID_API_KEY");
    const cacheKey = `hybrid:search:${hash}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const formData = new URLSearchParams({ hash });
    const response = await fetch(`${BASE_URL}/search/hash`, {
        method: "POST",
        headers: {
            ...hybridHeaders(apiKey),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Hybrid Analysis API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 2. malwareOverview — Get full analysis overview for a SHA256 ───
export async function malwareOverview(sha256, apiKey) {
    requireApiKey(apiKey, "Hybrid Analysis", "HYBRID_API_KEY");
    const cacheKey = `hybrid:overview:${sha256}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(`${BASE_URL}/overview/${encodeURIComponent(sha256)}`, {
        headers: hybridHeaders(apiKey),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Hybrid Analysis API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 3. malwareFeed — Get latest 250 malware detonations ───
export async function malwareFeed(apiKey) {
    requireApiKey(apiKey, "Hybrid Analysis", "HYBRID_API_KEY");
    const cacheKey = "hybrid:feed:latest";
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(`${BASE_URL}/feed/latest`, {
        headers: hybridHeaders(apiKey),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Hybrid Analysis API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
//# sourceMappingURL=index.js.map