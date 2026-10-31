<#
.SYNOPSIS
  Round-3 item #5 — on-demand Claude Code OpenTelemetry TRACE capture.

  Stands up a local Jaeger OTLP collector (via Docker) and prints the env vars
  to launch `claude` with enhanced trace export. Produces a latency-resolved
  span tree across tool / permission / hook / subagent / Bash boundaries — the
  forensic view for diagnosing a stalled orchestration run (Ralph, metaswarm,
  codex council). ON-DEMAND ONLY: do not leave telemetry always-on.

.NOTES
  Beta (CLAUDE_CODE_ENHANCED_TELEMETRY_BETA): span names/attributes may churn —
  pin a CC version when you rely on it. Requires Docker running.
  Caveat: native batching can lose the tail if the CLI is killed mid-run; for
  long/killable Ralph loops prefer the `cc-trace` hook (records per-tool,
  exports on Stop) instead of this native path.
  Keep OTEL_LOG_TOOL_CONTENT unset/false — content stays opt-in (no log-everything).
#>
[CmdletBinding()]
param([int]$JaegerUiPort = 16686, [int]$OtlpPort = 4318)

$ErrorActionPreference = 'Stop'

Write-Host "1) Starting local Jaeger all-in-one (OTLP http on $OtlpPort, UI on $JaegerUiPort)..." -ForegroundColor Cyan
docker run -d --name verdict-jaeger -p "${JaegerUiPort}:16686" -p "${OtlpPort}:4318" jaegertracing/all-in-one:latest | Out-Null
Write-Host "   Jaeger UI: http://localhost:$JaegerUiPort" -ForegroundColor Green

Write-Host "`n2) Launch Claude Code in a NEW terminal with these env vars set, then reproduce the stall:" -ForegroundColor Cyan
@"
`$env:CLAUDE_CODE_ENABLE_TELEMETRY = '1'
`$env:CLAUDE_CODE_ENHANCED_TELEMETRY_BETA = '1'
`$env:OTEL_TRACES_EXPORTER = 'otlp'
`$env:OTEL_EXPORTER_OTLP_PROTOCOL = 'http/protobuf'
`$env:OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:$OtlpPort'
`$env:OTEL_TRACES_EXPORTER_INTERVAL = '1000'   # flush ~1s so a kill loses less
# leave OTEL_LOG_TOOL_CONTENT unset (content opt-in)
claude
"@ | Write-Host -ForegroundColor Yellow

Write-Host "`n3) Inspect the span tree in the Jaeger UI (service 'claude-code'). When done:" -ForegroundColor Cyan
Write-Host "   docker rm -f verdict-jaeger" -ForegroundColor Yellow
Write-Host "`n   For long/killable runs, prefer the cc-trace hook (no live collector, survives kills)." -ForegroundColor DarkGray
