# Control-bad: unquoted caret-bearing git revisions through PowerShell.
Set-Location $Repo
git rev-parse HEAD^
git rev-parse v1.4.1^{commit}
git show HEAD^1
