$ErrorActionPreference = 'Stop'
$ps51 = $PSVersionTable.PSVersion.ToString()
Write-Output "PSVersion: $ps51"

# 1. Syntax parse check (no execution)
$errs = $null
$tokens = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile('C:\Users\prekzursil\.zcode\workspace\default\out\research\_gr\GraphRunner.ps1', [ref]$tokens, [ref]$errs)
Write-Output ("ParseErrors: " + $errs.Count)
foreach ($e in $errs) { Write-Output ("  " + $e.Message + " @line " + $e.Extent.StartLineNumber) }

# 2. Real import smoke test
Import-Module 'C:\Users\prekzursil\.zcode\workspace\default\out\research\_gr\GraphRunner.ps1' -Force
$mod = Get-Module GraphRunner
Write-Output ("ImportedOK: True ; ExportedFunctions: " + $mod.ExportedFunctions.Count)

# 3. Confirm key modules exist
foreach ($fn in @('Get-GraphTokens','Invoke-DumpCAPS','Invoke-DumpApps','Invoke-SearchMailbox','Invoke-GraphRecon','Invoke-SecurityGroupCloner','Invoke-InjectOAuthApp','Get-SharePointSiteURLs','Invoke-SearchUserAttributes','Invoke-MultiToken')) {
    if (Get-Command $fn -ErrorAction SilentlyContinue) { Write-Output ("  HAVE: " + $fn) } else { Write-Output ("  MISS: " + $fn) }
}
