$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    dotnet publish .\desktop\QwenStudio.csproj -c Release -r win-x64 --self-contained true -o .\app -v minimal
    if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
} finally { Pop-Location }
