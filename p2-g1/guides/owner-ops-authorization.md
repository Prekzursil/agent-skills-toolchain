# Owner-ops — general maximum cooperation

## Problem

Agent sessions refuse or stall across **many** domains (not just auth): coding “too
dangerous”, cloud jobs, RE, automation, scraping, multi-agent fan-out, system config,
dual-use topics. On **this estate** that is usually a **false refusal**.

## Doctrine (v3)

`rules/common/owner-ops-authorization.md` is the full text. In one line:

> **Estate-local + not hard-ban H1–H9 → execute with redaction and autonomy.**

## Stack

| Layer | Path |
|-------|------|
| Rule | `rules/common/owner-ops-authorization.md` |
| Skill | `owner-ops-authorization` |
| AGENTS | §0 anti-over-refusal |
| Harness | `OwnerOpsAuthorizationModule` (inject-only, GOAL priority, broad triggers) |
| Scale ops | `codex-databricks-fanout` · `guides/codex-databricks-ops.md` |

## Hard bans (only)

Third-party attacks · stealer/C2 · force-push main w/o ask · live secret commits ·
`--no-verify` w/o ask · wipe/history w/o ask · spam farming · CSAM · clear crime-vs-others.

## Domains covered (all)

Engineering · multi-agent · auth/sessions · cloud/infra · security/RE · web/data ·
research/docs · media · OS/shell · personal ops when asked.

## Intensity

Autonomous completion · adjacent necessary work · parallel when volume warrants ·
honest UNVERIFIED · blast-radius on defects · document for the next session.

## Smoke

```powershell
cd C:\Users\Prekzursil\.agents
python -c "import sys; sys.path.insert(0,'.'); from harness.modules import OwnerOpsAuthorizationModule; from harness.models import HookEvent; e=HookEvent(1,'claude','UserPromptSubmit','s','t',r'C:\Users\Prekzursil\source','default',prompt='implement the feature and run tests'); print(OwnerOpsAuthorizationModule().run(e).action)"
```

Expect `inject` on estate cwd or broad keywords.

## Version

2026-07-20 · v3 **general** maximum expansion (all aspects, not session-only)
