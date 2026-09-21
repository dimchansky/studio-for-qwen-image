# Installation and downloads

[简体中文](installation.zh-CN.md) | [Home](../README.en.md)

## Choose a package

Download the Windows x64 or Mac arm64 ZIP from [GitHub Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) and extract the entire archive into a writable directory. Keep the Windows EXE with its accompanying folders. Source archives require a local build; platform ZIPs include the compiled desktop application.

Setup has three stages: download the desktop app, install Python dependencies, then download weights inside the app. The model files occupy about 33.1 GB. Chunk assembly temporarily uses extra space. Reserving at least 80 GB is a practical starting point for installation; saved images require additional space.

## Windows

1. Install [64-bit Python](https://www.python.org/downloads/windows/), version 3.10–3.13. Python 3.11 with Python Launcher is recommended.
2. Install an appropriate NVIDIA driver and the [WebView2 Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).
3. Extract the Windows ZIP and run `setup.cmd`. It creates `.venv` in the application directory, installs PyTorch from the official CUDA 13.0 index, then installs other dependencies.
4. Run `start.cmd`. Before generating an image, open model settings, click the download button and choose a source.

The setup wrapper uses `ExecutionPolicy Bypass` for that PowerShell process only. It does not change the system execution policy. The release package includes the .NET 10 runtime; an SDK is unnecessary for normal use.

For a CUDA 12.8 driver environment:

```powershell
.\setup.ps1 -Cuda cu128
```

To select an installed interpreter:

```powershell
.\setup.ps1 -Python 'C:\Python311\python.exe'
```

Refer to [PyTorch installation instructions](https://pytorch.org/get-started/previous-versions/) for CUDA builds and driver compatibility. Image inference on Windows requires NVIDIA CUDA; this release has no CPU, AMD or Intel GPU image backend.

## Mac

1. Use an Apple Silicon Mac with macOS 14 or later.
2. Install the universal2 build of [Python 3.11](https://www.python.org/downloads/macos/). Native arm64 Python 3.10, 3.12 and 3.13 are also supported by the setup script.
3. Extract the Mac ZIP and run `setup.command`. Dependencies go into `~/Library/Application Support/Qwen Studio/runtime`.
4. Open `Qwen Studio.app`, or move it into Applications first.
5. Choose ModelScope or Hugging Face in model settings and start the download.

The App has an ad-hoc signature and is not Apple-notarized. If macOS cannot verify the developer, check the source and SHA-256 checksum first, then use the opening option offered in Privacy & Security. There is no need to disable system security checks.

Setup looks for python.org installations first, then `/opt/homebrew/bin/python3`. To select another interpreter:

```sh
QWEN_STUDIO_PYTHON_BOOTSTRAP=/path/to/python3 ./setup.command
```

The download includes a compiled App. Xcode Command Line Tools are only needed when building from source.

## Model downloads and resuming

The first download requires an explicit source choice. ModelScope may be easier to reach from mainland China; choose Hugging Face when it is reliable on your network. The selection is stored locally and can be changed later.

Progress includes downloaded size, recent transfer speed and estimated time remaining. Verification and disk writes can make these estimates fluctuate. Restarting a download keeps completed chunks, including when switching sources. Source changes are disabled during an active download.

`backend/model-files.json` pins file sizes and SHA-256 hashes. Hugging Face URLs use a fixed commit; ModelScope URLs use file revisions. Model weights are excluded from release packages.

## Connect Ollama

Install and start [Ollama](https://ollama.com/download), then download a chat model suitable for your hardware through Ollama. Qwen Studio connects to `127.0.0.1:11434`. Choose the chat tab, then select an installed model.

Image inference is handled separately by Diffusers. Thinking controls follow capabilities reported by Ollama and are omitted for models that do not support them.

## Storage and existing models

| Platform | Default data directory | Default model directory |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Qwen Studio` | `models/Qwen-Image-2.1` under the data directory |
| Windows | `%LOCALAPPDATA%\QwenStudio` | `models\Qwen-Image-2.1` under the data directory |

On Windows, copy `settings.example.json` to `settings.local.json` and set your directories. Backslashes in JSON must be escaped as `\\`. Download packages never contain or replace your local configuration.

Both platforms accept `QWEN_STUDIO_DATA`. Windows also accepts `QWEN_STUDIO_MODEL`; Mac accepts `QWEN_STUDIO_PYTHON` for a custom interpreter. Mac model storage follows the data directory. Apps started through Finder do not inherit temporary shell environment variables.

Existing weights must be a complete Diffusers directory matching the file manifest, including transformer, text_encoder, vae and tokenizer components. GGUF files, LoRA files and other Qwen Image versions cannot be substituted directly.

## Updates and removal

Close the app before updating and keep the data directory. On Windows, replace application files while preserving `.venv` and `settings.local.json`; rerun `setup.cmd` when dependencies change. On Mac, replace the App and follow release notes about rerunning `setup.command`.

Removing the application does not erase saved conversations or models. Back up images before deleting the data directory yourself. Mac Python dependencies also live there. Deleting a conversation removes its messages but leaves generated image files on disk.

## Verify an archive

Each release includes `SHA256SUMS.txt`. From the download directory:

```sh
# Mac
shasum -a 256 QwenStudio-2.1.0-macos-arm64.zip
```

```powershell
# Windows
Get-FileHash .\QwenStudio-2.1.0-windows-x64.zip -Algorithm SHA256
```

Compare the complete hash with the release checksum file. See the [Usage guide](usage.en.md) for troubleshooting.
