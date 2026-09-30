// Vulners — Vulnerability and exploit database provider
// Tools: vulnersSearch, vulnersId, vulnersExploit
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
// ─── Constants ───
const BASE_URL = "https://vulners.com/api/v3";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(1000);
const cache = new TTLCache(10 * 60 * 1000); // 10 min
// ─── 1. vulnersSearch — Search vulnerability database ───
export async function vulnersSearch(query, limit = 20, apiKey) {
    const cacheKey = `vulners:search:${query}:${limit}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const body = {
        query,
        size: limit,
    };
    if (apiKey) {
        body.apiKey = apiKey;
    }
    const response = await fetch(`${BASE_URL}/search/lucene/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`Vulners API error: HTTP ${response.status} ${response.statusText} — ${text}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 2. vulnersId — Lookup a specific vulnerability by ID (free, no key) ───
export async function vulnersId(id) {
    const cacheKey = `vulners:id:${id}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const params = new URLSearchParams({ id });
    const response = await fetch(`${BASE_URL}/search/id/?${params.toString()}`, {
        headers: {
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`Vulners API error: HTTP ${response.status} ${response.statusText} — ${text}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 3. vulnersExploit — Search for exploits specifically ───
export async function vulnersExploit(query, limit = 20, apiKey) {
    const exploitQuery = `type:exploitdb AND ${query}`;
    const cacheKey = `vulners:exploit:${query}:${limit}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const body = {
        query: exploitQuery,
        size: limit,
    };
    if (apiKey) {
        body.apiKey = apiKey;
    }
    const response = await fetch(`${BASE_URL}/search/lucene/`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
        },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`Vulners API error: HTTP ${response.status} ${response.statusText} — ${text}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
//# sourceMappingURL=index.js.map