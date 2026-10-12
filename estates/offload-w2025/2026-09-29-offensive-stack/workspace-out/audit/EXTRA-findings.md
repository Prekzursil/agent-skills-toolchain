# Extra audit findings (owner-side, 2026-09-29)

Findings surfaced outside the four workflow audit lanes. The audit-fixes
implementer MUST fold these into its pass.

## F1 — firecrawl self-host: dead entry + port collision (HIGH, kind: risk + stale + unwired)

- **Where:** `~/.agents/agents.json` → `mcp.servers.firecrawl`
- **Evidence:** entry was `enabled: true` → `http://127.0.0.1:31114/mcp`; probe of
  `:31114` → connection refused (nothing listening). Documented backing stack
  ("self-host docker stack :3002, no credits") is gone, and `:3002` is NOW
  decepticon-initial-access (FastMCP, verified HTTP 200 on /mcp) — a live port
  collision if the self-host ever returns on its documented port.
- **Inverted doctrine:** entry claimed "Hosted lane auto-restores after 09-16 by
  clearing FIRECRAWL_API_URL" — wrong direction: the gateway front treats
  FIRECRAWL_API_URL as the SELF-HOST switch; the cloud lane needs
  FIRECRAWL_API_KEY set (it is, verified HTTP 200 on 2026-09-29).
- **Status:** FIXED (owner-side) — entry parked `enabled: false`, tags
  `parked/dead-port/port-collision-3002`, description rewritten with the revival
  path. Revival staged at `D:\opt\firecrawl-selfhost` (docker-pending, external
  port 31115 to avoid the collision). No further action required unless the
  docker era begins, at which point: bring up the compose, then
  `setx FIRECRAWL_API_URL http://127.0.0.1:31115` — the gateway front
  (`fronts/firecrawl.py`) flips to self-hosted automatically, zero code changes.
