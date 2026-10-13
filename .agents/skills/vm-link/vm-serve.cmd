@echo off
rem serve.cmd v2 (vm side) - VM-AGNOSTIC: binds the CURRENT tailscale IPv4 at
rem runtime, so a mirrored/renamed VM (new tailnet IP) self-heals on boot.
setlocal enableextensions
set RCLONE=C:\Users\prekzursil\.local\bin\rclone.exe
set VMLINK=C:\ProgramData\vm-link
set TSIP=
for /f "usebackq delims=" %%I in (`"C:\Program Files\Tailscale\tailscale.exe" ip -4 2^>nul`) do set TSIP=%%I
if "%TSIP%"=="" (
  echo [%date% %time%] no tailscale IP - aborting serve >> "%VMLINK%\serve.err.log"
  exit /b 1
)

netstat -ano | findstr /C:"%TSIP%:2022" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp C:\ --addr %TSIP%:2022 --user link --authorized-keys "%VMLINK%\authorized_keys" --key "%VMLINK%\host_ed25519" --vfs-cache-mode writes --log-file "%VMLINK%\serve-c.log" --log-level INFO
)
netstat -ano | findstr /C:"%TSIP%:2023" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp D:\ --addr %TSIP%:2023 --user link --authorized-keys "%VMLINK%\authorized_keys" --key "%VMLINK%\host_ed25519" --vfs-cache-mode writes --log-file "%VMLINK%\serve-d.log" --log-level INFO
)
echo [%date% %time%] serving on %TSIP% >> "%VMLINK%\serve-ok.log"
