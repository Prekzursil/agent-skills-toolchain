# restore_env.ps1 - restore missing user env vars from the 2026-09-29 backups.
# Only fills vars that are missing / empty / literal ${...} placeholders in the
# live User scope. Never touches vars that already have values (PATH, ZAI_API_KEY...).
$ErrorActionPreference = 'Stop'
$backups = @(
    'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\user.env',
    'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\machine.env'
)
# system-managed / structural vars never restored from a backup
$skip = @('path','Path','PATH','PSModulePath','PATHEXT','ComSpec','OS','windir',
          'USERNAME','PROCESSOR_ARCHITECTURE','PROCESSOR_IDENTIFIER','PROCESSOR_LEVEL',
          'PROCESSOR_REVISION','NUMBER_OF_PROCESSORS','TEMP','TMP','DriverData',
          'POWERSHELL_DISTRIBUTION_CHANNEL','POWERSHELL_TELEMETRY_OPTOUT','ChocolateyInstall',
          'ZES_ENABLE_SYSMAN')
$restored = New-Object System.Collections.Generic.List[string]
$keptLive = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]
foreach ($f in $backups) {
    if (-not (Test-Path $f)) { throw "backup missing: $f" }
    $lines = [System.IO.File]::ReadAllLines($f)
    foreach ($line in $lines) {
        if ($line -notmatch '^[A-Za-z_][A-Za-z0-9_]*=') { continue }
        $idx = $line.IndexOf('=')
        $name = $line.Substring(0, $idx)
        $val = $line.Substring($idx + 1)
        if ($skip -contains $name) { $skipped.Add($name); continue }
        $cur = [Environment]::GetEnvironmentVariable($name, 'User')
        $broken = [string]::IsNullOrEmpty($cur) -or ($cur -match '^\$\{[^}]*\}$')
        if ($broken) {
            [Environment]::SetEnvironmentVariable($name, $val, 'User')
            $restored.Add($name)
        } else {
            $keptLive.Add($name)
        }
    }
}
Write-Output ("restored: " + $restored.Count)
Write-Output ("already-live-kept: " + $keptLive.Count)
Write-Output ("skipped-system: " + $skipped.Count)
Write-Output ("RESTORED-VARS: " + (($restored | Sort-Object -Unique) -join ','))
