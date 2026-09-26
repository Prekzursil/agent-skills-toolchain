---
title: verdict.apk (com.patched.verdict) install+crash diagnosis 2026-06-12
type: note
permalink: main/projects/verdict.apk-com.patched.verdict-install-crash-diagnosis-2026-06-12
---

# verdict.apk diagnosis (2026-06-12)

File: `C:/Users/Prekzursil/Downloads/New folder (2)/verdict.apk` — 16.5MB, pkg **com.patched.verdict** (renamed/patched), versionName 7.4.3. WebView+Firebase+Play-Services-Cast app, NO native libs. Original app = **com.verdictdanabudeanu.verdictbydanabudeanu** ("Verdict by Dana Budeanu"), which is what's installed/working on BlueStacks (different package!).

Test devices: physical = **SM-X620 (Galaxy Tab S10+), Android 16/SDK36** (user calls it "S25"; real S25=SM-S931x). BlueStacks = emulator-5554, Android 9/SDK28, spoofs SM-S908E.

## Three-layer problem
1. **Install blocker #1 (root cause of "won't install"):** v1(JAR)-only signature, signer `CN=Patched` (self-signed, dated today). `.SF` declares `X-Android-APK-Signed: 2` but v2 block was STRIPPED → `INSTALL_PARSE_FAILED_NO_CERTIFICATES: ...Signature stripped?`. Android 7+ rejects; BlueStacks(9) tolerated original. FIX: re-sign v1+v2+v3.
2. **Install blocker #2:** manifest `isSplitRequired=true requiredSplitTypes="base__abi,base__density"` + `<meta-data com.android.vending.splits.required true>` → `INSTALL_FAILED_MISSING_SPLIT`. It's the BASE split of an AAB. FIX: neutralize flags. **Do it via SURGICAL binary AXML edit, NOT apktool** — apktool rebuild remapped resources.arsc (created dangling pkg-id 0x6a refs). Surgical patch keeps resources.arsc byte-identical (verified 0x7f only).
3. **Runtime crash (UNSOLVED):** even clean-signed+split-stripped+resources-intact, launch → `FATAL java.lang.ExceptionInInitializerError` at `com.google.android.gms.internal.cast.zzsq.<clinit>` → `Charset.forName("")` → `IllegalCharsetNameException`. Cast framework async init (Handler-posted zzq.run). Reproduces on pristine build → INHERENT to this patched build, likely a blanked string constant in bundled play-services-cast@@21.3.0 from the patch process. `No package ID 6a found for resource ID 0x6a0b0013` is RED HERRING (Samsung RRO; also logged by com.sec.penup).

## Tools (all local)
build-tools 36.0.0 at `C:/Program Files (x86)/Android/android-sdk/build-tools/36.0.0/` (apksigner.jar, zipalign.exe). apktool 3.0.2 at D:/ReverseTools/Android/apktool. Keystore created: `verdict-resign.jks` (storepass/keypass=android, alias verdict). adb at C:/ADB/adb.

## Artifacts produced (in New folder (2))
- `verdict-clean.apk` = WORKING INSTALL (surgical patch, resources intact, v1+v2+v3) — installs Success on Android 16 but app crashes at launch (cast). **Best base for further work.**
- `verdict-fixed.apk` = apktool version (resources CORRUPTED) — avoid.
- app.apkm/app1.apkm in Downloads = DIFFERENT app (Cornershop/Shipt v4.619, 229MB) — unrelated red herring.

## Open decision (asked user)
Goal: run original vs. need THIS patched build? Provenance of the patch? Whether to dig into neutralizing Cast init to stop the crash.