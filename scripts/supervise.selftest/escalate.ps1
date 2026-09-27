# Stand-in ESCALATION for the self-test: proves the latch dispatched a DIFFERENT remediation
# rather than another restart. Real escalations would page, open a loop, or run a deeper repair.
param([string]$MarkerFile)
$ErrorActionPreference = 'SilentlyContinue'
# supervise.ps1 appends <Name> <Reason> after the configured -EscalateArgs
$rest = $args -join ' '
Add-Content -LiteralPath $MarkerFile -Value ("{0} ESCALATED {1}" -f (Get-Date).ToString('o'), $rest) -Encoding utf8
