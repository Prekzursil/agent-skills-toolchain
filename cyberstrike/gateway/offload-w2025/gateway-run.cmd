@echo off
rem Launcher for the scheduled task: file-redirected so rich/uvicorn logging
rem can never block on a hidden-session console (the 2026-10-01 wedge cause:
rem logging handler lock held by a blocked console write froze the event loop).
cd /d D:\opt\cyberstrike-mcp
C:\Python314\python.exe -u gateway-server.py >> logs\gateway.out.log 2>> logs\gateway.err.log
