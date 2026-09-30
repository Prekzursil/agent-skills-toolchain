// Hudson Rock Cavalier — Stealer log intelligence provider
// Tools: stealerDomain, stealerEmail, stealerIp
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
import { requireApiKey } from "../utils/require-key.js";
// ─── Constants ───
const BASE_URL = "https://cavalier.hudsonrock.com/api/json/v2";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(2000);
const cache = new TTLCache(10 * 60 * 1000); // 10 min
// ─── Helpers ───
async function hudsonrockFetch(path, apiKey) {
    const cacheKey = `hudsonrock:${path}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const url = `${BASE_URL}${path}`;
    const separator = path.includes("?") ? "&" : "?";
    const fullUrl = `${url}${separator}api-key=${encodeURIComponent(apiKey)}`;
    const response = await fetch(fullUrl, {
        headers: {
            Accept: "application/json",
        },
    });
    if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`Hudson Rock API error: HTTP ${response.status} ${response.statusText} — ${body}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 1. stealerDomain — Search stealer logs by domain ───
export async function stealerDomain(domain, apiKey) {
    requireApiKey(apiKey, "Hudson Rock", "HUDSONROCK_API_KEY");
    const params = new URLSearchParams({ domain });
    return hudsonrockFetch(`/osint-tools/search-by-domain?${params.toString()}`, apiKey);
}
// ─── 2. stealerEmail — Search stealer logs by email ───
export async function stealerEmail(email, apiKey) {
    requireApiKey(apiKey, "Hudson Rock", "HUDSONROCK_API_KEY");
    const params = new URLSearchParams({ email });
    return hudsonrockFetch(`/osint-tools/search-by-email?${params.toString()}`, apiKey);
}
// ─── 3. stealerIp — Search stealer logs by IP address ───
export async function stealerIp(ip, apiKey) {
    requireApiKey(apiKey, "Hudson Rock", "HUDSONROCK_API_KEY");
    const params = new URLSearchParams({ ip });
    return hudsonrockFetch(`/osint-tools/search-by-ip?${params.toString()}`, apiKey);
}
//# sourceMappingURL=index.js.map