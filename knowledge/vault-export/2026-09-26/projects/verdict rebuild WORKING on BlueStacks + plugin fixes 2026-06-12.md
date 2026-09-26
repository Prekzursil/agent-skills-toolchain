---
title: verdict rebuild WORKING on BlueStacks + plugin fixes 2026-06-12
type: note
permalink: main/projects/verdict-rebuild-working-on-blue-stacks-plugin-fixes-2026-06-12
---

# verdict clean Capacitor rebuild — WORKING on BlueStacks (2026-06-12)

Rebuild at `D:/vr` (Capacitor 8.4.0). APK: `D:/vr/android/app/build/outputs/apk/debug/app-debug.apk`. Installed + runs on BlueStacks (127.0.0.1:5555, Android 9). **No PairIP, no crashes.**

## CONFIRMED WORKING (screenshots taken)
- App launches, Angular WebView renders. Home feed loads articles+images from Typesense backend (categories VERDICT AMETITE, VERDICT MEDIA). Bottom nav works.
- **Unlock CONFIRMED**: tapped a premium video article ("AMETITELE CA N FILME!") → opened to full content with play button, NO /purchase redirect (the `!1 &&` web bypass works).

## FIXES APPLIED (iterative)
1. **White screen** → `Uncaught ReferenceError: CdvPurchase is not defined` (subscription service references purchase plugin global at boot, not guarded). FIX: `npm i cordova-plugin-purchase`. → renders.
2. **Videos don't play** → deferred capacitor-video-player. FIX: `npm i capacitor-video-player --legacy-peer-deps` (got 6.0.2, builds on Cap8 despite peer warning).
3. **Video crash** → `IllegalStateException: OptionsProvider must be provided ... OPTIONS_PROVIDER_CLASS_NAME` — capacitor-video-player calls CastContext.getSharedInstance() in onCreateView. FIX: created `app/src/main/java/com/verdictdanabudeanu/verdictbydanabudeanu/CastOptionsProvider.java` (minimal, receiverApplicationId CC1AD845) + manifest meta-data `com.google.android.gms.cast.framework.OPTIONS_PROVIDER_CLASS_NAME` + added `implementation "com.google.android.gms:play-services-cast-framework:21.3.0"` to app/build.gradle (cast classes weren't on app module classpath). → cast crash gone, ExoPlayer reaches codec init.

## Installed plugins
@capacitor/{app,device,splash-screen,status-bar}, cordova-plugin-{advanced-http,file,purchase}, capacitor-video-player@6.0.2. Firebase via JS SDK. minSdk 24. appId com.verdictdanabudeanu.verdictbydanabudeanu (genuine, for Firebase compat).

## PENDING
- User to confirm video PLAYBACK on BlueStacks (blind adb taps couldn't reliably hit play; cast crash is fixed so should work now).
- Then test on PHONE (R52Y307HHXB, arm64, Android 16) — was disconnected; reconnect + install same APK.
- Remaining original plugins not yet added (onesignal, deeplinks, photoviewer, inappbrowser, social-sharing, privacyscreen, firebase-analytics, unique-device-id) — app guards with isPluginAvailable so non-fatal; add if a feature needs them.
- Modern features (nav/UI/video-dl/crawler) = edit Angular web bundles in D:/vr/www + `npx cap sync` + rebuild.

## Build env (clean paths required!)
JAVA_HOME=C:/Program Files/Microsoft/jdk-21.0.10.7-hotspot. SDK junction D:/android-sdk. local.properties forward-slashes. Build: `cd D:/vr/android && JAVA_HOME=... ./gradlew assembleDebug --no-daemon`.