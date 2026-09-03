@echo off
REM Loopback-only Streamable HTTP front for official sliver-client mcp (stdio).
REM Default mcp-proxy host is "::" — MUST pass 127.0.0.1.
"C:\Program Files\nodejs\node.exe" "D:\opt\cyberstrike-mcp\node_modules\mcp-proxy\dist\bin\mcp-proxy.mjs" --host 127.0.0.1 --port 31380 --server stream -- "C:\Users\Prekzursil\.local\opt\sliver\sliver-client.exe" mcp --config "C:\Users\Prekzursil\.local\opt\sliver\operators\cyberstrike_127.0.0.1.cfg" --disable-wg
