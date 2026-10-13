# rail_health.ps1 — research-rail health check + McpHub auto-heal (observe + heal, exit 0)
# Fixes applied 2026-09-22: McpHub URL /mcp->/sse (service was healthy, route was wrong),
# huggingface header dropped (OAuth/anonymous fallback), openalex-alt retired, searxng wired (searx.be).
$ErrorActionPreference = "SilentlyContinue"
$log = "C:\Users\Prekzursil\.agents\logs\rail-health.jsonl"
function Log($rail, $status, $action) {
  $ts = (Get-Date).ToUniversalTime().ToString("o")
  Add-Content -Path $log -Value ('{"ts":"' + $ts + '","rail":"' + $rail + '","status":"' + $status + '","action":"' + $action + '"}')
}
Log "healer" "boot" "run-start"

# --- McpHub: probe /sse with configured token; restart only on connection-refused (dead process) ---
try {
  # .claude.json has case-duplicate keys (reframe/Reframe) that break PS ConvertFrom-Json; use python (case-sensitive) instead
  $tok = python -c "import json;print(json.load(open(r'C:\Users\Prekzursil\.claude.json',encoding='utf-8'))['mcpServers']['McpHub']['headers']['Authorization'])"
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:24680/sse" -Headers @{Authorization=$tok} -TimeoutSec 6 -UseBasicParsing
  Log "mcphub" "ok:$($r.StatusCode)" "none"
} catch {
  if ($_.Exception.Message -match "unable to connect|refused|no connection") {
    Log "mcphub" "dead" "restarting"
    Get-Process McpHub | Stop-Process -Force
    Start-Sleep -Seconds 2
    Start-Process -FilePath "C:\Users\Prekzursil\.local\opt\mcphub\McpHub.exe" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 8
    try {
      $r2 = Invoke-WebRequest -Uri "http://127.0.0.1:24680/sse" -Headers @{Authorization=$tok} -TimeoutSec 6 -UseBasicParsing
      Log "mcphub" "restarted:$($r2.StatusCode)" "restart-ok"
    } catch { Log "mcphub" "restart-failed" "manual-attention" }
  } else {
    Log "mcphub" "degraded:$($_.Exception.Message.Substring(0,[Math]::Min(80,$_.Exception.Message.Length)))" "config-layer (401/404 = check token/route, not process)"
  }
}

# --- searx instance (log-only) ---
try {
  $s = Invoke-WebRequest -Uri "https://searx.be" -TimeoutSec 10 -UseBasicParsing
  Log "searxng-instance" "ok:$($s.StatusCode)" "none"
} catch { Log "searxng-instance" "unreachable" "swap SEARXNG_URL to another public instance if persistent" }

# --- huggingface endpoint (log-only) ---
try {
  $h = Invoke-WebRequest -Uri "https://huggingface.co/mcp" -TimeoutSec 10 -UseBasicParsing
  Log "huggingface" "ok:$($h.StatusCode)" "none"
} catch { Log "huggingface" "unreachable" "log-only" }

exit 0
