$r1 = Test-NetConnection 100.97.16.36 -Port 2022 -WarningAction SilentlyContinue
$r2 = Test-NetConnection 100.97.16.36 -Port 2023 -WarningAction SilentlyContinue
Write-Output ("2022: " + $r1.TcpTestSucceeded + "  2023: " + $r2.TcpTestSucceeded)
