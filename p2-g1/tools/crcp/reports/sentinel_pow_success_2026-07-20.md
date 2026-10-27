# Sentinel PoW write-path — SUCCESS (2026-07-20)

## Proof
```text
python -m crcp chatgpt send --new "CRCP: reply PONG only"
→ success=true
→ POST /backend-api/f/conversation  200 text/event-stream
→ event_count=21
→ persona=chatgpt-paid
→ PoW ~73s (parallel threads), payload_mode=seed+s
```

## What works for paid accounts
1. `POST /backend-api/sentinel/chat-requirements/prepare` (empty `p` OK)
2. Local **sha3_512 PoW** → `openai-sentinel-proof-token` (`gAAAAAB` + b64 config)
3. Headers: `openai-sentinel-chat-requirements-prepare-token` + proof (+ optional turnstile)
4. Body: desktop_auth lean schema
5. **Turnstile flagged required but not needed** for this paid path

## Code
- `crcp/sentinel.py` — prepare + parallel PoW + acquire
- `crcp/write_path.py` — `send_message(auto_sentinel=True)` acquires tokens **last** before POST
- CLI: `python -m crcp chatgpt send "…"` / `--new`

## Notes
- PoW difficulty varies; solver retries prepare up to 3× and searches up to 80M iters
- Do not insert conduit prepare between sentinel and POST (invalidates short-lived tokens)
- Report: `reports/chatgpt_send_last.json`
