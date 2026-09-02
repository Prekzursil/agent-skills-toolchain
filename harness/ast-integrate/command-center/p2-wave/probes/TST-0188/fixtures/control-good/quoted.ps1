# Control-good: sanctioned forms. The scanner MUST be silent here.
Set-Location $Repo
git rev-list -n 1 v1.4.1
git rev-parse 'HEAD^'
git rev-parse "v1.4.1^{commit}"
git --% rev-parse HEAD^
