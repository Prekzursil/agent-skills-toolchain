# Desktop authenticated write capture (Fiddler) — 2026-07-20

## Proof
- System proxy ON
- Session **250**: POST /backend-api/f/conversation → **200** 	ext/event-stream
- User message body text: . (minimal probe)
- Conversation id assigned: 6a5d8dd9-e298-8328-8e60-354316af9bc2

## Auth header stack (names only; tokens not stored)
| Header | Notes |
|--------|--------|
| Authorization | Bearer (same ChatGPT OAuth family as Codex) |
| chatgpt-account-id | account UUID |
| oai-did | device id |
| oai-language | en-US |
| originator | **Codex Browser** (chat) vs Codex Desktop (wham) |
| openai-sentinel-chat-requirements-**prepare**-token | from prepare endpoint |
| openai-sentinel-proof-token | client PoW |
| openai-sentinel-turnstile-token | client Turnstile |

## Body (auth first turn is leaner than guest web)
- ction=next, model=gpt-5-5, supported_encodings=[v1], timezone fields
- message object full role envelope (status, weight, recipient)
- **local_function_signatures** with Work-mode handoff tool
- **no** parent_message_id / conversation_id on this capture

## Sentinel path (paid Desktop/Browser)
1. POST /backend-api/sentinel/chat-requirements/prepare → persona chatgpt-paid + prepare_token
2. Client solves PoW + Turnstile **without** finalize round-trip (no finalize session observed)
3. Send with prepare-token + proof + turnstile headers

## Implication for CRCP
- Fix header name for auth: openai-sentinel-chat-requirements-prepare-token
- Still need browser/VM PoW+Turnstile generation (or short-lived capture-and-replay)
- Endpoint confirmed: /backend-api/f/conversation
