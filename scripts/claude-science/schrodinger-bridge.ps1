# On-demand Schrodinger MCP -> HTTP/SSE bridge for Claude Science.
# WSL2 mirrored networking shares localhost, so the WSL daemon reaches this at the same URL.
#
# USAGE: run this script, then in Claude Science:  Customize > Connectors > + Add connector
#        URL: http://127.0.0.1:9000/sse   (transport: SSE)   name: Schrodinger
# Stop with Ctrl-C (or close the window). Only needs to run while you use Schrodinger in Claude Science.

$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\Prekzursil\source\repos\schrodinger-mcp'
$py   = Join-Path $repo '.venv\Scripts\python.exe'
$port = 9000

if (-not (Test-Path -LiteralPath $py))        { throw "schrodinger-mcp venv python not found: $py" }
if (-not (Test-Path -LiteralPath (Join-Path $repo 'server.py'))) { throw "server.py not found in $repo" }
$env:SCHRODINGER = 'D:\Program Files\Schrodinger 2026-2'

Set-Location $repo
Write-Host "Schrodinger bridge -> http://127.0.0.1:$port/sse   (SCHRODINGER=$env:SCHRODINGER)"
Write-Host "Add that URL in Claude Science: Customize > Connectors > + Add connector (transport SSE)."
# supergateway wraps the stdio MCP server as SSE
npx -y supergateway --stdio "`"$py`" server.py" --port $port --cors --healthEndpoint /healthz
