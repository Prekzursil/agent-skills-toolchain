param(
    [string]$SessionId = 'ses_f8d44be61ffewvsgXK9huAdYmt'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$credentialName = 'ZAI_API_KEY_realprekzursil'
$credentialValue = [Environment]::GetEnvironmentVariable($credentialName, 'User')
$credentialScope = 'User'

if ([string]::IsNullOrWhiteSpace($credentialValue)) {
    $credentialValue = [Environment]::GetEnvironmentVariable($credentialName, 'Machine')
    $credentialScope = 'Machine'
}

if ([string]::IsNullOrWhiteSpace($credentialValue)) {
    throw "Required Windows credential '$credentialName' is not set at User or Machine scope."
}

if (-not [string]::IsNullOrWhiteSpace($SessionId) -and $SessionId -notmatch '^ses_[A-Za-z0-9]+$') {
    throw "Invalid CyberStrike session id: '$SessionId'."
}

$cyberstrikeCommand = Get-Command -Name 'cyberstrike' -ErrorAction Stop
$previousProcessValue = [Environment]::GetEnvironmentVariable($credentialName, 'Process')

try {
    # The credential value stays in process memory and is never written to argv, logs, or config.
    [Environment]::SetEnvironmentVariable($credentialName, $credentialValue, 'Process')
    Write-Host "Loaded $credentialName from Windows $credentialScope scope (value hidden)."

    if ([string]::IsNullOrWhiteSpace($SessionId)) {
        & $cyberstrikeCommand.Source
    }
    else {
        & $cyberstrikeCommand.Source -s $SessionId
    }
}
finally {
    [Environment]::SetEnvironmentVariable($credentialName, $previousProcessValue, 'Process')
}
