param(
    [Parameter(Mandatory = $true)]
    [string]$OutFile
)

Add-Type -AssemblyName System.Windows.Forms | Out-Null
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class FgSnap {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
}
"@ | Out-Null

$hwnd = [FgSnap]::GetForegroundWindow()
$pidOut = [uint32]0
[FgSnap]::GetWindowThreadProcessId($hwnd, [ref]$pidOut) | Out-Null
$sb = New-Object System.Text.StringBuilder 512
[FgSnap]::GetWindowText($hwnd, $sb, $sb.Capacity) | Out-Null
$title = $sb.ToString()
$procName = $null
try { $procName = (Get-Process -Id $pidOut -ErrorAction SilentlyContinue).ProcessName } catch {}
$payload = @{
    hwnd     = $hwnd.ToInt64()
    pid      = $pidOut
    process  = $procName
    title    = $title
    captured = (Get-Date).ToString('o')
} | ConvertTo-Json -Compress
$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
Set-Content -LiteralPath $OutFile -Value $payload -Encoding utf8
Write-Output "SUCCESS:foreground pid=$pidOut process=$procName title=$title"
