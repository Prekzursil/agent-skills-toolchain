param($Src, $Dest)
# AUD-0018 planted guarded sync: Copy-Item -Force plus the three named guards.
Get-ChildItem -Path $Src -File -Recurse | ForEach-Object {
  $rel = $_.FullName.Substring($Src.Length).TrimStart('\', '/')
  # guard: nested-repo
  if (Test-Path (Join-Path $_.DirectoryName '.git')) { continue }
  # guard: vendored-tree
  if ($rel -match '(^|\\|/)vendor(\\|/|$)') { continue }
  # guard: repo-owned-file
  if (Test-Path ($_.FullName + '.repo-owned')) { continue }
  $target = Join-Path $Dest $rel
  Copy-Item -Path $_.FullName -Destination $target -Force
}
