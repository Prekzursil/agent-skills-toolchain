# Control-bad: unquoted caret-bearing git revisions through PowerShell.
# windows-shell.md:2 / TST-0188 both-states: the scanner MUST fire here.
Set-Location $Repo
git rev-parse HEAD^
git rev-parse v1.4.1^{commit}
git show HEAD^1
