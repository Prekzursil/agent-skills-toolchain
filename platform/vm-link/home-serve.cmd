@echo off
REM Home side of the VM<->home link. Mirror of serve.cmd on offload-w2025.
REM Bound to the tailnet address ONLY - never 0.0.0.0.
REM Registered as a boot-triggered scheduled task by install-home-service.ps1.
set RCLONE=C:\Users\prekzursil\.local\bin\rclone.exe
set VMLINK=C:\ProgramData\vm-link
start "" /b "%RCLONE%" serve sftp C:\ --addr 100.97.16.36:2022 --user link --authorized-keys "%USERPROFILE%\.ssh\authorized_keys" --key "%VMLINK%\host_ed25519" --vfs-cache-mode writes --log-file "%VMLINK%\serve-c.log" --log-level INFO
start "" /b "%RCLONE%" serve sftp D:\ --addr 100.97.16.36:2023 --user link --authorized-keys "%USERPROFILE%\.ssh\authorized_keys" --key "%VMLINK%\host_ed25519" --vfs-cache-mode writes --log-file "%VMLINK%\serve-d.log" --log-level INFO
