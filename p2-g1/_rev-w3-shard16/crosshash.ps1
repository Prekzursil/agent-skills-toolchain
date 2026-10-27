$ErrorActionPreference = 'Stop'
$root = 'C:\Users\Prekzursil\p2-g1'
$sha = [System.Security.Cryptography.SHA256]::Create()
$cat = Get-Content (Join-Path $root 'command-center\WORK-UNIT-CATALOG.json') -Raw | ConvertFrom-Json
foreach ($u in 'RES-0044','RES-0089','RES-0111') {
  $e = $cat.work_units | Where-Object { $_.id -eq $u }
  $p = Join-Path $root $e.output_path
  $raw = [System.IO.File]::ReadAllText($p)
  $norm = $raw.Replace("`r`n", "`n")
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($norm)
  $h = $sha.ComputeHash($bytes)
  $hex = ($h | ForEach-Object { $_.ToString('x2') }) -join ''
  Write-Output ("{0} ps-sha={1}" -f $u, $hex)
}
$sha.Dispose()
