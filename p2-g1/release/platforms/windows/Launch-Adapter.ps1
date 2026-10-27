# Windows launch adapter (PowerShell surface) for IMP-0013.
# PATHEXT-aware resolve; never Git-Bash; UseShellExecute pinned false.
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string[]]$ArgumentList = @(),
    [string[]]$PathDirs = @()
)

function Get-AdapterCommand {
    param([string]$ToolName, [string[]]$Dirs)
    $exts = @('', '.COM', '.EXE', '.BAT', '.CMD')
    foreach ($dir in $Dirs) {
        foreach ($ext in $exts) {
            $cand = Join-Path $dir ($ToolName + $ext)
            if (Test-Path -LiteralPath $cand -PathType Leaf) {
                return $cand
            }
        }
    }
    return $null
}

$search = if ($PathDirs.Count -gt 0) { $PathDirs } else { $env:PATH -split ';' }
$resolved = Get-AdapterCommand -ToolName $Name -Dirs $search
if (-not $resolved) {
    Write-Error "ERROR:TOOL_NOT_FOUND $Name"
    exit 2
}

# LAUNCH-PATH-BEGIN
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $resolved
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
if ($ArgumentList) {
    $psi.Arguments = ($ArgumentList -join ' ')
}
$proc = [System.Diagnostics.Process]::Start($psi)
$stdout = $proc.StandardOutput.ReadToEnd()
$stderr = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()
Write-Output $stdout
if ($stderr) { Write-Error $stderr }
exit $proc.ExitCode
# LAUNCH-PATH-END
