[IO.File]::ReadAllBytes('C:\Users\Prekzursil\.agents\wsl_move_out.log') | ForEach-Object {} | Out-Null
$t = [Text.Encoding]::Unicode.GetString([IO.File]::ReadAllBytes('C:\Users\Prekzursil\.agents\wsl_move_out.log'))
($t -replace '[^\x20-\x7E\r\n]','')
Write-Output '--- raw hexdump head ---'
$b = [IO.File]::ReadAllBytes('C:\Users\Prekzursil\.agents\wsl_move_out.log')
($b[0..([Math]::Min(300,$b.Length-1))] | ForEach-Object { $_.ToString('X2') }) -join ' '
