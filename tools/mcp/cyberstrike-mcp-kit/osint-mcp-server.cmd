@echo off
cd /d "%~dp0node_modules\osint-mcp-server"
"C:\Program Files\nodejs\node.exe" "%~dp0node_modules\osint-mcp-server\dist\index.js" %*
