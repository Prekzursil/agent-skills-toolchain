# SSH nonce E2E — 2026-07-20

## Nonce
`SSH-CROSSVENDOR-E2E-20260720-A7F3`

## SSH inventory
- ssh.exe present (OpenSSH-Win64 + System32)
- `~/.ssh/config` Hosts:
  - `ssh.lightning.ai` only (Lightning Studios)
- **No Claude / Codex / cross-vendor SSH Host** configured for nonce rail

## Attempts
| Target | Result |
|--------|--------|
| Local echo | SUCCESS: `SSH-CROSSVENDOR-E2E-20260720-A7F3` |
| ssh.lightning.ai BatchMode | `Warning: Permanently added 'ssh.lightning.ai' (RSA) to the list of known hosts.
prekzursil@ssh.lightning.ai: Permission denied (publickey).` |

## Verdict
SSH-CROSSVENDOR rail **not available** as a Claude peer endpoint on this host.
Local nonce echo recorded for ledger continuity. Configure a Claude SSH host if required later.
