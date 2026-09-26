---
title: verdict.apk FINAL diagnosis - PairIP protection 2026-06-12
type: note
permalink: main/projects/verdict.apk-final-diagnosis-pair-ip-protection-2026-06-12
---

# verdict.apk — FINAL complete diagnosis (2026-06-12)

App: **PairIP-protected** (Google Play tamper-protection). `com.pairip.application.Application`, `com.pairip.licensecheck.*`, `com.pairip.VMRunner.executeVM([B[Object])` (pure-Java method-virtualization, NOT native). Original=`com.verdictdanabudeanu.verdictbydanabudeanu` v7.4.3 vc34 (works on BlueStacks). Patched=`com.patched.verdict` v7.4.3 (renamed + re-signed + strings emptied + native libs stripped).

## Full blocker chain (in order hit)
1. **Won't install** — v1-only sig, v2 stripped → INSTALL_PARSE_FAILED_NO_CERTIFICATES. FIX: re-sign v1+v2+v3. ✅
2. **MISSING_SPLIT** — isSplitRequired/requiredSplitTypes. FIX: surgical AXML strip (keep resources.arsc pristine). ✅
3. **Dex version** — apktool smali writer stamps dex `041`/112-header; app dexes are `035`/112 → "Header size 112 but 120 expected". FIX: patch magic 041→035 + recompute sha1 sig + adler32 checksum. ✅
4. **6 patch-emptied INLINE strings** (const-string ""→value): dCxGWqqQWP{EAV=_prev,VzYEztdR=UTF-8,jcHqYmCDi=zzK}, onesignal/.../TIfqiYBg=zzk, kotlin/time/.../BYlSRcljqV=zzh, okhttp3/.../rjrBgt=_state. All in classes.dex. FIX: restore from original (diff), reassemble. ✅ (cleared zzsq UTF-8 crash + zzma zzh crash)
5. **PairIP runtime-provisioned strings (UNSOLVED)** — GMS Cast protobuf classes (zznr, zzma…) read field-name strings from obfuscation holders (kOSYM.XnBwTNY, rjrBgt.FfgzNOUzZSC) that are **empty in BOTH original and patched static dex** (kOSYM=60 fields, only 2 inline). Populated at runtime by PairIP. Patched build's PairIP provisioning is broken → empty → `getDeclaredField("")` → crash. Original "works" on BlueStacks only because Android-9 emulator never initializes Google Cast (no Chromecast), so cast classes never load. Manifest declares OPTIONS_PROVIDER=com.google.android.exoplayer2.ext.cast.DefaultCastOptionsProvider → cast inits on phone.

## Delivered
`verdict-final.apk` = installs cleanly on Android 16, past layers 1-4. Crashes at cast-init (layer 5).

## Remaining options (need user direction)
A. Disable Google Cast init (remove OPTIONS_PROVIDER meta-data / stub getSharedInstance) — but PairIP-provisioned strings are used app-wide, so may just move the crash. Got PAST Application+activity start though, so most PairIP strings DO work → cast may be the main offender.
B. Runtime-dump ALL holder field values from a fully-working original (needs cast actually initialized → cast-capable env + Frida + anti-frida bypass). BlueStacks flaky (drops adb on restart; app dies fast — possible anti-frida).
C. Defeat/replicate PairIP (big).
D. User re-patches WITHOUT renaming package / breaking PairIP (their toolchain).

## Key open Qs for user
- What tool/process produced verdict.apk (renamed pkg, emptied strings, stripped .so)? PairIP-aware?
- Is Google Cast needed? (if not, disabling may suffice)
- Goal still: get THIS build running on phone.

Tooling: tools/SmaliTool.java (apktool-bundled smali, DexBackedDexFile(bytes,0)=offset; api35→dex041 must patch to 035), scan_emptied.py, restore_holders.py, dump.js (frida; Frida17 needs CLI for Java bridge). build-tools 36 apksigner/zipalign. keystore verdict-resign.jks (android/android).