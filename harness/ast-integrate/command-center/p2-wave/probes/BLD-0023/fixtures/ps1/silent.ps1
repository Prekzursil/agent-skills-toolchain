Get-ChildItem -Path C:\missing -ErrorAction SilentlyContinue
Get-Item -Path C:\also-missing -EA SilentlyContinue
$ErrorActionPreference = 'SilentlyContinue'
