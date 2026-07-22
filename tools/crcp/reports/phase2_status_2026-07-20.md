# Phase 2 Status — 20.07.2026

## Delivered

| Feature | Command | Status |
|---------|---------|--------|
| Drop-folder ingest | `python -m crcp inbox scan` | DONE |
| Watch mode | `python -m crcp inbox scan --watch` | DONE |
| Linear + mapping export shapes | auto-detect | DONE (fixed linear `messages[]`) |
| Publish to agent-mail | `python -m crcp publish` | DONE |
| mon crcp health | `mon crcp` | Registered |

## Smoke

- inbox scan processed drop → outbox envelope
- publish → sender `BoldCat` (crcp-bridge) → recipients OrangeCreek, VioletTower
- agent-mail deliveries id 24+ confirmed

## Paths

- inbox: `tools/crcp/inbox/chatgpt/`
- processed: `tools/crcp/inbox/chatgpt/processed/`
- outbox: `tools/crcp/outbox/`
- mon: `~/.agents/skills/crcp-health/` + `[crcp]` in monitors.toml
