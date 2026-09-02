# Windows-style tool resolver for CNF-0021.
# PATHEXT-aware so a .cmd shim is visible. Does not call POSIX which.
param(
    [Parameter(Mandatory = $true)]
    [string]$NameList,
    [string]$ExtraPath = '',
    [string]$JsonOut = ''
)
$ErrorActionPreference = 'Continue'
$Name = @($NameList -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if (-not $env:PATHEXT) {
    $env:PATHEXT = '.COM;.EXE;.BAT;.CMD;.cmd;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.CPL'
} elseif ($env:PATHEXT -notmatch '\.cmd') {
    $env:PATHEXT = $env:PATHEXT + ';.cmd;.CMD'
}
if ($ExtraPath) {
    $env:PATH = $ExtraPath + [IO.Path]::PathSeparator + $env:PATH
}

function Resolve-WindowsStyle {
    param([string]$Tool)
    $exts = New-Object System.Collections.Generic.List[string]
    [void]$exts.Add('')
    foreach ($e in ($env:PATHEXT -split ';')) {
        if (-not $e) { continue }
        foreach ($variant in @($e, $e.ToLowerInvariant(), $e.ToUpperInvariant())) {
            if (-not $exts.Contains($variant)) { [void]$exts.Add($variant) }
        }
    }
    foreach ($dir in ($env:PATH -split [IO.Path]::PathSeparator)) {
        if (-not $dir) { continue }
        foreach ($ext in $exts) {
            $candidate = Join-Path $dir ($Tool + $ext)
            if (Test-Path -LiteralPath $candidate) {
                try { return (Resolve-Path -LiteralPath $candidate).Path }
                catch { return $candidate }
            }
        }
    }
    $gc = Get-Command -Name $Tool -ErrorAction SilentlyContinue
    if ($null -eq $gc) { return $null }
    if ($gc.Source) { return [string]$gc.Source }
    if ($gc.Path) { return [string]$gc.Path }
    return $null
}

$rows = New-Object System.Collections.Generic.List[object]
foreach ($n in $Name) {
    $src = Resolve-WindowsStyle -Tool $n
    $ver = $null
    if ($src) {
        foreach ($flag in @('--version', '-V', 'version')) {
            try {
                $out = & $src $flag 2>&1 | Out-String
                $line = ($out -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 1)
                if ($line) { $ver = $line.Trim(); break }
            } catch { }
        }
    }
    $rows.Add([pscustomobject]@{
            name              = $n
            resolved          = [bool]$src
            source            = $src
            version_verbatim  = $ver
            engine            = 'pwsh-windows-pathext'
            posix_which_used  = $false
        }) | Out-Null
}
$json = @($rows.ToArray()) | ConvertTo-Json -Depth 6 -Compress
if ($null -eq $json) { $json = '[]' }
if (-not $json.StartsWith('[')) { $json = '[' + $json + ']' }
if ($JsonOut) {
    [System.IO.File]::WriteAllText($JsonOut, $json)
} else {
    Write-Output $json
}
