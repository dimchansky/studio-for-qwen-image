param(
    [string]$Python = '',
    [ValidateSet('cu130','cu128')][string]$Cuda = 'cu130'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Run-Python([string[]]$Arguments) {
    & $script:PythonCommand @script:PythonPrefix @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Python setup failed. Review the error above and rerun setup.cmd.' }
}
$script:PythonCommand = $Python
$script:PythonPrefix = @()
if (-not $Python) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @('-3.11','-3.10','-3.12','-3.13')) {
            & py $version -c 'import sys; assert sys.maxsize > 2**32' 2>$null
            if ($LASTEXITCODE -eq 0) { $script:PythonCommand='py'; $script:PythonPrefix=@($version); break }
        }
    }
    if (-not $script:PythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) { $script:PythonCommand='python' }
}
if (-not $script:PythonCommand) { throw 'Install 64-bit Python 3.11 from https://www.python.org/downloads/windows/ and rerun setup.cmd.' }
Run-Python -Arguments @('-c','import sys; assert (3,10) <= sys.version_info[:2] < (3,14) and sys.maxsize > 2**32, "Use 64-bit Python 3.10-3.13"')
if (-not (Test-Path '.venv\Scripts\python.exe')) { Run-Python -Arguments @('-m','venv','.venv') }
$script:PythonCommand=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$script:PythonPrefix=@()
Run-Python -Arguments @('-m','pip','install','--upgrade','pip')
Run-Python -Arguments @('-m','pip','install','torch==2.9.0','torchvision==0.24.0','--index-url',"https://download.pytorch.org/whl/$Cuda")
Run-Python -Arguments @('-m','pip','install','-r','requirements.txt')
Run-Python -Arguments @('-c','import torch; from diffusers import QwenImage21Pipeline; print("PyTorch:", torch.__version__); print("CUDA available:", torch.cuda.is_available())')
Write-Host 'Setup complete. Run start.cmd to open Qwen Studio. Choose the model source in the app before downloading.'
