// Pulsedive — Community threat intelligence provider
// Tools: pulsediveIndicator, pulsediveSearch, pulsediveExplore
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
// ─── Constants ───
const BASE_URL = "https://pulsedive.com/api";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(1000);
const cache = new TTLCache(10 * 60 * 1000); // 10 min
// ─── Helpers ───
async function pulsediveFetch(path, params) {
    const cacheKey = `pulsedive:${path}?${params.toString()}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const url = `${BASE_URL}${path}?${params.toString()}`;
    const response = await fetch(url, {
        headers: {
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Pulsedive API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 1. pulsediveIndicator — Lookup an indicator (IP, domain, URL, hash) ───
export async function pulsediveIndicator(indicator, apiKey) {
    const params = new URLSearchParams({ indicator });
    if (apiKey)
        params.set("key", apiKey);
    return pulsediveFetch("/info.php", params);
}
// ─── 2. pulsediveSearch — Search indicators by value ───
export async function pulsediveSearch(query, apiKey) {
    const params = new URLSearchParams({ q: query });
    if (apiKey)
        params.set("key", apiKey);
    return pulsediveFetch("/search.php", params);
}
// ─── 3. pulsediveExplore — Explore linked indicators with queries ───
export async function pulsediveExplore(query, apiKey) {
    const params = new URLSearchParams({ q: query });
    if (apiKey)
        params.set("key", apiKey);
    return pulsediveFetch("/explore.php", params);
}
//# sourceMappingURL=index.js.map