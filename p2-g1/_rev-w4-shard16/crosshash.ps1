# Independent .NET SHA256 over CRLF->LF-normalized artifact bytes
# (cross-instrument check vs the python hashlib numbers in verify_out.json).
$ids = 'RES-0158','RES-0160','RES-0162','RES-0164','RES-0168','RES-0175','RES-0176','RES-0179','RES-0180','RES-0182','TST-0018','TST-0028'
$cat = Get-Content 'C:\Users\Prekzursil\p2-g1\command-center\WORK-UNIT-CATALOG.json' -Raw | ConvertFrom-Json
$byid = @{}
foreach ($u in $cat.work_units) { $byid[$u.id] = $u }
$root = 'C:\Users\Prekzursil\p2-g1'
$sha = [System.Security.Cryptography.SHA256]::Create()
$out = foreach ($id in $ids) {
  $rel = $byid[$id].output_path.Replace('\','/')
  $p = Join-Path $root $rel.Replace('/', '\')
  if (Test-Path -LiteralPath $p) {
    $bytes = [System.IO.File]::ReadAllBytes($p)
    $ms = New-Object System.IO.MemoryStream
    for ($i = 0; $i -lt $bytes.Length; $i++) {
      if ($bytes[$i] -eq 13 -and $i + 1 -lt $bytes.Length -and $bytes[$i+1] -eq 10) { continue }
      $ms.WriteByte($bytes[$i])
    }
    $norm = $ms.ToArray(); $ms.Dispose()
    $h = $sha.ComputeHash($norm)
    [PSCustomObject]@{ unit=$id; bytes=$norm.Length; sha256=([BitConverter]::ToString($h) -replace '-','').ToLower(); path=$rel }
  } else {
    [PSCustomObject]@{ unit=$id; bytes=-1; sha256='ABSENT'; path=$rel }
  }
}
$out | ConvertTo-Json -Depth 3 | Set-Content 'C:\Users\Prekzursil\p2-g1\_rev-w4-shard16\crosshash_out.json' -Encoding UTF8
$out | ForEach-Object { '{0} {1} {2}' -f $_.unit, $_.bytes, $_.sha256 }
