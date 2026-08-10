---
name: c2patool-provenance
description: "Use when c2patool provenance is needed. Read + attach C2PA / Content Credentials (cryptographic, tamper-evident content provenance) to images, video, and audio using c2patool. Use to VERIFY the provenance/manifest of a media file, or to SIGN your own AI-edited exports (reframe / watermark-removal."
license: 'c2patool is Apache-2.0 / MIT (Content Authenticity Initiative).'
---

# c2patool-provenance — read & sign C2PA / Content Credentials

C2PA (Content Credentials) embeds a signed, tamper-evident manifest into a media file recording
who/what produced or edited it (claim generator, actions, ingredients, author). Use c2patool to
READ a file's provenance, or to SIGN your own exports with an origin claim — relevant for AI-edited
media disclosure (EU AI Act Art.50, applies 2026-08-02) and authenticity.

## Binary

`~/.local/bin/c2patool.exe` (v0.9.12, prebuilt release). NOTE: `cargo install c2patool` (0.26.x)
FAILS to source-compile on this Windows box (heavy transitive deps) — the prebuilt release binary
is the supported path here. Add `~/.local/bin` to PATH, or call it by full path.

## Read provenance (no cert needed)

```
~/.local/bin/c2patool.exe <ASSET>          # prints the JSON manifest (or "no claim" if unsigned)
~/.local/bin/c2patool.exe <ASSET> --info   # concise summary
```

## Sign / attach a manifest

```
~/.local/bin/c2patool.exe <INPUT> -m <manifest.json> -o <OUTPUT> -f
```
The manifest JSON declares the signer + claims:
```json
{
  "alg": "es256",
  "private_key": "es256_private.key",
  "sign_cert": "es256_certs.pem",
  "claim_generator": "my-app/1.0",
  "assertions": [
    {"label": "c2pa.actions", "data": {"actions": [{"action": "c2pa.published"}]}}
  ]
}
```
`private_key` / `sign_cert` resolve relative to the CWD (or use absolute paths, or the env vars
`C2PA_PRIVATE_KEY` + `C2PA_SIGN_CERT`). `-f` overwrites the output; the input is never modified.

### Certs — TEST vs REAL
### Acceptance (verified 2026-07-04)
### Notes
