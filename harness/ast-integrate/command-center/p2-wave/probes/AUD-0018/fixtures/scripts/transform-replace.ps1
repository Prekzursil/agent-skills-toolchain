param($SrcFile, $DestFile)
# AUD-0018 planted transform control: bytes are rewritten, not copied.
Get-Content -Path $SrcFile | ForEach-Object { $_ -replace 'SRC-OK', 'TRANSFORMED' } | Set-Content -Path $DestFile
