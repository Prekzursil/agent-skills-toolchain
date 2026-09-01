# cursor-hook-log.ps1 — Wave B (2026-08-27) generic observe-mode Cursor hook logger.
# P0 fix 2026-08-28: if -Allow, emit {"permission":"allow"} FIRST (UTF-8 no BOM);
# strip stdin BOM; write jsonl via UTF-8 no-BOM AppendAllText (never splice raw BOM
# into a JSON string). FAIL-OPEN: any error swallowed, exit always 0. Never vetoes.
param(
    [string]$LogName = "cursor-hooks-misc.jsonl",
    [switch]$Allow
)
$ErrorActionPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding $false
try { [Console]::OutputEncoding = $utf8 } catch {}
if ($Allow) {
    [Console]::Out.Write('{"permission":"allow"}')
    [Console]::Out.Flush()
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $raw = [Console]::In.ReadToEnd()
    if ($null -eq $raw) { $raw = "" }
    $raw = $raw.Trim().Trim([char]0xFEFF)
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = "{}" }
    $payloadJson = "{}"
    try {
        $parsed = $raw | ConvertFrom-Json
        $payloadJson = $parsed | ConvertTo-Json -Compress -Depth 8
    } catch {
        $esc = $raw -replace '\\', '\\\\' -replace '"', '\"' -replace "`t", ' ' -replace "[`r`n]+", ' '
        $payloadJson = '{"_unparsed":"' + $esc + '"}'
    }
    $logDir = "C:\Users\Prekzursil\.agents\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $line = '{"ts":"' + $ts + '","hook_ms":' + $sw.ElapsedMilliseconds + ',"payload":' + $payloadJson + '}'
    $logPath = Join-Path $logDir $LogName
    [System.IO.File]::AppendAllText($logPath, $line + [Environment]::NewLine, $utf8)
} catch { }
exit 0
