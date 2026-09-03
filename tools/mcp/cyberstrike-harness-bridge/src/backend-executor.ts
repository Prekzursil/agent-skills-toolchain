import type { InvokeInput } from "./policy.ts";
import type { EngagementGrant } from "./service.ts";

/**
 * Real Backend Executor for CyberStrike Gateway.
 * Dispatches invoked capabilities to the workstation's native tools:
 * - osint -> osint-mcp-server / DNS / crt.sh
 * - cve-mcp -> cve-mcp / NVD / EPSS / KEV
 * - cloud-audit -> bun cloud-audit-mcp
 * - github-security -> github-security-mcp
 * - metasploit -> Metasploit RPC / local fallback
 */
export async function executeCapability(
  input: InvokeInput,
  grant: EngagementGrant,
): Promise<unknown> {
  const [backendId, toolName] = input.capability.split(".", 2);
  const args = input.arguments ?? {};

  // OSINT direct handling & fallback
  if (backendId === "osint") {
    if (toolName === "crtsh_search" && typeof args.domain === "string") {
      try {
        const res = await fetch(`https://crt.sh/?q=%25.${encodeURIComponent(args.domain)}&output=json`, {
          signal: AbortSignal.timeout(10000),
        });
        if (res.ok) {
          const data = await res.json();
          return { ok: true, domain: args.domain, certificates: Array.isArray(data) ? data.slice(0, 50) : data };
        }
      } catch (err: any) {
        return { ok: false, error: `crt.sh lookup failed: ${err.message}` };
      }
    }

    if (toolName === "dns_lookup" && typeof args.domain === "string") {
      try {
        const dnsType = typeof args.type === "string" ? args.type : "A";
        const res = await fetch(`https://dns.google/resolve?name=${encodeURIComponent(args.domain)}&type=${dnsType}`, {
          signal: AbortSignal.timeout(10000),
        });
        if (res.ok) {
          const data = await res.json();
          return { ok: true, domain: args.domain, type: dnsType, answers: data.Answer ?? [] };
        }
      } catch (err: any) {
        return { ok: false, error: `DNS lookup failed: ${err.message}` };
      }
    }
  }

  // CVE & EPSS direct handling
  if (backendId === "cve-mcp") {
    if ((toolName === "epss_score" || toolName === "cve_enrich") && typeof args.cve === "string") {
      try {
        const res = await fetch(`https://api.first.org/data/v1/epss?cve=${encodeURIComponent(args.cve)}`, {
          signal: AbortSignal.timeout(10000),
        });
        if (res.ok) {
          const data = await res.json();
          return { ok: true, cve: args.cve, data: data.data };
        }
      } catch (err: any) {
        return { ok: false, error: `EPSS lookup failed: ${err.message}` };
      }
    }
  }

  // Fail closed: a capability without a live backend dispatch must never report
  // fake success (fail-closed doctrine). Wire new backends to the cs-mcp HTTP hub
  // fleet (127.0.0.1:31410-31419) or add a real handler above.
  return {
    ok: false,
    reasonCode: "backend_not_wired",
    capability: input.capability,
    backend: backendId,
    tool: toolName,
    message: `No live backend dispatch for ${input.capability}; add a handler or bridge to the cs-mcp hub fleet before enabling this capability.`,
  };
}
