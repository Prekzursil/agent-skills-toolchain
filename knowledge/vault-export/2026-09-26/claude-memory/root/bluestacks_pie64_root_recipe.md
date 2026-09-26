---
name: BlueStacks 5 Pie64 Root + Magisk + LSPosed + Frida recipe
description: Non-obvious procedure to root BlueStacks 5 with full Magisk/Zygisk/LSPosed/Frida
  stack, including the version-downgrade requirement and policy-DB tricks
type: project
originSessionId: 177b5875-766a-4400-8672-1ae9e0959579
permalink: main/claude-memory/root/bluestacks-pie64-root-recipe
---

The user runs Battle Cats reverse engineering work on BlueStacks 5 / Pie64 (Android 9 / API 28 / x86_64). Previous WSA setup was abandoned due to slow Frida/ADB; switched to BlueStacks 2026-04-29.

**The procedure that actually works (verified 2026-04-29 03:25):**

1. **BlueStacks version matters**: 5.22.150.1014+ has a self-imposed integrity check that blocks root by detecting `Readonly→Normal` disk-attribute changes. **Must use 5.22.130.1019** (last working build for rooting). The full installer (3.7GB) lives at `D:\ReverseTools\Android\BlueStacks-Downgrade\BlueStacksFullInstaller_5.22.130.1019_amd64_native.exe` (SHA256 `695658a6b1bc138dd5a156fb5373c874941db1ab62b811f160e0c9a95e6df0c4`).

2. **Block the updater**: Add `127.0.0.1` host entries for `ak-build.bluestacks.com`, `bsupdater.bluestacks.com`, `update.bluestacks.com`, `cdn-updater.bluestacks.com`, `install.bluestacks.com` so BlueStacks can't silently upgrade past the lockout cutoff.

3. **Three files patched per instance** (BlueStacks must be fully shut down):
   - `C:\ProgramData\BlueStacks_nxt\bluestacks.conf`: set `bst.feature.rooting="1"` and `bst.instance.Pie64.enable_root_access="1"`. The global `feature.rooting` reverts to `"0"` on each shutdown — that's fine, runtime gate is the per-instance flag plus disk attrs.
   - `C:\ProgramData\BlueStacks_nxt\Engine\Pie64\Android.bstk.in` and `Pie64.bstk`: change `type="Readonly"` → `type="Normal"` for both `fastboot.vdi` and `Root.vhd`. **This is the critical change** — without it /system reverts at every boot. The `Data.vhdx` is already `Normal` (user data partition).

4. **Stock Magisk doesn't work on BlueStacks** because it expects a real `boot.img` to patch. Use **Kitsune Mask** (HuskyDG fork). The original `HuskyDG/magisk-files` repo is 404 — get the v26.4 stable APK from the `Scratch2033Alt/KitsuneMagisk` mirror at `https://raw.githubusercontent.com/Scratch2033Alt/KitsuneMagisk/main/26.4-kitsune.apk`. Install via `adb install`, open the app in Pie64, tap **"Install" → "Direct Install" → wait for "Installation complete" → "Reboot"**.

5. **`/system/xbin/su` (BlueStacks's original) coexists with `/sbin/su → magisk`** after install. Use BlueStacks's su as a one-time bootstrap to grant Magisk's su access to adb shell:
   ```
   echo 'magisk --sqlite "REPLACE INTO policies (uid,policy,until,logging,notification) VALUES (2000,2,0,0,0)"' > grant.sh
   adb push grant.sh /data/local/tmp/grant.sh
   adb shell "/system/xbin/su -c sh /data/local/tmp/grant.sh"
   ```
   Magisk's policy DB uses `policy=2` for ALLOW (not 1). uid=2000 is adb shell.

6. **Enable Zygisk via SQL** (not via Magisk Manager UI — easier to script):
   ```
   magisk --sqlite "REPLACE INTO settings (key,value) VALUES ('zygisk',1)"
   ```
   Then reboot. Verify with `ps -A | grep -E "magiskd|zygiskd|lspd"`.

7. **LSPosed Manager APK is bundled inside the Zygisk module** at `/data/adb/modules/zygisk_lsposed/manager.apk` — install separately via `pm install` after copying out of /data/adb (which is root-only readable):
   ```
   adb shell "su -c 'cp /data/adb/modules/zygisk_lsposed/manager.apk /data/local/tmp/lsposed-manager.apk && chmod 644 /data/local/tmp/lsposed-manager.apk'"
   adb shell "pm install /data/local/tmp/lsposed-manager.apk"
   ```

8. **Frida-server runs as a Magisk module** for boot autostart. Module template at `C:\Users\Prekzursil\.cache\frida-magisk-module\` — module.prop, service.sh that waits for `sys.boot_completed=1` then starts the binary in nohup.

9. **Frida from host**: `adb forward tcp:27042 tcp:27042` then `frida-ps -H 127.0.0.1`. **Avoid `frida-ps -U`** — it tends to hang on BlueStacks's ADB-over-TCP setup.

**Why this matters for future sessions**: The integrity-check downgrade requirement is *not* obvious from BlueStacks's docs (which actively discourage rooting in newer builds). The Magisk policy DB grant is *not* documented anywhere except Magisk's source. Without these two specific tricks, you'd be stuck thinking root is broken when it's actually just a UID-2000 default-deny in the policy DB.

**Reference docs in the project**:
- `D:\ReverseTools\Android\BattleCats\DEBUGGING_STACK.md` — full host stack quick-reference
- `D:\ReverseTools\Android\LSPosed\README.md` — LSPosed-specific verify/rollback procedures
- Patch scripts: `C:\Users\Prekzursil\.cache\bluestacks-{cleanup,root-patch,block-updater}.ps1`