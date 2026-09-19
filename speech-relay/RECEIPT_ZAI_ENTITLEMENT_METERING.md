# Z.AI entitlement & metering architecture receipt — 2026-09-19 07:53 (operator's own keys)
## Channels on this box
1. Coding-Plan speech channel (video-agent-kit 'online'):
   - Endpoint POST {ZCODE_BASE_URL}/api/v1/mcp/server/video_edit (Streamable HTTP MCP)
   - Auth: per-call JWT identity headers via MCP _meta 'com.zcode/official-mcp-auth';
     minted by ZCode host from Coding Plan; Start/API-key connections ineligible
   - Metering: server-side on the plan. No client-visible quota headers; client sees
     success/failure + request ids only. 401-after-rotation is by design (no in-proc retry).
2. Model API (operator keys):
   - ZAI_API_KEY_realprekzursil sha8:2b98b9a3 len 49 -> measured HTTP 429
     (Too Many Requests) on 2026-09-19 07:53: rate/quota-limited at server; error carries only
     X-LOG-ID / X-Request-ID; NO rate-limit or remaining-quota headers exposed.
   - ZAI_API_KEY sha8:2cbe00c7 len 49 -> measured HTTP 200 glm-4.7-flash;
     usage block per response (prompt/completion/total tokens, cached-token detail);
     NO rate/quota headers. Metering visibility = per-response usage + 429s, nothing else.
## Metering enforcement summary (client-visible evidence)
- All enforcement is server-side: plan entitlement via per-call JWTs; Model API via
  per-key accounting surfaced only as 429 + per-response usage blocks.
- No client-side meter state, no quota headers, no offline grace: nothing to disable
  or buffer locally; 'unmetered' locally means the offline whisper channel only.
## Keys persisted
- Plaintext + sha8: D:olt\credentials\ZAI_KEYS_SOT.json (gitignored, verified
  credentials/*.json ignored by .gitignore:65; repo bolt_security_training PRIVATE)
