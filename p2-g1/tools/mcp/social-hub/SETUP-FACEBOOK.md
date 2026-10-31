# Facebook setup — one screen

Two things you do once; everything after is automatic and self-healing. **You** log into
Facebook yourself — no script here ever types a password, a code, or a credential.

Run commands from `tools/mcp/social-hub/` unless noted. `node` + the fb-reels Playwright must
be installed (`cd ../fb-reels-uploader && npm install` once).

---

## 1. Refresh the Facebook session (fixes `whoami`, Messenger, E2EE DMs)

```
python fb_session.py
```

A browser window opens on facebook.com. **Log in yourself** (this is the ONLY step that touches
your password, and you type it — the tool cannot). When you are in, the tool writes `cookies.json`
and immediately verifies it by calling the backend's `whoami`. Success prints:

```
SUCCESS:fb-session authenticated -> …/cookies.json
```

- It reuses the **same** persistent profile as fb-reels, so this one login also powers Reel uploads.
- **Re-run this whenever `whoami` starts failing.** That is the whole point — the old rot (a
  6-week-stale cookie) can no longer happen silently.
- Already logged in and just want to re-export headlessly: `python fb_session.py --headless`.
- Just re-check auth without a browser: `python fb_session.py --verify-only`.

---

## 2. Get your OWN posts into the writing corpus — the DYI export (the complete rail)

This is the **chosen** rail: it is the only complete, official, scrape-free path to your authored
posts. `fbchat_muqit`/cookies only reach Messenger, so they can NOT do this.

1. Facebook → **Accounts Center** → **Your information and permissions** → **Export your
   information** → **Create export**.
2. Pick your profile. Under **Your Facebook activity**, select at least **Posts** (add **Comments**
   if you want them). Set **Date range = All time**, **Format = JSON**, **Media quality = Low**.
3. Submit. Facebook asks you to **re-enter your password** (only you can clear this gate), then
   prepares the archive over hours→days and gives you a **4-day download window**.
4. Download the `.zip` (do not unzip), then:

```
python fb_timeline.py dyi  path/to/facebook-export.zip  --out "C:/Users/Prekzursil/Downloads/my_writing/Facebook"
```

It writes `facebook_posts.jsonl` + `.txt` (mojibake auto-repaired) which `build_corpus.py` folds in
like the other sources. *(The corpus skill's richer `isolate_facebook.py` targets the same export
if you prefer it; this tool is the self-contained repo equivalent.)*

> "All time" is not "everything": Meta warns it may omit very early history and anything you
> deleted. Those are survivorship gaps, not bugs — do not debug them.

---

## 3. (Optional) Live/incremental posts via the Graph API

Only if you want new posts without re-exporting. Not the completeness rail — Meta may return a
partial set.

> **Heads-up (observed 2026-07-19):** Meta Developer enrollment for this account is currently
> blocked by an account-safety cooldown. The registration page returns *"You can't make this
> change at the moment... we noticed you are using a device you don't usually use..."* (reproduced
> live in the page DOM on one device; the owner reports it on all devices, which is not
> independently verified here). This gates `FB_USER_TOKEN` generation, so the Graph rail is
> unavailable until Meta's cooldown clears (time + normal logged-in use). There is **no**
> legitimate bypass, and you should not attempt one. It does **not** affect the DYI rail in
> step 2, which needs no developer account. Likely cause: a device-trust reset after the
> ~6-week-stale session was re-established.

1. Create (or reuse) your own app at developers.facebook.com and keep it in **Development** mode —
   as its admin you can grant yourself `user_posts` with **no App Review**.
2. In **Graph API Explorer**, generate a **User** token with the `user_posts` scope; copy it.
3. `export FB_USER_TOKEN=<that token>` (or set it in your shell profile), then:

```
python fb_timeline.py graph --out "C:/Users/Prekzursil/Downloads/my_writing/Facebook"
```

---

## What is now automatic

- **Self-healing auth** — re-running step 1 re-exports + re-verifies; no more silent rot.
- **Per-account** — `FB_COOKIES_PATH` is wired in `backends.py`, so `fb_account_switch`/`_cycle`
  swap Facebook sessions exactly like Instagram's `INSTA_DATA_DIR`.

## One promotion step (optional, owner-only)

A live Claude session rewrites `~/.mcp.json` every ~30s, so this repo does **not** edit it. The fb
backend already defaults `FB_COOKIES_PATH` to `repos/fb-messenger-mcp/data/cookies.json`, so nothing
is required. If you want a different canonical path, add `"FB_COOKIES_PATH": "<path>"` to the
`social-hub` server's `env` block in `~/.mcp.json` yourself and restart the session.
