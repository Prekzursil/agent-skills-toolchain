---
title: verdict.apk ROOT CAUSE - broken string-externalization patch 2026-06-12
type: note
permalink: main/projects/verdict.apk-root-cause-broken-string-externalization-patch-2026-06-12
---

# verdict.apk REAL root cause (2026-06-12) — broken string-externalization

The launch crash (`Charset.forName("")` in `com.google.android.gms.internal.cast.zzsq.<clinit>` → IllegalCharsetNameException) is ONE symptom of a **broken string-externalization pass** in the user's patch.

## Mechanism
Patcher injected class `Lcom/google/android/exoplayer2/mediacodec/Sk/dCxGWqqQWP;` (defined in classes.dex) with **53 public static String fields**. Its `<clinit>` sets **ALL 53 to `""`** (no decryption, no real values). The patch replaced 53 string literals across the app: each original `const-string vR, "VALUE"` became `const/4 vR,0x0` + `sget-object vR, dCxGWqqQWP;->FIELD:String`. So every externalized string reads as empty. zzsq (GMS cast Utf8 helper: zza=US-ASCII, zzb=UTF-8→FIELD VzYEztdR, zzc=ISO-8859-1) crashes first at startup. Rest break features silently/loudly.

## Recovery is CLEAN (1:1)
- 53 fields, 53 `sget-object` reads total across classes/classes2/classes3 → each field read exactly once.
- Original unpatched app **`com.verdictdanabudeanu.verdictbydanabudeanu` versionName 7.4.3 (==patched 7.4.3), versionCode 34** is installed on BlueStacks (emulator-5554) at `/data/app/...verdictbydanabudeanu.../base.apk`. SAME version → original literals recoverable by matching each field's read-site method to the original's `const-string`.
- Algorithm: per method, ordered list of dCxGWqqQWP field reads in patched ↔ ordered list of const-strings present in original-method but absent in patched-method.

## Plan
pull original base.apk → disassemble → build FIELD→string map (53) → rewrite dCxGWqqQWP.<clinit> with real values → reassemble classes.dex via tools/SmaliTool (apktool-bundled smali) → swap classes.dex into verdict-clean base (manifest split-patch already applied) → zipalign + apksigner v1+v2+v3 → install + launch loop.

## Tooling note
tools/SmaliTool.java (compile `javac -cp D:/ReverseTools/Android/apktool/apktool.jar`; run `java -cp ".;<apktooljar>" SmaliTool dis <apk> <dexName> <outdir>` / `asm <smaliDir> <out.dex>`). DexBackedDexFile(byte[],0) — int arg is OFFSET not api. Windows classpath form `D:/...` required, `;` separator.