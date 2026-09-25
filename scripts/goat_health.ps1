#Requires -Version 7
<#
goat_health.ps1 — one-command GOAT stack health check (RB-07, 2026-09-22).
Checks: WSL, CS daemon, GLM router, biomni web+MCP, basic-memory chain,
GLM key liveness, model tier. Emits PASS/FAIL lines + GOAT:HEALTHY|DEGRADED.
Usage: pwsh -File goat_health.ps1  (-SkipKeyProbe for offline check)
#>
param([switch]$SkipKeyProbe)
$fail = 0
function Check([string]$Name, [scriptblock]$Probe) {
    try {
        $ok = & $Probe
        if ($ok) { Write-Host "PASS: $Name" -ForegroundColor Green }
        else { Write-Host "FAIL: $Name" -ForegroundColor Red; $script:fail++ }
    } catch {
        Write-Host "FAIL: $Name ($($_.Exception.Message.Split("`n")[0]))" -ForegroundColor Red; $script:fail++
    }
}

Check "wsl-alive" { (wsl -d Ubuntu -- echo ok 2>$null) -match "ok" }
Check "cs-daemon-8000" {
    $c = (curl.exe -s -o NUL -w "%{http_code}" --max-time 8 http://127.0.0.1:8000/ 2>$null)
    $c -in "200","401","403"
}
Check "glm-router-8231" {
    $c = (curl.exe -s -o NUL -w "%{http_code}" -X POST http://127.0.0.1:8231/v1/messages -H "Content-Type: application/json" -d "{}" --max-time 8 2>$null)
    $c -in "400","404","405","200"  # 400 = alive (empty body rejected)
}
Check "biomni-web-7860" {
    $c = (curl.exe -s -o NUL -w "%{http_code}" --max-time 8 http://127.0.0.1:7860/ 2>$null)
    $c -eq "200"
}
Check "biomni-mcp-7870" {
    $c = (curl.exe -s -o NUL -w "%{http_code}" -X POST http://127.0.0.1:7870/mcp -H "Content-Type: application/json" -d "{}" --max-time 8 2>$null)
    $c -in "400","405","200"
}
Check "basic-memory-18765" {
    $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"goat-health","version":"1.0"}}}'
    $c = (curl.exe -s -o NUL -w "%{http_code}" -X POST http://127.0.0.1:18765/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d $body --max-time 10 2>$null)
    $c -eq "200"
}
Check "cs-connector-registration" {
    wsl -d Ubuntu -- bash -c "grep -q 'biomni-a1' /home/prekzursil/.claude-science/mcp/local-mcp.json 2>/dev/null" 2>$null
    $LASTEXITCODE -eq 0
}
Check "biomni-env-key-present" {
    wsl -d Ubuntu -- bash -c "grep -q '^BIOMNI_CUSTOM_API_KEY=.\{20,\}' /home/prekzursil/Biomni/.env 2>/dev/null" 2>$null
    $LASTEXITCODE -eq 0
}
if (-not $SkipKeyProbe) {
    Check "glm-key-liveness" {
        $key = [Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User")
        if (-not $key) { return $false }
        $body = '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":8}'
        try {
            $req = [System.Net.Http.HttpRequestMessage]::new("POST", "https://api.z.ai/api/coding/paas/v4/chat/completions")
            $req.Headers.Add("Authorization", "Bearer $key")
            $req.Content = [System.Net.Http.StringContent]::new($body, [Text.Encoding]::UTF8, "application/json")
            $resp = [System.Net.Http.HttpClient]::new().SendAsync($req).GetAwaiter().GetResult()
            $resp.StatusCode.value__ -eq 200
        } catch { $false }
    }
}
$tier = wsl -d Ubuntu -- bash -c "grep '^BIOMNI_LLM=' /home/prekzursil/Biomni/.env 2>/dev/null | cut -d= -f2" 2>$null
Write-Host "INFO: biomni tier = $tier ; router default = glm-5.3 (flash via CS_GLM_MODEL)"

if ($fail -eq 0) { Write-Host "GOAT:HEALTHY (all checks passed)" -ForegroundColor Green; exit 0 }
else { Write-Host "GOAT:DEGRADED ($fail failed)" -ForegroundColor Red; exit 1 }
