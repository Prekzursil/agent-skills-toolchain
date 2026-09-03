@echo off
set "SLIVER_OPERATOR_CONFIG=C:\Users\Prekzursil\.local\opt\sliver\operators\cyberstrike_127.0.0.1.cfg"
set "SLIVER_FULL_MCP_HOST=127.0.0.1"
set "SLIVER_FULL_MCP_PORT=31381"
set "PYTHONUNBUFFERED=1"
"C:\Users\Prekzursil\.local\opt\sliver-mcp\.venv\Scripts\python.exe" "D:\opt\cyberstrike-mcp\sliver-full-http.py"
