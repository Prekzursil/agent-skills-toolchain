# One-off: remove ONLY byte-identical duplicate Cursor state.vscdb copies.
# Keeps 09-18's copy (identical content) and every OTHER file in each backup dir
# (browser cookies, trust tokens, Local State, wal/shm) — those may hold distinct
# values/JWTs. Deletes a target ONLY if its hash matches the keeper at run time.
$ErrorActionPreference = 'Stop'
$base   = 'C:\Users\Prekzursil\Cowork\private'
$keeper = Join-Path $base 'cursor-desktop-auth-backup_2026-09-18\cursor-globalStorage\state.vscdb'
$targets = '2026-09-12','2026-09-13','2026-09-14','2026-09-15','2026-09-16' | ForEach-Object {
  Join-Path $base "cursor-desktop-auth-backup_$_\cursor-globalStorage\state.vscdb" }

if(-not (Test-Path $keeper)){ Write-Output 'ABORT: keeper 09-18 state.vscdb missing'; return }
$kh = (Get-FileHash $keeper -Algorithm SHA256).Hash
Write-Output "KEEPER 09-18 hash=$($kh.Substring(0,16))  (identical content preserved here)"
$freed = 0
foreach($t in $targets){
  if(-not (Test-Path $t)){ Write-Output "skip (absent): $t"; continue }
  $th = (Get-FileHash $t -Algorithm SHA256).Hash
  if($th -eq $kh){
    $sz = (Get-Item $t).Length
    [System.IO.File]::Delete($t)
    $freed += $sz
    Write-Output ("DELETED {0:N2}GB  {1}" -f ($sz/1GB), (Split-Path $t -Parent | Split-Path -Leaf))
  } else {
    Write-Output "KEPT (hash differs = distinct content): $t"
  }
}
Write-Output ("FREED={0:N2}GB" -f ($freed/1GB))
