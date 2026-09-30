@echo off
set ROOT=C:\ProgramData\vm-link
set RCLONE=%ROOT%\rclone.exe
set AK=%ROOT%\authorized_keys
set KEY=%ROOT%\host_ed25519
set TSIP=
for /f "usebackq delims=" %%I in (`"C:\Program Files\Tailscale\tailscale.exe" ip -4 2^>nul`) do set TSIP=%%I
if "%TSIP%"=="" set TSIP=100.97.16.36

netstat -ano | findstr /C:"%TSIP%:2022" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp C:\ --addr %TSIP%:2022 --user link --authorized-keys "%AK%" --key "%KEY%" --vfs-cache-mode writes --log-file "%ROOT%\serve-c.log" --log-level INFO
)

netstat -ano | findstr /C:"%TSIP%:2023" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp D:\ --addr %TSIP%:2023 --user link --authorized-keys "%AK%" --key "%KEY%" --vfs-cache-mode writes --log-file "%ROOT%\serve-d.log" --log-level INFO
)
exit /b 0
