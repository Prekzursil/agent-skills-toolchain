# Firecrawl self-host (staged, docker-pending)

Revival of the estate's local firecrawl lane — the one that died with the old
stack and whose registry entry is now parked (see `out/audit/EXTRA-findings.md`
F1 in the workflow workspace).

## Why staged, not running
This VM has no Docker engine yet (GCP, no nested virt — decision pending).
Firecrawl self-host is a container stack (api + workers + redis + postgres +
playwright service); there is no realistic native-Windows path.

## Bring-up (when Docker exists)
```powershell
cd D:\opt\firecrawl-selfhost
docker compose up -d        # pulls firecrawl/* images on first run
# wait for healthy, then:
setx FIRECRAWL_API_URL http://127.0.0.1:31115
```
The gateway firecrawl front prefers `FIRECRAWL_API_URL` over the cloud key
automatically (`fronts/firecrawl.py` dual-mode contract) — no code changes.

## Port
External **31115** (remapped from the stack's internal 3002). The old
documented port 3002 now belongs to decepticon-initial-access — do not reuse.

## After it is healthy
1. Re-enable `mcp.servers.firecrawl` in `~/.agents/agents.json` pointing at a
   live MCP proxy for it (or simply consume the gateway backend).
2. Remove the `parked` tags and update the description.
3. Cloud key stays as fallback: unset FIRECRAWL_API_URL → cloud mode returns.
