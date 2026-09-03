#Requires -Version 5.1
<#
.SYNOPSIS
  Launch CyberStrike only from the dedicated engagement tree (grill G-8 A).
.DESCRIPTION
  Refuses HOME, source checkouts, and any cwd outside
  Cowork\private\cyberstrike-engagements. Default engagement is
  D:\opt\cyberstrike-mcp\current-engagement.txt.
#>
$ErrorActionPreference = 'Stop'
$EngageRoot = 'C:\Users\Prekzursil\Cowork\private\cyberstrike-engagements'
$Pointer = 'D:\opt\cyberstrike-mcp\current-engagement.txt'
$Banned = @(
  'C:\Users\Prekzursil',
  'C:\Users\Prekzursil\source',
  'C:\Users\Prekzursil\.agents',
  'C:\Users\Prekzursil\.codex',
  'C:\Users\Prekzursil\.claude',
  'C:\Users\Prekzursil\.grok'
)

function Get-EngagementDir {
  if ($env:CYBERSTRIKE_ENGAGEMENT_DIR) {
    return [IO.Path]::GetFullPath($env:CYBERSTRIKE_ENGAGEMENT_DIR)
  }
  $name = (Get-Content -LiteralPath $Pointer -TotalCount 1).Trim()
  if (-not $name) { throw "current-engagement.txt is empty" }
  return [IO.Path]::GetFullPath((Join-Path $EngageRoot $name))
}

function Assert-EngagementPath([string]$dir) {
  $full = [IO.Path]::GetFullPath($dir)
  $rootFull = [IO.Path]::GetFullPath($EngageRoot).TrimEnd('\') + '\'
  if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw "G-8 A: engagement path must live under $EngageRoot (got $full)"
  }
  if (-not (Test-Path -LiteralPath $full -PathType Container)) {
    throw "G-8 A: engagement directory does not exist: $full"
  }
  foreach ($b in $Banned) {
    if ($full.TrimEnd('\').Equals([IO.Path]::GetFullPath($b).TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
      throw "G-8 A: refused launch from $full"
    }
  }
}

$dir = Get-EngagementDir
Assert-EngagementPath $dir
$node = 'C:\Program Files\nodejs\node.exe'
$bin = Join-Path $env:APPDATA 'npm\node_modules\@cyberstrike-io\cyberstrike\bin\cyberstrike'
if (-not (Test-Path -LiteralPath $node)) { throw "node.exe missing: $node" }
if (-not (Test-Path -LiteralPath $bin)) { throw "cyberstrike bin missing: $bin" }
# Invoke node with a real argv array. The npm cyberstrike.ps1 shim passes `$args`
# unsplatted, which joins `-s` + `--prompt` into ONE argument and makes
# GET /session/<id> --prompt ... → "session not found".
$csArgs = New-Object System.Collections.Generic.List[string]
$csArgs.Add($dir)
foreach ($a in $args) { $csArgs.Add([string]$a) }
Write-Host ("G-8 A launch dir={0} argc={1}" -f $dir, $csArgs.Count)
Set-Location -LiteralPath $dir
& $node $bin @($csArgs.ToArray())
exit $LASTEXITCODE
