[CmdletBinding()]
param(
  [string]$GhidraHome = $env:GHIDRA_INSTALL_DIR,
  [string]$JavaExe,
  [string]$JarPath,
  [int]$Port = 8089,
  [string]$Bind = '127.0.0.1',
  [switch]$Restart,
  [switch]$Foreground
)

$ErrorActionPreference = 'Stop'

if (-not $GhidraHome) { $GhidraHome = 'D:\Program Files\Ghidra\ghidra_12.0.3_PUBLIC' }
if (-not $JavaExe) {
  $javaHome = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { 'D:\Program Files\Java\jdk-21.0.10+7' }
  $JavaExe = Join-Path $javaHome 'bin\java.exe'
}
if (-not $JarPath) { $JarPath = 'D:\MCP\ghidra-mcp\target\GhidraMCP-4.3.0.jar' }
$LogDir = 'D:\ProgramData\GhidraMCP\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Test-GhidraHealth {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

$healthUrl = "http://$Bind`:$Port/check_connection"
if (Test-GhidraHealth $healthUrl) {
  if (-not $Restart) {
    Write-Host "Ghidra headless already healthy at $healthUrl"
    exit 0
  }
}

$listener = Get-NetTCPConnection -LocalAddress $Bind -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener -and -not (Test-GhidraHealth $healthUrl)) {
  throw "Port $Port is already in use on $Bind, but the Ghidra health check failed. Stop the conflicting process manually before retrying."
}

$jarPaths = @($JarPath)
$roots = @(
  (Join-Path $GhidraHome 'Ghidra\Framework'),
  (Join-Path $GhidraHome 'Ghidra\Features'),
  (Join-Path $GhidraHome 'Ghidra\Processors')
)
foreach ($rootDir in $roots) {
  if (Test-Path $rootDir) {
    $jarPaths += Get-ChildItem -Path $rootDir -Filter *.jar -Recurse -File | ForEach-Object FullName
  }
}
$classPath = ($jarPaths | Select-Object -Unique) -join ';'
$args = @(
  '-Xmx4g',
  '-XX:+UseG1GC',
  ('-Dghidra.home="{0}"' -f $GhidraHome),
  '-Dapplication.name=GhidraMCP',
  '-classpath', ('"{0}"' -f $classPath),
  'com.xebyte.headless.GhidraMCPHeadlessServer',
  '--port', "$Port",
  '--bind', $Bind
)

if ($Foreground) {
  & $JavaExe @args
  exit $LASTEXITCODE
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outLog = Join-Path $LogDir "ghidra-headless-$stamp.out.log"
$errLog = Join-Path $LogDir "ghidra-headless-$stamp.err.log"
$proc = Start-Process -FilePath $JavaExe -ArgumentList $args -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Start-Sleep -Seconds 5
if (-not (Test-GhidraHealth $healthUrl)) {
  throw "Ghidra headless failed to become healthy at $healthUrl. Check logs: $outLog and $errLog"
}
Write-Host "Ghidra headless healthy at $healthUrl (pid=$($proc.Id))"
