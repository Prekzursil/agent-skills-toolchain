param(
  [Parameter(Mandatory=$true)][string[]]$Tasks,
  [switch]$Revert
)
# Hide Scheduled-Task console pop-ups WITHOUT changing execution context.
# Method: rewrite the console action to run through runhidden.exe (a GUI-subsystem helper
# that CreateProcess()es the original command with CREATE_NO_WINDOW, waits, and returns its
# exit code). LogonType stays Interactive, so session / environment / DPAPI / network /
# desktop access and exit-code + single-instance behaviour are all preserved; only the
# window is suppressed. Original command line is preserved verbatim (exe re-quoted if it has
# spaces). Every touched task is backed up to XML first; -Revert restores from that backup.
# Generated 2026-09-17.

$ErrorActionPreference = 'Stop'
$launch = 'C:\Users\Prekzursil\.local\opt\hidden-launchers'
$backup = 'C:\Users\Prekzursil\.agents\maintenance\hide-terminals-2026-09-17\backup'
$runhidden = Join-Path $launch 'runhidden.exe'
New-Item -ItemType Directory -Force -Path $launch,$backup | Out-Null
if(-not $Revert -and -not (Test-Path $runhidden)){ throw "runhidden.exe not found at $runhidden — compile it first." }
$consoleRe = 'powershell|pwsh|cmd\.exe|\\python|pythonw|\\node|node\.exe|ruby|perl|\\bash|wscript|cscript'

function Quote-Exe([string]$s){
  $s = $s.Trim().Trim('"')
  if($s -match '[\\/ ]'){ '"' + $s + '"' } else { $s }
}

foreach($n in $Tasks){
  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if(-not $t){ Write-Output "FAIL $n : task not found"; continue }
  $safe = ($n -replace '[^\w.-]','_')
  $bf   = Join-Path $backup "$safe.xml"

  if($Revert){
    if(-not (Test-Path $bf)){ Write-Output "FAIL $n : no backup to revert from"; continue }
    try{
      Register-ScheduledTask -Xml (Get-Content -Raw -Path $bf) -TaskName $n -TaskPath $t.TaskPath -Force | Out-Null
      Write-Output "REVERTED $n"
    }catch{ Write-Output "FAIL $n : revert failed $($_.Exception.Message)" }
    continue
  }

  # pristine backup (never overwrite the first one)
  if(-not (Test-Path $bf)){
    try{ Export-ScheduledTask -TaskName $n -TaskPath $t.TaskPath | Set-Content -Path $bf -Encoding Unicode }
    catch{ Write-Output "WARN $n : backup failed $($_.Exception.Message)" }
  }

  $acts = @($t.Actions)
  $newActs = @()
  $wrapped = 0
  foreach($a in $acts){
    $exe = "$($a.Execute)"
    $isWrapped = ($exe.Trim('"') -ieq $runhidden)
    if($isWrapped -or ($exe -notmatch $consoleRe)){
      # already wrapped, or a non-console action: keep as-is
      $p=@{Execute=$a.Execute}; if($a.Arguments){$p.Argument=$a.Arguments}; if($a.WorkingDirectory){$p.WorkingDirectory=$a.WorkingDirectory}
      $newActs += (New-ScheduledTaskAction @p); continue
    }
    $argN = "$($a.Arguments)"
    $wd   = "$($a.WorkingDirectory)"
    $cmd  = if($argN){ (Quote-Exe $exe) + ' ' + $argN } else { (Quote-Exe $exe) }
    $p=@{ Execute=$runhidden; Argument=$cmd }
    if($wd){ $p.WorkingDirectory = $wd }
    $newActs += (New-ScheduledTaskAction @p)
    $wrapped++
  }
  if($wrapped -eq 0){ Write-Output "SKIP $n : already wrapped / nothing to wrap"; continue }
  try{
    Set-ScheduledTask -TaskName $n -TaskPath $t.TaskPath -Action $newActs | Out-Null
    Write-Output "OK   $n : wrapped $wrapped action(s)"
  }catch{ Write-Output "FAIL $n : Set-ScheduledTask failed $($_.Exception.Message)" }
}
