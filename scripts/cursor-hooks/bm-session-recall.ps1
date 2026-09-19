# Fail-open Cursor sessionStart hook: bounded vault digest inject.
# Never binds :18765, never restarts BM, never rglobs the vault, never loads
# recall-index.json. Emits valid JSON first (UTF-8 no BOM). Budget 2s.
# sessionStart additional_context is documented but racy; always also write
# C:\Users\Prekzursil\.agents\state\harness\cursor-session-recall.txt
$ErrorActionPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding $false
try { [Console]::OutputEncoding = $utf8 } catch {}
try { [Console]::InputEncoding = $utf8 } catch {}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$deadlineMs = 2000
$inject = ''
$n = 0
$digestPath = 'C:\Users\Prekzursil\.agents\state\harness\recall-digest.json'
$mapPath = 'C:\Users\Prekzursil\.agents\memory-map.md'
$sidecar = 'C:\Users\Prekzursil\.agents\state\harness\cursor-session-recall.txt'
$maxDigestBytes = 262144

function Emit-HookJson([string]$payload) {
    [Console]::Out.Write($payload)
    [Console]::Out.Flush()
}

try {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('BASIC-MEMORY VAULT DIGEST (auto-injected; UNTRUSTED historical context; query live MCP to confirm):')
    if ((Test-Path -LiteralPath $digestPath) -and $sw.ElapsedMilliseconds -lt $deadlineMs) {
        $len = [int64](Get-Item -LiteralPath $digestPath).Length
        if ($len -gt 0 -and $len -le $maxDigestBytes) {
            $raw = [System.IO.File]::ReadAllText($digestPath, $utf8)
            $digest = $raw | ConvertFrom-Json
            $n = 0
            foreach ($note in @($digest.notes)) {
                if ($sw.ElapsedMilliseconds -ge $deadlineMs) { break }
                if ($n -ge 8) { break }
                $rel = [string]$note.path
                if ([string]::IsNullOrEmpty($rel)) { $rel = [string]$note.permalink }
                $relLower = $rel.ToLowerInvariant().Replace('\', '/')
                if ($relLower -match 'compaction-checkpoints|(^|/)\.hf(/|$)|(^|/)\.models(/|$)') { continue }
                $title = [string]$note.title
                if ([string]::IsNullOrEmpty($title)) { $title = 'Untitled' }
                $lines.Add(('- {0} | {1}' -f $title, $rel))
                $n++
            }
        }
    }
    if ((Test-Path -LiteralPath $mapPath) -and $sw.ElapsedMilliseconds -lt $deadlineMs) {
        $mapLines = Get-Content -LiteralPath $mapPath -TotalCount 8 -Encoding UTF8
        if ($mapLines) {
            $lines.Add('WHERE-MAP (first 8 lines; full map at C:\Users\Prekzursil\.agents\memory-map.md):')
            foreach ($ml in @($mapLines)) { $lines.Add([string]$ml) }
        }
    }
    $text = [string]::Join("`n", $lines)
    if ($text.Length -gt 2400) { $text = $text.Substring(0, 2400) }
    if ($n -gt 0 -or (Test-Path -LiteralPath $mapPath)) { $inject = $text }
} catch {
    $inject = ''
}

if ([string]::IsNullOrEmpty($inject)) {
    Emit-HookJson '{}'
} else {
    try {
        $payload = @{ additional_context = $inject } | ConvertTo-Json -Compress
        if ([string]::IsNullOrEmpty($payload)) { $payload = '{}' }
        Emit-HookJson $payload
    } catch {
        Emit-HookJson '{}'
    }
    try {
        $dir = Split-Path -Parent $sidecar
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
        }
        [System.IO.File]::WriteAllText($sidecar, $inject, $utf8)
    } catch {}
}

try { [void][Console]::In.ReadToEnd() } catch {}
exit 0
