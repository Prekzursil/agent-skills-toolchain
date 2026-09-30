# cyberstrike-launch.ps1 - full CyberStrike session launcher
# Auto-loads estate instructions/config: run from this reviewed kit dir,
# never from an untrusted checkout.
param(
    [string]$Model = "ollama-local/qwen3:4b",
    [switch]$Web
)
$env:CYBERSTRIKE_SERVER_PASSWORD = "CyberStrike-Estate-2026!x"
# OPENAI_API_KEY is already a user env var on this box.

if ($Web) {
    cyberstrike web --hostname 127.0.0.1 --port 4096
} else {
    cyberstrike --model $Model
}
