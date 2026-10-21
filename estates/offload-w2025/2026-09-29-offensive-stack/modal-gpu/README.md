# Modal GPU bench tier (credential-ready, staged-a per grill Q1c)

## What exists here
- `bench_modal_app.py` — Modal app: vLLM OpenAI-compatible server for
  Qwen3-4B-Instruct on an **L4**, weights cached in a Modal Volume
  (`estate-bench-weights`), `max_containers=1`, 5-min scaledown (serial-friendly).
- `providers-modal-qwen3-4b.json` — bench provider config (copy to
  `D:\opt\sandbox-agents\providers\` after filling the deployed URL).
- `deploy.ps1` — one-command deploy once credentials are live.

## Credentials (the one missing piece)
`MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` (+ `_474a0e`/`_3d3c42` account
variants). Located but value-blocked: names are indexed in the vault's
SECRET_INDEX_ALL; **values are git-crypt-encrypted** in
`Prekzursil/advver-m14-chk tools/mcp/cloud-hub/accounts.json` — home-only
(the VM-side link is restored; home itself must be up, or the owner pastes
the tokens, or `modal token new` from a logged-in browser).

## Bring-up (when creds land)
1. `setx MODAL_TOKEN_ID <id>` + `setx MODAL_TOKEN_SECRET <secret>` (user env).
2. `powershell -File deploy.ps1` → prints the `…modal.direct` URL.
3. Paste URL into the provider json, set `"enabled": true`, copy to
   `D:\opt\sandbox-agents\providers\modal-qwen3-4b.json`.
4. Verify: `C:\Python314\python.exe verify.py` (health + 1-token completion).
5. Record sha8+plaintext in `~/.config/cyberstrike/SSOT-secrets.md`.
6. First bench run: `bench.py --provider modal-qwen3-4b` (own table, I2 rules).

## Cost/scale notes (grill red-team)
L4 ≈ $0.80/hr-class, per-second billing, 20 serial tasks ≈ 15-25 min
(container warm across tasks via scaledown window) → well under $1 per full
table. No plan-quota dry-up mode → single active token; the second account
stays a cold spare, not a rotation pair (unlike zai-keys).

## Existing estate Modal infrastructure worth reusing later (stage-b)
`advver-m14-chk tools/mcp/cloud-hub/modal-mcp/` — home's Modal MCP wrapper
with per-invocation account/profile rotation, stdio purity, destructive-op
gating, local cost estimator. When stage-b (general elastic-GPU lane) is
wanted, wire THAT as the gateway backend rather than writing a second one.
