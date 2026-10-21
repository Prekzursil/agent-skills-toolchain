param(
    [Parameter(Mandatory=$true)][string]$Exe,
    [Parameter(Mandatory=$false)][string]$ExeArgs = "",
    [Parameter(Mandatory=$false)][string]$OutFile = "$env:TEMP\elevout.txt",
    [Parameter(Mandatory=$false)][int]$TimeoutSec = 900
)
$inner = "cmd /c `"`"$Exe`" $ExeArgs > `"$OutFile`" 2> `"$OutFile.err`"`""
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $inner -Verb RunAs -WindowStyle Hidden -PassThru
if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
    Write-Output "TIMEOUT"
    exit 124
}
Write-Output "EXITCODE=$($proc.ExitCode)"
