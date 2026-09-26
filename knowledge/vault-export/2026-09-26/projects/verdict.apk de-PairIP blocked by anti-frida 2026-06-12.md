---
title: verdict.apk de-PairIP blocked by anti-frida 2026-06-12
type: note
permalink: main/projects/verdict.apk-de-pair-ip-blocked-by-anti-frida-2026-06-12
---

# verdict.apk — de-PairIP attempt blocked (2026-06-12)

Scope of PairIP string-provisioning: **31 holder classes, ~1507 String fields** total. Restoring by hand = impossible; runtime-dump-and-inline is the only viable string fix.

**Runtime dump BLOCKED by anti-frida:** frida CLI 17.11.0 (frida-server running root on BlueStacks emulator-5554, 110MB binary) repeatedly fails `Failed to load script: timeout was reached` attaching to genuine `com.verdictdanabudeanu.verdictbydanabudeanu` (pid alive, app stable). Even a trivial deferred-setTimeout script won't load. PairIP anti-instrumentation. (Note: frida WORKS for Battle Cats on a different BC stack per memory — so it's app-specific anti-frida, not broken frida.)

**App is Ionic/Cordova hybrid** (io.ionic.links, by.chemerisuk.cordova, WebView) → articles/videos load over HTTP; the API/content URLs are PairIP-encrypted strings → empty in the gutted patched build → "content doesn't load".

**Genuine app status:** com.verdictdanabudeanu v7.4.3 runs STABLE on BlueStacks (MainActivity, alive). Uses FLAG_SECURE (screencap returns 0 bytes). Has lib/x86_64/libpairipcore.so. The patched com.patched.verdict is broken everywhere (incl. when user installed it on BlueStacks).

**executeVM is pure-Java** (no native modifier) — so OFFLINE string decryption MIGHT be possible by extracting the executeVM interpreter + encrypted blobs and running in a JVM, but PairIP bootstrap is complex; unverified.

**Phone:** disconnected mid-session (R52Y307HHXB gone from adb). arm64. Needs arm64 libpairipcore.so for genuine PairIP (BlueStacks only has x86_64) — re-signing genuine also breaks PairIP integrity. So genuine works on phone ONLY if installed Play-Store-signed (no re-sign).

**Verdict:** patched build unsalvageable without full de-PairIP (defeat anti-frida + extract 1500 strings + neutralize licensecheck/integrity + possibly de-virtualize methods) = major multi-session RE project. Modern features (nav/UI/video-dl/crawler) NOT yet implemented in verdict.apk, so nothing in it worth saving. Pending: WHY user uses patch (paywall/region/removed?) — determines if genuine app suffices.