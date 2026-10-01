# deploy.ps1 - deploy the estate Modal bench endpoint (needs creds live first)
$ErrorActionPreference = "Stop"
$Modal = "$env:APPDATA\Python\Python314\Scripts\modal.exe"
if (-not (Test-Path $Modal)) { $Modal = "modal" }
if (-not $env:MODAL_TOKEN_ID -or -not $env:MODAL_TOKEN_SECRET) {
    throw "MODAL_TOKEN_ID/SECRET not in env - see D:\opt\modal-gpu\README.md (values are home-side pending wake)"
}
& $Modal deploy "D:\opt\modal-gpu\bench_modal_app.py"
Write-Host ""
Write-Host "Paste the https://...modal.direct URL into providers-modal-qwen3-4b.json, set enabled=true, copy to D:\opt\sandbox-agents\providers\"
