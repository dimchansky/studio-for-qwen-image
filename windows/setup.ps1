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
$runtimePython = if ($env:QWEN_STUDIO_PYTHON) { $env:QWEN_STUDIO_PYTHON } else { Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if ($env:QWEN_STUDIO_PYTHON) {
    & $runtimePython -c 'import sys; assert sys.prefix != sys.base_prefix, "Custom runtime must be a virtual environment; global Python is not modified."'
    if ($LASTEXITCODE -ne 0) { throw 'Select a working virtual environment or remove QWEN_STUDIO_PYTHON to use the app runtime.' }
}
if (-not $Python -and (Test-Path $runtimePython)) {
    try { & $runtimePython -c 'import sys; assert (3,10)<=sys.version_info[:2]<(3,14)' 2>$null; if ($LASTEXITCODE -eq 0) { $Python=$runtimePython } } catch {}
}
if (-not $PSBoundParameters.ContainsKey('Cuda') -and (Test-Path $runtimePython)) {
    try { $existingCuda=& $runtimePython -c 'import torch; print(torch.version.cuda or "")' 2>$null; if ($LASTEXITCODE -eq 0 -and $existingCuda -eq '12.8') { $Cuda='cu128' } } catch {}
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
$runtimeReady=$false
if (Test-Path $runtimePython) {
    try { & $runtimePython -c 'import sys; assert (3,10)<=sys.version_info[:2]<(3,14)' 2>$null; $runtimeReady=($LASTEXITCODE -eq 0) } catch { $runtimeReady=$false }
}
if (-not $runtimeReady) { Run-Python -Arguments @('-m','venv','--clear','.venv') }
$script:PythonCommand=$runtimePython
$script:PythonPrefix=@()
Run-Python -Arguments @('-m','pip','install','--upgrade','pip')
Run-Python -Arguments @('-m','pip','install','--force-reinstall','torch==2.9.0','torchvision==0.24.0','--index-url',"https://download.pytorch.org/whl/$Cuda")
Run-Python -Arguments @('-m','pip','install','-r','requirements.txt')
Run-Python -Arguments @('-m','pip','install','--force-reinstall','--no-deps','-r','requirements.txt')
# Reinstall the imported transitive packages too, without replacing the CUDA build.
$transitive = & $runtimePython -c 'import importlib.metadata as m; print("\n".join(n+"=="+m.version(n) for n in ["numpy","tokenizers","safetensors","huggingface_hub"]))'
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect dependency versions.' }
Run-Python -Arguments (@('-m','pip','install','--force-reinstall','--no-deps') + $transitive)
Run-Python -Arguments @('-c','import torch; from diffusers import QwenImage21Pipeline; print("PyTorch:", torch.__version__); print("CUDA available:", torch.cuda.is_available())')
Write-Host 'Setup complete. Run start.cmd to open Qwen Studio. Choose the model source in the app before downloading.'
