// Optional online citation verifier logic (used by the dist/verify-citation.js
// CLI, never an eighth MCP tool). Redirects are disabled; the initial URL and
// every redirect target are validated (HTTPS, allowlisted host, no userinfo/port,
// DNS not loopback/link-local/private) BEFORE contact. All network + clock
// primitives are injected so the policy is deterministic and testable.

import { CANONICAL_HOST_CLOUD, CANONICAL_HOST_MAIN } from "./provenance.js";
import { VERIFY_MAX_REDIRECT_HOPS } from "./limits.js";
import { matchGroup } from "./util.js";

export interface HttpResponse {
  status: number;
  location: string | null;
  body: string;
}

export interface VerifyDeps {
  fetchNoRedirect: (url: string) => Promise<HttpResponse>;
  resolveIps: (hostname: string) => Promise<string[]>;
  now: () => Date;
}

export interface CitationInput {
  canonical_url: string;
  title: string | null;
  heading: string | null;
}

export interface VerifyResult {
  verification: "verified" | "unverified" | "drifted";
  canonical_url: string;
  checked_at: string;
  status: number | null;
  title_match: boolean;
  heading_match: boolean;
  redirect_hops: string[];
  failure_code: string | null;
}

const ALLOWED_HOSTS = new Set([CANONICAL_HOST_MAIN, CANONICAL_HOST_CLOUD]);

// IPv4 private/loopback/link-local + IPv6 loopback/link-local/unique-local.
export function isDisallowedIp(ip: string): boolean {
  if (ip === "::1") {
    return true;
  }
  if (ip.startsWith("fe80:") || ip.startsWith("fc") || ip.startsWith("fd")) {
    return true;
  }
  const m = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/.exec(ip);
  if (m === null) {
    return false;
  }
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (a === 127 || a === 10 || a === 0) {
    return true;
  }
  if (a === 169 && b === 254) {
    return true;
  }
  if (a === 192 && b === 168) {
    return true;
  }
  if (a === 172 && b >= 16 && b <= 31) {
    return true;
  }
  return false;
}

async function validateTarget(
  rawUrl: string,
  resolveIps: (hostname: string) => Promise<string[]>,
): Promise<{ ok: true } | { ok: false }> {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    return { ok: false };
  }
  if (url.protocol !== "https:") {
    return { ok: false };
  }
  if (url.username !== "" || url.password !== "") {
    return { ok: false };
  }
  if (url.port !== "") {
    return { ok: false };
  }
  if (!ALLOWED_HOSTS.has(url.hostname)) {
    return { ok: false };
  }
  const ips = await resolveIps(url.hostname);
  for (const ip of ips) {
    if (isDisallowedIp(ip)) {
      return { ok: false };
    }
  }
  return { ok: true };
}

const TITLE_RE = /<title>([^<]*)<\/title>/i;
const CANONICAL_RE = /<link\s+rel="canonical"\s+href="([^"]*)"/i;

function bodyTitleMatches(body: string, expected: string): boolean {
  const m = TITLE_RE.exec(body);
  if (m === null) {
    return false;
  }
  const title = matchGroup(m, 1).toLowerCase();
  if (/page not found/i.test(title)) {
    return false;
  }
  return title.includes(expected.toLowerCase());
}

function bodyCanonicalMatches(body: string, expected: string): boolean {
  const m = CANONICAL_RE.exec(body);
  if (m === null) {
    return false;
  }
  return matchGroup(m, 1) === expected;
}

function fail(
  base: Omit<VerifyResult, "verification" | "failure_code">,
  failureCode: string,
): VerifyResult {
  return { ...base, verification: "unverified", failure_code: failureCode };
}

export async function verifyCitation(
  input: CitationInput,
  deps: VerifyDeps,
): Promise<VerifyResult> {
  const base: Omit<VerifyResult, "verification" | "failure_code"> = {
    canonical_url: input.canonical_url,
    checked_at: deps.now().toISOString(),
    status: null,
    title_match: false,
    heading_match: false,
    redirect_hops: [],
  };
  let currentUrl = input.canonical_url;
  const hops: string[] = [];
  let response: HttpResponse | null = null;
  for (let hop = 0; hop <= VERIFY_MAX_REDIRECT_HOPS; hop++) {
    const target = await validateTarget(currentUrl, deps.resolveIps);
    if (!target.ok) {
      return fail({ ...base, redirect_hops: hops }, "citation_unverified");
    }
    const res = await deps.fetchNoRedirect(currentUrl);
    if (res.status >= 300 && res.status < 400) {
      if (res.location === null) {
        return fail({ ...base, status: res.status, redirect_hops: hops }, "citation_unverified");
      }
      hops.push(res.location);
      currentUrl = res.location;
      continue;
    }
    response = res;
    break;
  }
  if (response === null) {
    return fail({ ...base, redirect_hops: hops }, "citation_unverified");
  }
  const withStatus = { ...base, status: response.status, redirect_hops: hops };
  if (response.status !== 200) {
    return fail(withStatus, "citation_unverified");
  }
  if (currentUrl.endsWith("/404.html")) {
    return fail(withStatus, "citation_unverified");
  }
  const titleMatch =
    input.title === null ? true : bodyTitleMatches(response.body, input.title);
  const headingMatch =
    input.heading === null
      ? true
      : response.body.toLowerCase().includes(input.heading.toLowerCase());
  const resolved = { ...withStatus, title_match: titleMatch, heading_match: headingMatch };
  if (!titleMatch || !headingMatch) {
    return { ...resolved, verification: "unverified", failure_code: "citation_unverified" };
  }
  if (!bodyCanonicalMatches(response.body, input.canonical_url)) {
    return { ...resolved, verification: "drifted", failure_code: null };
  }
  return { ...resolved, verification: "verified", failure_code: null };
}
