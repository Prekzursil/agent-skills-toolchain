<#
.SYNOPSIS
    Run headed focus-independent proofs for Chrome, then Edge, then Firefox.
    Always uses -Profile agent-persistent (explicit). Does not touch live browsers.
#>
[CmdletBinding()]
param(
    [ValidateSet('chrome', 'edge', 'firefox', 'all')]
    [string]$Lane = 'all'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$proofDir = $PSScriptRoot
$here = Split-Path -Parent $proofDir
$results = Join-Path $proofDir 'results'
if (-not (Test-Path -LiteralPath $results)) { New-Item -ItemType Directory -Path $results | Out-Null }
$fgFile = Join-Path $results 'foreground.json'

function Start-Decoy {
    $script = Join-Path $results 'decoy.ps1'
    @'
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = 'ESTATE-BROWSER-PROOF-FOREGROUND'
$form.Width = 480
$form.Height = 180
$form.TopMost = $true
$label = New-Object System.Windows.Forms.Label
$label.Dock = 'Fill'
$label.Text = "Proof decoy — keep this focused.`r`nAgent browser is driven without OS keystrokes."
$form.Controls.Add($label)
$form.Add_Shown({ $form.Activate(); $form.BringToFront() })
[System.Windows.Forms.Application]::Run($form)
'@ | Set-Content -LiteralPath $script -Encoding utf8
    $proc = Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile', '-File', $script) -PassThru
    Start-Sleep -Seconds 2
    return $proc
}

function Snapshot-Fg {
    & pwsh -NoProfile -File (Join-Path $here 'lib\Snapshot-Foreground.ps1') -OutFile $fgFile
}

$decoy = $null
try {
    Write-Output 'PROFILE_EXPLICIT=agent-persistent (b) — LIVE not used; would disturb owner windows'
    $decoy = Start-Decoy
    Snapshot-Fg

    if ($Lane -in @('all', 'chrome', 'edge')) {
        & pwsh -NoProfile -File (Join-Path $here 'Start-Hub.ps1') -Mode agent
        if ($LASTEXITCODE -ne 0) { throw "hub start failed: $LASTEXITCODE" }
    }

    foreach ($browser in @('chrome', 'edge')) {
        if ($Lane -notin @('all', $browser)) { continue }
        Write-Output "==== $browser agent-persistent proof ===="
        & pwsh -NoProfile -File (Join-Path $here 'Start-AgentBrowser.ps1') -Browser $browser -Profile agent-persistent
        if ($LASTEXITCODE -ne 0) { throw "$browser launch failed: $LASTEXITCODE" }
        Start-Sleep -Seconds 3
        Snapshot-Fg
        $decoy.Refresh()
        if (-not $decoy.HasExited) {
            # Re-assert decoy focus without touching owner Chrome/Edge titles.
            try {
                Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class FgBoost {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@ -ErrorAction SilentlyContinue
            } catch {}
            $main = (Get-Process -Id $decoy.Id -ErrorAction SilentlyContinue).MainWindowHandle
            if ($main -and $main -ne [IntPtr]::Zero) {
                [FgBoost]::SetForegroundWindow($main) | Out-Null
            }
        }
        Start-Sleep -Milliseconds 400
        Snapshot-Fg
        & node (Join-Path $proofDir 'prove-chromedge.mjs') --port 8770 --browser $browser --results $results --foreground-json $fgFile
        if ($LASTEXITCODE -ne 0) { throw "$browser proof failed: $LASTEXITCODE" }
        & pwsh -NoProfile -File (Join-Path $here 'Start-AgentBrowser.ps1') -Browser $browser -Profile agent-persistent -Stop
    }

    if ($Lane -in @('all', 'firefox')) {
        Write-Output '==== firefox agent-persistent proof ===='
        & pwsh -NoProfile -File (Join-Path $here 'Start-FirefoxAgent.ps1') -Profile agent-persistent
        $ffDir = Join-Path $env:USERPROFILE '.agents\browser-profiles\firefox-agent'
        Snapshot-Fg
        & python (Join-Path $proofDir 'prove-firefox.py') --profile agent-persistent --user-data-dir $ffDir --results $results --foreground-json $fgFile
        if ($LASTEXITCODE -ne 0) { throw "firefox proof failed: $LASTEXITCODE" }
    }

    Write-Output 'SUCCESS:focus-proof lanes complete'
} finally {
    if ($decoy -and -not $decoy.HasExited) {
        Stop-Process -Id $decoy.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process -Name powershell, pwsh -ErrorAction SilentlyContinue | Where-Object {
        $_.MainWindowTitle -eq 'ESTATE-BROWSER-PROOF-FOREGROUND'
    } | Stop-Process -Force -ErrorAction SilentlyContinue
}
