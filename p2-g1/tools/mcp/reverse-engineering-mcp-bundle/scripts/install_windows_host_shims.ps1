param(
    [string]$LocalBin = "$HOME\.local\bin",
    [string]$IdaExe = "C:\Program Files\IDA Professional 9.3\ida.exe",
    [string]$GhidraRun = "D:\Program Files\Ghidra\ghidra_12.0.3_PUBLIC\ghidraRun.bat",
    [string]$BinaryNinjaExe = "C:\Program Files\Vector35\BinaryNinja\binaryninja.exe"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $LocalBin -Force | Out-Null

$shimMap = @{
    "ida64.cmd"                = "@echo off`r`n`"$IdaExe`" %*`r`n"
    "ghidraRun.cmd"            = "@echo off`r`ncall `"$GhidraRun`" %*`r`n"
    "binaryninja.cmd"          = "@echo off`r`n`"$BinaryNinjaExe`" %*`r`n"
    "binaryninja-personal.cmd" = "@echo off`r`n`"$BinaryNinjaExe`" %*`r`n"
}

foreach ($pair in $shimMap.GetEnumerator()) {
    Set-Content -Path (Join-Path $LocalBin $pair.Key) -Value $pair.Value -Encoding ASCII
    Write-Host "Wrote shim $($pair.Key)"
}

Write-Host "Host launch shims are ready under $LocalBin"
