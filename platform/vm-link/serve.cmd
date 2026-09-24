@echo off
start "" /b "C:\Users\prekzursil\.local\bin\rclone.exe" serve sftp C:\ --addr 100.117.115.55:2022 --user link --authorized-keys "C:\ProgramData\vm-link\authorized_keys" --key "C:\ProgramData\vm-link\host_ed25519" --vfs-cache-mode writes --log-file "C:\ProgramData\vm-link\serve-c.log" --log-level INFO
start "" /b "C:\Users\prekzursil\.local\bin\rclone.exe" serve sftp D:\ --addr 100.117.115.55:2023 --user link --authorized-keys "C:\ProgramData\vm-link\authorized_keys" --key "C:\ProgramData\vm-link\host_ed25519" --vfs-cache-mode writes --log-file "C:\ProgramData\vm-link\serve-d.log" --log-level INFO

