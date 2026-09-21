$ErrorActionPreference = 'Stop'
$studioApp = Join-Path $PSScriptRoot 'app\Qwen Studio.exe'
if (-not (Test-Path -LiteralPath $studioApp)) { throw 'Qwen Studio.exe is missing. Run build.ps1 first.' }
Start-Process -FilePath $studioApp -WorkingDirectory $PSScriptRoot
