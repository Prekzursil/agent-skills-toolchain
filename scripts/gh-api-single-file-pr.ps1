<#
.SYNOPSIS
  Land a single-file change as a PR via the GitHub Contents API — NO local checkout.
.DESCRIPTION
  A fresh git worktree/clone of a git-crypt repo fails the smudge filter on encrypted
  files (no key), and a local branch switch can drag along uncommitted secrets. Doing the
  change SERVER-SIDE via `gh api` sidesteps both: no checkout, no smudge, no chance of
  committing the working tree's secrets. Ends with a SUCCESS:/FAILED: marker.
.EXAMPLE
  ./gh-api-single-file-pr.ps1 -Repo owner/repo -Path rules/common/x.md `
     -ContentFile .\x.md -Branch fix/x -Message "docs: x" -Title "docs: x"
#>
param(
  [Parameter(Mandatory)][string]$Repo,
  [Parameter(Mandatory)][string]$Path,
  [Parameter(Mandatory)][string]$ContentFile,
  [Parameter(Mandatory)][string]$Branch,
  [Parameter(Mandatory)][string]$Message,
  [Parameter(Mandatory)][string]$Title,
  [string]$Body = $Message,
  [string]$Base = "main"
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Output "FAILED:gh-api-single-file-pr need-gh-cli"; exit 3 }
if (-not (Test-Path $ContentFile)) { Write-Output "FAILED:gh-api-single-file-pr content-file-missing=$ContentFile"; exit 3 }

try {
  $baseSha = gh api "repos/$Repo/git/ref/heads/$Base" --jq .object.sha
  # create branch ref (tolerate 'already exists')
  try { gh api -X POST "repos/$Repo/git/refs" -f "ref=refs/heads/$Branch" -f "sha=$baseSha" *> $null }
  catch { Write-Warning "branch $Branch may already exist — reusing" }
  # current blob sha (empty => new file)
  $fileSha = ""
  try { $fileSha = gh api "repos/$Repo/contents/$Path`?ref=$Base" --jq .sha 2>$null } catch {}
  $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path $ContentFile)))
  $putArgs = @("-X","PUT","repos/$Repo/contents/$Path","-f","message=$Message","-f","content=$b64","-f","branch=$Branch")
  if ($fileSha) { $putArgs += @("-f","sha=$fileSha") }
  gh api @putArgs *> $null
  $url = gh pr create --repo $Repo --base $Base --head $Branch --title $Title --body $Body
  Write-Output "SUCCESS:gh-api-single-file-pr $Repo $Branch $Path -> $url"
} catch {
  Write-Output "FAILED:gh-api-single-file-pr $($_.Exception.Message)"
  exit 1
}
