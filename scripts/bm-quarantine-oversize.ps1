# Move vault markdown >100 KB out of D:\basic-memory and leave a pointer.
# Idempotent. Never deletes permanently. Skips files that are already pointers
# (frontmatter status: quarantined). Does not bind :8765. Does not reindex.
$ErrorActionPreference = 'Stop'
$Vault = 'D:\basic-memory'
$Stamp = Get-Date -Format 'yyyy-MM-dd'
$DestRoot = Join-Path 'C:\Users\Prekzursil\.basic-memory\quarantine' $Stamp
$Limit = 100000
$SkipDirs = @('.models', '.hf', '.git', 'node_modules', '__pycache__')

New-Item -ItemType Directory -Force -Path $DestRoot | Out-Null
$manifestPath = Join-Path $DestRoot 'MANIFEST.json'
$entries = @()
if (Test-Path $manifestPath) {
    try { $entries = @(Get-Content $manifestPath -Raw | ConvertFrom-Json) } catch { $entries = @() }
}

function Test-AlreadyPointer([string]$Path) {
    try {
        $head = Get-Content -LiteralPath $Path -TotalCount 20 -ErrorAction Stop
        return ($head -join "`n") -match 'status:\s*quarantined'
    } catch { return $false }
}

$files = Get-ChildItem -LiteralPath $Vault -File -Recurse -Filter '*.md' -ErrorAction SilentlyContinue |
    Where-Object {
        $relParts = $_.FullName.Substring($Vault.Length).Split([IO.Path]::DirectorySeparatorChar)
        -not ($relParts | Where-Object { $SkipDirs -contains $_ }) -and $_.Length -gt $Limit
    }

foreach ($f in $files) {
    if (Test-AlreadyPointer $f.FullName) { continue }
    $rel = $f.FullName.Substring($Vault.Length).TrimStart('\')
    $dest = Join-Path $DestRoot $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    $bytes = $f.Length
    Move-Item -LiteralPath $f.FullName -Destination $dest -Force
    $pointer = @"
---
title: $($f.BaseName) (quarantined)
type: index
status: quarantined
tags: [quarantine]
valid_as_of: $Stamp
---

# Pointer (not ingested)

Original size: $bytes bytes (>100 KB). Body moved out of the vault so FastEmbed cannot chunk it.

- Quarantine: ``$dest``
- Re-run: ``C:\Users\Prekzursil\.agents\scripts\bm-quarantine-oversize.ps1``
"@
    Set-Content -LiteralPath $f.FullName -Value $pointer -Encoding utf8
    $entries += [pscustomobject]@{ path = $rel; bytes = $bytes; dest = $dest; when = $Stamp }
}

($entries | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output "QUARANTINE notes=$($files.Count) manifest=$manifestPath"
