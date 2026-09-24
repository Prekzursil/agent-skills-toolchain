@echo off
start "" /b "C:\Users\prekzursil\.local\bin\rclone.exe" mount homeC:/ L: --vfs-cache-mode writes --log-file "C:\ProgramData\vm-link\mount-L.log" --log-level INFO
start "" /b "C:\Users\prekzursil\.local\bin\rclone.exe" mount homeD:/ M: --vfs-cache-mode writes --log-file "C:\ProgramData\vm-link\mount-M.log" --log-level INFO

