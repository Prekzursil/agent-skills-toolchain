# Secrets & credential stores (git-crypt)

This repo carries per-user credential stores (`tools/mcp/*/accounts.json`) so the MCP
hubs are **plug-and-play on a new device**. Those files hold real API keys / account
tokens, so they are committed **encrypted** with [git-crypt](https://github.com/AGWA/git-crypt)
— never in plaintext.

- Encrypted in git, decrypted transparently in your working tree after you unlock.
- The MCP hubs read `accounts.json` normally — no app changes.
- `*.example.json` templates stay plaintext (they only show `${ENV}`-reference shapes).
- Which files are encrypted is defined in the root [`.gitattributes`](../.gitattributes).

## Plug-and-play on a new device

```bash
# 1. install git-crypt   (Windows: scoop install git-crypt  |  macOS: brew install git-crypt
#                          Debian/Ubuntu: sudo apt install git-crypt)
# 2. clone
git clone <repo-url> && cd agent-skills-toolchain
# 3. unlock with the exported key (keep this key in your password manager, NEVER in git)
git-crypt unlock /path/to/agent-skills-toolchain.gitcrypt.key
```

After `unlock`, every `accounts.json` decrypts in place and the hubs work immediately.

## The key

- Exported once with `git-crypt export-key <path>` → stored in your **password manager**.
- It is a symmetric key: anyone with it can decrypt the committed secrets. Treat it like
  the secrets themselves. It lives **outside** the repo and is never committed.
- Lost the key? You cannot decrypt existing blobs — rotate the affected API keys/tokens,
  re-`git-crypt init`, and re-commit.

## Verify encryption before committing new secret files

git-crypt failures are silent (a misconfigured file commits in plaintext). Before pushing
any change that adds/edits a secret file, confirm the **staged blob** is encrypted:

```bash
git show :tools/mcp/<hub>/accounts.json | head -c 16 | od -c   # expect: \0 G I T C R Y P T \0
git show :tools/mcp/<hub>/accounts.json | grep -c '<a-known-secret-substring>'   # expect: 0
```

If you see plaintext JSON (`{`) or a non-zero grep, **do not push** — the `.gitattributes`
pattern isn't matching. Fix the pattern and re-stage.

## Rotating / adding accounts

The hubs manage accounts via their MCP tools (e.g. `ex_account_add`, `fb_account_add`),
which write `accounts.json`. Commit the resulting change like any other — git-crypt
re-encrypts on `git add`. Verify with the blob check above.
