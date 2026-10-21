// AlienVault OTX — Open Threat Exchange intelligence provider
// Tools: otxIp, otxDomain, otxHash, otxCve, otxSearchPulses
import { RateLimiter } from "../utils/rate-limiter.js";
import { TTLCache } from "../utils/cache.js";
// ─── Constants ───
const BASE_URL = "https://otx.alienvault.com/api/v1";
// ─── Rate Limiter & Cache ───
const limiter = new RateLimiter(1000);
const cache = new TTLCache(10 * 60 * 1000); // 10 min
// ─── Helpers ───
async function otxFetch(path, apiKey) {
    const cacheKey = `otx:${path}`;
    const cached = cache.get(cacheKey);
    if (cached)
        return cached;
    await limiter.acquire();
    const headers = {
        Accept: "application/json",
    };
    if (apiKey) {
        headers["X-OTX-API-KEY"] = apiKey;
    }
    const response = await fetch(`${BASE_URL}${path}`, { headers });
    if (!response.ok) {
        throw new Error(`OTX API error: HTTP ${response.status} ${response.statusText}`);
    }
    const data = (await response.json());
    cache.set(cacheKey, data);
    return data;
}
// ─── 1. otxIp — IP address general intelligence ───
export async function otxIp(ip, apiKey) {
    return otxFetch(`/indicators/IPv4/${encodeURIComponent(ip)}/general`, apiKey);
}
// ─── 2. otxDomain — Domain general intelligence ───
export async function otxDomain(domain, apiKey) {
    return otxFetch(`/indicators/domain/${encodeURIComponent(domain)}/general`, apiKey);
}
// ─── 3. otxHash — File hash general intelligence ───
export async function otxHash(hash, apiKey) {
    return otxFetch(`/indicators/file/${encodeURIComponent(hash)}/general`, apiKey);
}
// ─── 4. otxCve — CVE general intelligence ───
export async function otxCve(cve, apiKey) {
    return otxFetch(`/indicators/CVE/${encodeURIComponent(cve)}/general`, apiKey);
}
// ─── 5. otxSearchPulses — Search OTX pulses ───
export async function otxSearchPulses(query, limit = 10, apiKey) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return otxFetch(`/search/pulses?${params.toString()}`, apiKey);
}
//# sourceMappingURL=index.js.map