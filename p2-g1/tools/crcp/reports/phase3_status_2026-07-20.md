# Phase 3 Status — 20.07.2026

## Priority results

| # | Item | Status |
|---|------|--------|
| 1 | Live polling bridge | **DONE** — `python -m crcp chatgpt live` + HTTP :8820 |
| 6 | Token watcher | **DONE** — `python -m crcp auth watch` + health TTL |
| 4 | Grok on bus | **DONE** — IvoryBarn → VioletTower + OrangeCreek |
| 3 | Write path | **INVESTIGATED** — not 403; 422 body schema; init 200 |
| 2 | Databricks relay | **DONE** starter — `databricks/crcp_chatgpt_relay.py` |
| 5 | Stream reconnect | **DOCUMENTED** research — REST poll is production path |

## Live bridge

```powershell
$env:PYTHONPATH = "$HOME\source\agent-skills-toolchain\tools\crcp"
python -m crcp chatgpt live --poll-interval 60
# status: http://127.0.0.1:8820/health
# force:  POST http://127.0.0.1:8820/poll-now
python -m crcp chatgpt live --once   # single cycle
```

Smoke: first cycle listed 4 convos, fetched all deltas, published 4 envelopes via BoldCat.

## Grok three-way

- Grok agent: IvoryBarn (program grok-node)
- Marker received by VioletTower (Claude) and OrangeCreek (Codex)
- Report: reports/bus_three_way_proof.json

## Write path finding

- Codex OAuth scopes: openid profile email offline_access api.connectors.read api.connectors.invoke
- POST conversation → **422** Invalid body (auth accepted)
- POST conversation/init → **200**
- Not a simple missing-scope 403; body/schema RE is next for send

## Auth TTL in health

`mon crcp` / `python -m crcp health` shows e.g. `ttl=229.9h age=0.421d stale8d=False`
