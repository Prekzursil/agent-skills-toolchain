# shell-guard.ps1 — Cursor beforeShellExecution.
# 2026-08-28: UTF-8 Input+Output encoding (no BOM). Classify in-memory, THEN emit JSON,
# THEN log. AUTO-DENY estate locks; observe-only for diskpart/format/reg.
# FAIL-OPEN on parse error. Exit always 0.
$ErrorActionPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding $false
try { [Console]::InputEncoding = $utf8 } catch {}
try { [Console]::OutputEncoding = $utf8 } catch {}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$verdict = "ok"
$reason = ""
$cmd = ""
$raw = ""
try {
    $raw = [Console]::In.ReadToEnd()
    if ($null -eq $raw) { $raw = "" }
    $raw = $raw.Trim()
    $raw = $raw.Trim([char]0xFEFF)
    if ($raw.Length -ge 3 -and $raw[0] -eq [char]0x00EF) {
        # mis-decoded UTF-8 BOM as latin-1
    }
    if ($raw.StartsWith([string]([char]0x00EF) + [char]0x00BB + [char]0x00BF)) {
        $raw = $raw.Substring(3)
    }
    if ($raw.StartsWith('ï»¿')) { $raw = $raw.Substring(3) }
    try {
        $payload = $raw | ConvertFrom-Json
        $cmd = [string]$payload.command
        if ([string]::IsNullOrEmpty($cmd)) { $cmd = [string]$payload.cmd }
        if ([string]::IsNullOrEmpty($cmd) -and $payload.tool_input) {
            $cmd = [string]$payload.tool_input.command
        }
        if ([string]::IsNullOrEmpty($cmd) -and $payload.toolInput) {
            $cmd = [string]$payload.toolInput.command
        }
    } catch {
        if ($raw -match '"command"\s*:\s*"((?:\\.|[^"\\])*)"') {
            $cmd = $Matches[1] -replace '\\"', '"' -replace '\\\\', '\'
        }
    }
} catch { $cmd = "" }

function Test-EstateDeny([string]$c) {
    if ([string]::IsNullOrEmpty($c)) { return $null }
    if ($c -match 'credential[_-]?rotation[_-]?manifest') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): do not touch a credential-rotation manifest.')
    }
    if ($c -match 'rotate[_-]?credentials?') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): do not rotate credentials.')
    }
    if ($c -match 'gh\s+auth\s+refresh') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): gh auth refresh is rotation.')
    }
    if ($c -match 'aws\s+iam\s+(create|delete|update)-access-key') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): aws iam access-key mutation.')
    }
    if ($c -match 'az\s+ad\s+app\s+credential\s+(reset|delete)') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): az credential reset.')
    }
    if ($c -match 'gcloud\s+iam\s+service-accounts\s+keys\s+(create|delete)') {
        return @('never-rotate', 'NEVER-ROTATE (28.08.2026): gcloud key create/delete.')
    }
    if ($c -match 'gh\s+repo\s+edit' -and $c -match '--visibility\s+public') {
        return @('repo-public', 'PRIVATE-ONLY: refusing gh --visibility public.')
    }
    if ($c -match 'gh\s+repo\s+create' -and ($c -match '--public\b' -or $c -match '--visibility\s+public')) {
        return @('repo-public', 'PRIVATE-ONLY: refusing gh repo create --public.')
    }
    if ($c -match 'git\s+push' -and ($c -match '--force' -or $c -match '\s-f(\s|$)')) {
        return @('force-push', 'Refusing git push --force / --force-with-lease / -f.')
    }
    if ($c -match 'git\s+(commit|push|merge)' -and $c -match '--no-verify') {
        return @('no-verify', 'Refusing git --no-verify. Hooks are the safety layer.')
    }
    if ($c -match 'git\s+commit' -and $c -match '\s-n(\s|$)') {
        return @('no-verify', 'Refusing git commit -n (--no-verify).')
    }
    if ($c -match '\bgit\s+(add|commit|rm|update-index)\b') {
        if ($c -match '(^|[\\/ ])local\.json(\s|$)|(^|[\\/ ])[^\\/\s]+\.(pem|key|p12|pfx)(\s|$)|(^|[\\/ ])(?!.*tokeniz)[^\\/\s]*token[^\\/\s]*') {
            return @('secret-file', 'Refusing git write of raw secret files (*.key, *.pem, *token*, local.json).')
        }
    }
    return $null
}

$hit = $null
try { $hit = Test-EstateDeny $cmd } catch { $hit = $null }
if ($hit) {
    $verdict = $hit[0]
    $reason = $hit[1]
    $esc = $reason -replace '\\', '\\' -replace '"', '\"'
    [Console]::Out.Write('{"permission":"deny","agent_message":"' + $esc + '","user_message":"' + $esc + '"}')
    [Console]::Out.Flush()
} else {
    $denyObserve = @(
        '(^|[;&|]\s*)diskpart(\s|$)',
        '(^|[;&|]\s*)format(\.com)?\s+[a-zA-Z]:',
        '\breg(\.exe)?\s+delete\b',
        '\bbcdedit\s+/delete\b',
        '\bcipher\s+/w\b'
    )
    foreach ($p in $denyObserve) {
        if ($cmd -match $p) { $verdict = "would-deny"; break }
    }
    [Console]::Out.Write('{"permission":"allow"}')
    [Console]::Out.Flush()
}

try {
    $logDir = "C:\Users\Prekzursil\.agents\logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $cmdShort = if ($cmd.Length -gt 300) { $cmd.Substring(0, 300) + "..." } else { $cmd }
    $cmdEsc = $cmdShort -replace '\\', '\\\\' -replace '"', '\"' -replace "`t", ' ' -replace "[`r`n]+", ' '
    $head = ""
    if ($raw.Length -gt 0) {
        $n = [Math]::Min(24, $raw.Length)
        $chars = New-Object System.Collections.Generic.List[string]
        for ($i = 0; $i -lt $n; $i++) { [void]$chars.Add(('{0:X4}' -f [int]$raw[$i])) }
        $head = ($chars -join ' ')
    }
    $line = '{"ts":"' + $ts + '","hook":"beforeShellExecution","verdict":"' + $verdict + '","hook_ms":' + $sw.ElapsedMilliseconds + ',"command":"' + $cmdEsc + '","stdin_u16head":"' + $head + '"}'
    [System.IO.File]::AppendAllText((Join-Path $logDir "cursor-shell-guard.jsonl"), $line + [Environment]::NewLine, $utf8)
} catch { }
exit 0
