---
title: Verdict + dev learnings (self-reflect 2026-06-15)
type: note
permalink: main/projects/learnings/verdict-dev-learnings-self-reflect-2026-06-15
tags:
- learnings
- verdict
- gotcha
- self-reflect
---

Durable, reusable learnings mined from the 2026-06-15 session (Verdict app: share viewer + live search + dual-host deploy). Captured via self-reflect (Phase B; repo has no .beads/PRs).

## Verdict-specific (backend/app)
1. **[gotcha] Video CORS asymmetry.** Resolver `api.verdictapp.com/v1/videos/vimeo/<id>` sends NO CORS header (browser-blocked); `api.dyntube.com` reflects Origin and `cdn.dyntube.net` is `*`. So a web viewer proxies ONLY the resolver call; the HLS master+segments stream direct via hls.js. (applies: any web/edge renderer of Verdict video)
2. **[api_behavior] No public URL renders Verdict content.** `app.verdictapp.com/<id>` = the Capacitor bundle served on web (renders only inside the app); `verdictdanabudeanu.com/?p=<id>` 303→verdictapp.com; `verdictapp.com/article/<id>` 404. Shareable links need a self-hosted renderer.
3. **[gotcha] Typesense is CORS-`*`, content is plaintext HTML, premium is open server-side.** An edge/static viewer fetches any article by id directly (`q=*&query_by=title&filter_by=id:=<id>`) with the public search key — no proxy, no login.
4. **[gotcha] Don't "improve" Typesense search by setting its own defaults.** `prefix:true` and `num_typos:2` are ALREADY Typesense defaults → no-op. For "live as you type", the lever is the UI trigger (Ionic `ionChange`+enterkeyhint=search fires on ENTER → switch to `ionInput` per-keystroke) + drop the per-keystroke loading modal. (cost a wasted 7.4.5 release)

## Hybrid-app / build (Capacitor/Android)
5. **[gotcha] Minified webpack chunks patch in-place.** The content-hashed filename is a cache-buster, not a runtime integrity check — editing `<chunk>.<hash>.js` content (without renaming) works. Patch via exact-string replace + `node --check`.
6. **[gotcha] Half-installed cordova plugin = silent no-op.** JS wrapper + cordova_plugins.js present (carried from original) but native plugin absent → `cordova.exec` rejects at the native layer and `.catch` swallows it. Fix = `npm i <plugin> --legacy-peer-deps` + `npx cap sync`.
7. **[gotcha] adb `install -r` fails across signing schemes** (INSTALL_FAILED_UPDATE_INCOMPATIBLE) when installed=debug-signed and new=release-signed (or vice versa). `adb uninstall` first to test a release over a debug install.
8. **[gotcha] Capacitor WebView is opaque to uiautomator** — adb can't find HTML buttons inside the WebView (one node), so coordinate-tapping is blind/flaky. Verify WebView UI on a real device or via remote debugging, not adb taps.

## Tooling / deploy
9. **[gotcha] CLI OAuth (wrangler/deployctl) login dies in a backgrounded/non-interactive shell** — the localhost callback server is killed when the wrapper exits. Run login as the MAIN command of a persistent background task so the server stays up for the callback.
10. **[gotcha] Deno Deploy split:** classic `dash.deno.com` (deployctl, `*.deno.dev`) ≠ new `console.deno.com` (Playground/GitHub-app, `*.deno.net`). deployctl's classic auth long-poll fails for new-platform accounts; deploy via the console Playground (paste worker), and the playground/app NAME = the URL subdomain (rename → URL changes; verified slug pattern `{app.slug}.<org>.deno.net`).
11. **[gotcha] claude-in-chrome needs `/chrome` to pair the browser with the session** — "extension not connected" persists (Edge OR Chrome) until `/chrome` selects/pairs the "Claude" browser; then `tabs_context` returns "No MCP tab groups found" (=connected) and it drives Edge fine. Fix if it drops: run `/chrome`.
