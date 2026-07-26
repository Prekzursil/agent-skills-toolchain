import assert from "node:assert/strict";
import { test } from "node:test";

import { isDisallowedIp, verifyCitation } from "../dist/verify.js";

test("isDisallowedIp covers loopback, link-local, private and public ranges", () => {
  for (const ip of [
    "::1",
    "fe80::1",
    "fc00::1",
    "fd12::1",
    "127.0.0.1",
    "10.1.2.3",
    "0.0.0.0",
    "169.254.1.1",
    "192.168.1.1",
    "172.16.0.1",
    "172.20.0.1",
  ]) {
    assert.equal(isDisallowedIp(ip), true, ip);
  }
  for (const ip of [
    "2606:4700::1",
    "8.8.8.8",
    "169.1.1.1",
    "192.1.1.1",
    "172.15.0.1",
    "172.40.0.1",
    "not-an-ip",
  ]) {
    assert.equal(isDisallowedIp(ip), false, ip);
  }
});

const NOW = "2026-01-02T03:04:05.000Z";
const HOST = "https://hacktricks.wiki/en/x.html";

function deps(fetchImpl, ips = ["93.184.216.34"]) {
  return {
    fetchNoRedirect: fetchImpl,
    resolveIps: async () => ips,
    now: () => new Date(NOW),
  };
}

const okBody =
  '<title>SSRF Page</title><link rel="canonical" href="https://hacktricks.wiki/en/x.html">Redirect to Gopher';

test("verifyCitation returns verified for a matching page", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({ status: 200, location: null, body: okBody })),
  );
  assert.equal(result.verification, "verified");
  assert.equal(result.failure_code, null);
  assert.equal(result.status, 200);
  assert.equal(result.checked_at, NOW);
  assert.equal(result.title_match, true);
  assert.equal(result.heading_match, true);
});

test("verifyCitation treats null title/heading as satisfied", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(async () => ({ status: 200, location: null, body: okBody })),
  );
  assert.equal(result.verification, "verified");
});

test("verifyCitation drifts when the canonical link differs or is missing", async () => {
  const differs = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({
      status: 200,
      location: null,
      body: '<title>SSRF Page</title><link rel="canonical" href="https://hacktricks.wiki/en/other.html">Redirect',
    })),
  );
  assert.equal(differs.verification, "drifted");
  assert.equal(differs.failure_code, null);

  const missing = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({ status: 200, location: null, body: "<title>SSRF Page</title>Redirect" })),
  );
  assert.equal(missing.verification, "drifted");
});

test("verifyCitation is unverified on title/heading mismatch and soft-404 title", async () => {
  const titleMiss = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({ status: 200, location: null, body: "<title>Other</title>Redirect" })),
  );
  assert.equal(titleMiss.verification, "unverified");

  const noTitleTag = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({ status: 200, location: null, body: "no title tag here Redirect" })),
  );
  assert.equal(noTitleTag.verification, "unverified");

  const pageNotFound = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Redirect" },
    deps(async () => ({ status: 200, location: null, body: "<title>Page not found</title>Redirect" })),
  );
  assert.equal(pageNotFound.verification, "unverified");

  const headingMiss = await verifyCitation(
    { canonical_url: HOST, title: "SSRF", heading: "Missing" },
    deps(async () => ({ status: 200, location: null, body: okBody })),
  );
  assert.equal(headingMiss.verification, "unverified");
});

test("verifyCitation is unverified for a non-200 status", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(async () => ({ status: 500, location: null, body: "" })),
  );
  assert.equal(result.verification, "unverified");
  assert.equal(result.failure_code, "citation_unverified");
  assert.equal(result.status, 500);
});

test("verifyCitation rejects a soft-404 path", async () => {
  const result = await verifyCitation(
    { canonical_url: "https://hacktricks.wiki/en/404.html", title: null, heading: null },
    deps(async () => ({ status: 200, location: null, body: okBody })),
  );
  assert.equal(result.verification, "unverified");
});

test("verifyCitation follows a validated redirect and records hops", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(async (url) => {
      if (url === HOST) {
        return { status: 301, location: "https://hacktricks.wiki/en/moved.html", body: "" };
      }
      return {
        status: 200,
        location: null,
        body: '<link rel="canonical" href="https://hacktricks.wiki/en/x.html">',
      };
    }),
  );
  assert.equal(result.redirect_hops.length, 1);
  assert.equal(result.redirect_hops[0], "https://hacktricks.wiki/en/moved.html");
});

test("verifyCitation fails a redirect without a Location", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(async () => ({ status: 302, location: null, body: "" })),
  );
  assert.equal(result.verification, "unverified");
  assert.equal(result.status, 302);
});

test("verifyCitation fails after too many redirect hops", async () => {
  const result = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(async () => ({ status: 301, location: HOST, body: "" })),
  );
  assert.equal(result.verification, "unverified");
});

test("verifyCitation rejects unsafe targets before contact", async () => {
  const fetchGuard = async () => {
    throw new Error("must not fetch an unsafe target");
  };
  const badUrl = await verifyCitation(
    { canonical_url: "not a url", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(badUrl.verification, "unverified");

  const http = await verifyCitation(
    { canonical_url: "http://hacktricks.wiki/x", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(http.verification, "unverified");

  const userinfo = await verifyCitation(
    { canonical_url: "https://user@hacktricks.wiki/x", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(userinfo.verification, "unverified");

  const passwordOnly = await verifyCitation(
    { canonical_url: "https://:pw@hacktricks.wiki/x", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(passwordOnly.verification, "unverified");

  const port = await verifyCitation(
    { canonical_url: "https://hacktricks.wiki:8443/x", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(port.verification, "unverified");

  const badHost = await verifyCitation(
    { canonical_url: "https://evil.example/x", title: null, heading: null },
    deps(fetchGuard),
  );
  assert.equal(badHost.verification, "unverified");

  const rebind = await verifyCitation(
    { canonical_url: HOST, title: null, heading: null },
    deps(fetchGuard, ["127.0.0.1"]),
  );
  assert.equal(rebind.verification, "unverified");
});
