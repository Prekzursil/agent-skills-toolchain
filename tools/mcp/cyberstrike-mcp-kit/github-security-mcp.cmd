@echo off
cd /d "%~dp0node_modules\github-security-mcp"
"C:\Program Files\nodejs\node.exe" "%~dp0node_modules\github-security-mcp\dist\index.js" %*
