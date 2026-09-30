// IntelligenceX — Dark web data search and phonebook provider
// Tools: intelxSearch, intelxSearchResults, intelxPhonebook, intelxPhonebookResults
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
import { requireApiKey } from "../utils/require-key.js";
// ─── Constants ───
const BASE_URL = "https://2.intelx.io";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(2000);
const cache = new TTLCache(5 * 60 * 1000); // 5 min
// ─── Helpers ───
function intelxHeaders(apiKey) {
    return {
        "x-key": apiKey,
        "Content-Type": "application/json",
        Accept: "application/json",
    };
}
// ─── 1. intelxSearch — Initiate an IntelligenceX search ───
export async function intelxSearch(term, maxResults = 100, apiKey) {
    requireApiKey(apiKey, "IntelligenceX", "INTELX_API_KEY");
    const cacheKey = `intelx:search:${term}:${maxResults}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(`${BASE_URL}/intelligent/search`, {
        method: "POST",
        headers: intelxHeaders(apiKey),
        body: JSON.stringify({
            term,
            maxresults: maxResults,
            media: 0,
            timeout: 10,
        }),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`IntelligenceX search error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 2. intelxSearchResults — Retrieve results for a search ID ───
export async function intelxSearchResults(id, offset = 0, limit = 100, apiKey) {
    requireApiKey(apiKey, "IntelligenceX", "INTELX_API_KEY");
    const cacheKey = `intelx:results:${id}:${offset}:${limit}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const params = new URLSearchParams({
        id,
        offset: String(offset),
        limit: String(limit),
    });
    const response = await fetch(`${BASE_URL}/intelligent/search/result?${params.toString()}`, {
        headers: intelxHeaders(apiKey),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`IntelligenceX results error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 3. intelxPhonebook — Initiate a phonebook search (emails, domains, URLs) ───
export async function intelxPhonebook(term, target = 0, maxResults = 100, apiKey) {
    requireApiKey(apiKey, "IntelligenceX", "INTELX_API_KEY");
    const cacheKey = `intelx:phonebook:${term}:${target}:${maxResults}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const response = await fetch(`${BASE_URL}/phonebook/search`, {
        method: "POST",
        headers: intelxHeaders(apiKey),
        body: JSON.stringify({
            term,
            target,
            maxresults: maxResults,
        }),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`IntelligenceX phonebook error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 4. intelxPhonebookResults — Retrieve phonebook search results ───
export async function intelxPhonebookResults(id, offset = 0, limit = 100, apiKey) {
    requireApiKey(apiKey, "IntelligenceX", "INTELX_API_KEY");
    const cacheKey = `intelx:phonebook-results:${id}:${offset}:${limit}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const params = new URLSearchParams({
        id,
        offset: String(offset),
        limit: String(limit),
    });
    const response = await fetch(`${BASE_URL}/phonebook/search/result?${params.toString()}`, {
        headers: intelxHeaders(apiKey),
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`IntelligenceX phonebook results error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
//# sourceMappingURL=index.js.map