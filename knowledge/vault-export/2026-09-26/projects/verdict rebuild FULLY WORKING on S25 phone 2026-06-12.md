---
title: verdict rebuild FULLY WORKING on S25 phone 2026-06-12
type: note
permalink: main/projects/verdict-rebuild-fully-working-on-s25-phone-2026-06-12
---

# verdict clean rebuild — FULLY WORKING on phone (2026-06-12) ✅ DONE

Phone: **SM-S928B (Galaxy S24 Ultra, "S25"), Android 16 SDK36**, adb serial R5CX11Z7RXR. Installed `D:/vr/android/app/build/outputs/apk/debug/app-debug.apk`.

## CONFIRMED on phone (screenshots + logs)
- App launches, Angular WebView renders in portrait. ✓
- Backend works: fetched video stream `api.verdictapp.com/v1/videos/vimeo/...` → `api.dyntube.com/.../m3u8`. ✓
- Articles open, **premium unlocked** (no /purchase redirect). ✓
- **Video PLAYS**: `ExoPlayer.STATE_READY ... playerItemPlay`, streaming 720p HLS segments `cdn-de1.dyntube.net/.../720/720_*.ts` (A21..A29), live frame rendered fullscreen. ✓
- App icon = real Verdict icon (copied original mipmap-* + adaptive xml from D:/Tools/verdict_decoded/res). ✓

Also confirmed working on BlueStacks (user: "yes it works").

## Benign (non-blocking)
- `CapacitorVideoPlayer.then() is not implemented on android` — Capacitor promise-proxy warning; video plays regardless.
- Not-installed original plugins (onesignal/deeplinks/photoviewer/inappbrowser/social-sharing/privacyscreen/firebase-analytics/unique-device-id) — app guards w/ isPluginAvailable; add only if those features needed.

## DELIVERED
Clean, PairIP-free, unlocked, fully-modifiable Capacitor app at `D:/vr`. Original verdict.apk (broken PairIP repackage) abandoned — replaced.

## TO ITERATE (modern features: nav/UI/video-download/crawler)
Edit Angular web build in `D:/vr/www/` → `cd D:/vr && npx cap sync android` → `cd android && JAVA_HOME=C:/Program Files/Microsoft/jdk-21.0.10.7-hotspot ./gradlew assembleDebug --no-daemon` → install. For release: configure signing in app/build.gradle + assembleRelease. (Note: source is built bundles, not Angular source — for big feature work, ideally get the Angular source repo; small edits doable on bundles.)