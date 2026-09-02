# Control-good: quoted / stop-parsing forms. Scanner must stay silent.
Set-Location $Repo
git rev-parse 'HEAD^'
git rev-parse "v1.4.1^{commit}"
git --% rev-parse HEAD^
