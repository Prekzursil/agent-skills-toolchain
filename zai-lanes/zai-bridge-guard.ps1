# zai-bridge-guard v2 - DISABLED BY DEFAULT (owner incident 2026-09-23).
# v1 DEFECT (measured, owner-reported): its health probe SENT A CHAT ("Reply: OK")
# every 5 minutes through the web-profile browser, which carries the OWNER'S
# LOGGED-IN chat.z.ai session -> the "free lane" consumed the owner's account
# quota and cluttered their chat history. A health check must NEVER consume the
# resource it guards. v2 probes ONLY the TCP listener (zero browser, zero chat,
# zero quota) and restarts nothing on content-level failures - a wedged bridge
# costs nothing; a probing bridge costs the owner money.
#
# The task 'ZaiBridgeGuard' is Disabled. Re-enable only with owner consent and
# only with this v2 file in place.

$ErrorActionPreference = 'SilentlyContinue'

function ProbePort {
  # ZERO-COST liveness: TCP listener only. Never drive the browser. Never chat.
  return [bool](Get-NetTCPConnection -LocalPort 18319 -State Listen -ErrorAction SilentlyContinue)
}

if (-not (ProbePort)) {
  # port down: restart the bridge process (does NOT open chats by itself;
  # the browser only spawns on the first real user-initiated request)
  Start-Process -WindowStyle Hidden -FilePath python `
    -WorkingDirectory 'C:\Users\Prekzursil\source\agent-skills-toolchain\zai-lanes' `
    -ArgumentList 'D:olt\enum\pulls\zai-entitlement-fuzz_2026-09-19\zai-anon-mcp.py','http','18319'
}
