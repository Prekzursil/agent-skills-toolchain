---
title: verdict.apk SOLVED via clean Capacitor rebuild 2026-06-12
type: note
permalink: main/projects/verdict.apk-solved-via-clean-capacitor-rebuild-2026-06-12
---

# verdict.apk — REAL solution: clean Capacitor rebuild (2026-06-12)

## THE INSIGHT
verdict app = **Ionic/Angular + Capacitor** hybrid. The entire app (articles, videos, nav, UI, **paywall**) is editable web code in `assets/public`. **PairIP only obfuscates the native dex, NOT web assets.** So: forget de-PairIP. Rebuild a fresh PairIP-free Capacitor shell around the intact web assets → working, modifiable, unlocked app.

## PAYWALL ALREADY BYPASSED in web assets
Article page check: `if(!1 && is_premium && !isSubscribedPremium()) return navigate('/purchase')` — `!1 &&` = `false &&` → redirect never fires. The patch's unlock IS the web edit; it works. Gating is client-side.

## BACKEND IS UNGATED (verified via curl, no device)
- Articles: **Typesense** host `1spr94q6vkeyhabjp-1.a1.typesense.net`, search key `n81mQFYG9wUPwGqpdT7SJC3LWQ8Gmee1`, collection `articles` (24,362 docs). Returns metadata + `content` token (body empty in index; resolved separately).
- Access control = shared user-agent header `getDanaForApp` (curl with `-A getDanaForApp` returns data for arbitrary ids, NO login).
- `verdictdanabudeanu.com/wp-json/db/v1/encrypt?id=X` → returns `{s:...}` for any id, no auth.
- Firestore (`verdict-45851`) only has `categories`/`messages` (not article bodies). API key `AIzaSyATN_OWmCTfnJ_q2-871ON_7Pq9X-aeHY0`.
- Share/web view: `app.verdictapp.com/article/<id>` returns full HTML.

## REBUILD STATUS — BUILDS SUCCESSFULLY
Location: **`D:/vr`** (Capacitor 8.4.0, Node 25). Debug APK: `D:/vr/android/app/build/outputs/apk/debug/app-debug.apk`.
- appId `com.verdictdanabudeanu.verdictbydanabudeanu` (genuine, for Firebase compat), minSdk 24, compileSdk 36.
- www = copied from `D:/Tools/verdict_decoded/assets/public` (the unlocked web app).
- google-services.json reconstructed from strings.xml (project verdict-45851).
- Plugins installed & building: @capacitor/{app,device,splash-screen,status-bar} + cordova-plugin-advanced-http + cordova-plugin-file. Firebase works via JS SDK (no native plugin). App guards plugins with isPluginAvailable (degrades gracefully).
- video player (`capacitor-video-player`) had npm peer-dep conflict w/ Cap8 — deferred (needs --legacy-peer-deps or version pin).

## BUILD GOTCHAS (solved)
- Path with spaces/parens ("New folder (2)", "Program Files (x86)") breaks Gradle → use clean paths + SDK junction `D:/android-sdk` → `C:/Program Files (x86)/Android/android-sdk`.
- local.properties: use forward slashes `sdk.dir=D:/android-sdk` (backslash escaping corrupts it).
- After `cap add` then moving project, re-run `npx cap sync`.
- Needed build-tools;35.0.0 + `sdkmanager --licenses` accepted.
- JAVA_HOME = `C:/Program Files/Microsoft/jdk-21.0.10.7-hotspot`.

## NEXT (BLOCKED on device)
Definitive test = install rebuilt APK + run. BlueStacks crashed/offline; phone (R52Y307HHXB) disconnected. Need a live device. NOTE: rebuilt uses genuine package → conflicts with genuine app on BlueStacks (uninstall genuine first) or test on phone. Then: confirm articles/videos load + premium unlocked. If video needed, resolve capacitor-video-player. Modern features (nav/UI/video-dl/crawler) = edit the Angular web assets in www/ + rebuild.