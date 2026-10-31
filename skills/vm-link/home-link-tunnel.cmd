@echo off
rem home-link-tunnel.cmd v2 - VM-AGNOSTIC reverse tunnel for the VM->home data path.
rem Target VM is read from C:\ProgramData\vm-link\target.conf (first line:
rem "user host" e.g. "prekzursil offload-w2025" or "prekzursil 100.117.115.55").
rem When jumping/mirroring VMs: update target.conf, kill the ssh loop, task
rem re-establishes on next pass. Loop re-reads config every pass.
setlocal enableextensions
set ROOT=C:\ProgramData\vm-link
set RCLONE=%ROOT%\rclone.exe
set AK=%ROOT%\authorized_keys
set KEY=%ROOT%\host_ed25519
set SKEY=%ROOT%\home_to_vm

netstat -ano | findstr /C:"127.0.0.1:21222" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp C:\ --addr 127.0.0.1:21222 --user link --authorized-keys "%AK%" --key "%KEY%" --vfs-cache-mode writes --log-file "%ROOT%\serve-lo-c.log" --log-level INFO
)
netstat -ano | findstr /C:"127.0.0.1:21223" | findstr LISTENING >nul
if errorlevel 1 (
  start "" /b "%RCLONE%" serve sftp D:\ --addr 127.0.0.1:21223 --user link --authorized-keys "%AK%" --key "%KEY%" --vfs-cache-mode writes --log-file "%ROOT%\serve-lo-d.log" --log-level INFO
)
timeout /t 3 /nobreak >nul

:loop
set VMUSER=prekzursil
set VMHOST=100.117.115.55
if exist "%ROOT%\target.conf" (
  for /f "usebackq tokens=1,2" %%A in ("%ROOT%\target.conf") do (
    set VMUSER=%%A
    set VMHOST=%%B
  )
)
ssh -i "%SKEY%" ^
  -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=4 ^
  -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 ^
  -R 127.0.0.1:21022:127.0.0.1:21222 ^
  -R 127.0.0.1:21023:127.0.0.1:21223 ^
  -N %VMUSER%@%VMHOST%
timeout /t 15 /nobreak >nul
goto loop
