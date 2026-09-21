# 安装与下载

[English](installation.en.md) | [返回首页](../README.md)

## 选择下载包

从 [GitHub Releases](https://github.com/rigorhormist/QwenStudio/releases/latest) 下载 Windows x64 或 Mac arm64 的 ZIP，并完整解压到可写目录。不要只复制 Windows 的 EXE。源码压缩包用于自行构建；想直接打开桌面程序，请选名称包含平台的发布包。

安装分为三部分：下载桌面程序，安装 Python 依赖，在应用内下载模型。模型约 33.1 GB，下载分段合并期间还会占用额外空间；建议预留至少 80 GB 空间作为安装起点，长期保存图片需另行增加。

## Windows

1. 安装 [64 位 Python](https://www.python.org/downloads/windows/)，支持 3.10–3.13，建议选择 3.11 并启用 Python Launcher。
2. 安装或更新 NVIDIA 显卡驱动，并确认已有 [WebView2 Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)。
3. 完整解压 Windows ZIP，双击 `setup.cmd`。脚本在当前目录创建 `.venv`，从 PyTorch 官方 CUDA 13.0 源安装 PyTorch，再安装其余依赖。
4. 安装成功后双击 `start.cmd`。首次生成图片前，打开“模型设置”，点击“下载模型”，选择下载源。

安装脚本只在该次 PowerShell 进程使用 `ExecutionPolicy Bypass`，不改系统执行策略。Windows 发布包自带 .NET 10 运行时，普通使用无需安装 SDK。

如果驱动环境需要 CUDA 12.8，使用：

```powershell
.\setup.ps1 -Cuda cu128
```

指定已安装的 Python：

```powershell
.\setup.ps1 -Python 'C:\Python311\python.exe'
```

PyTorch 的 CUDA 构建和驱动要求见 [官方安装说明](https://pytorch.org/get-started/previous-versions/)。应用仅为图像推理启用 CUDA，没有 Windows CPU、AMD 或 Intel GPU 图像后端。

## Mac

1. 使用 Apple Silicon Mac，系统为 macOS 14 或更新。
2. 安装 [Python 3.11](https://www.python.org/downloads/macos/) 的 universal2 版本。也支持 3.10、3.12、3.13 的原生 arm64 Python。
3. 解压 Mac ZIP，运行 `setup.command`。依赖安装到 `~/Library/Application Support/Qwen Studio/runtime`。
4. 完成后打开 `Qwen Studio.app`，或将它移入“应用程序”再打开。
5. 在“模型设置”中选择 ModelScope 或 Hugging Face，下载图像模型。

发布包使用本地临时签名，没有 Apple 公证。如果系统提示无法验证开发者，请先核对下载来源与 SHA-256，再按 macOS“隐私与安全性”页面提供的打开方式处理，不需要关闭系统安全检查。

安装脚本优先寻找 python.org 的 Python，随后寻找 `/opt/homebrew/bin/python3`。也可指定解释器：

```sh
QWEN_STUDIO_PYTHON_BOOTSTRAP=/path/to/python3 ./setup.command
```

下载包已带编译好的 App，首次安装无需 Xcode。只有从源码构建时才需要 Xcode Command Line Tools。

## 模型下载与断点续传

首次点击“下载模型”时不会自动替你决定来源。ModelScope 通常更适合中国大陆网络，Hugging Face 适用于能够稳定访问它的网络。选择保存在本地，之后可以在设置中更改。

下载时会显示已完成体积、速度和预计剩余时间。估算基于最近的传输速度，校验与磁盘写入期间数值可能波动。中断后重新点击下载会保留已有分段；切换来源也会保留分段。正在下载时不能切换来源。

`backend/model-files.json` 固定文件大小和 SHA-256；Hugging Face 固定到指定提交，ModelScope 使用文件版本。发布包不含模型权重。

## 接入 Ollama

安装并启动 [Ollama](https://ollama.com/download)，然后先在 Ollama 下载一个适合自己设备的聊天模型。应用连接固定的本机端口 `127.0.0.1:11434`。在首页选择“对话”，从模型列表选择已安装模型即可。

Ollama 不参与本应用的图像推理。思考强度控件根据 Ollama 返回的模型能力显示；模型不支持时不会强行发送该参数。

## 数据目录和已有模型

| 平台 | 默认数据目录 | 默认模型目录 |
| --- | --- | --- |
| Mac | `~/Library/Application Support/Qwen Studio` | 数据目录下 `models/Qwen-Image-2.1` |
| Windows | `%LOCALAPPDATA%\QwenStudio` | 数据目录下 `models\Qwen-Image-2.1` |

Windows 可复制 `settings.example.json` 为 `settings.local.json`，填写自己的目录。JSON 中的反斜杠必须写成 `\\`。原有用户的本地配置不会被下载包覆盖。

两端均支持 `QWEN_STUDIO_DATA` 环境变量。Windows 另支持 `QWEN_STUDIO_MODEL`；Mac 自定义解释器使用 `QWEN_STUDIO_PYTHON`。Mac 的模型目录跟随数据目录。通过 Finder 启动 App 时不会继承终端里临时设置的环境变量。

已有模型必须是与应用文件清单匹配的完整 Diffusers 目录，包含 transformer、text_encoder、vae、tokenizer 等组件。GGUF、LoRA 或其他 Qwen Image 版本不能直接放进去替用。

## 更新与卸载

更新前关闭应用，保留数据目录。Windows 可覆盖程序和源码文件，同时保留 `.venv` 与 `settings.local.json`；依赖发生变化时重新运行 `setup.cmd`。Mac 替换 App，再按发布说明决定是否重新运行 `setup.command`。不要在任务执行中覆盖程序。

卸载程序不会自动删除会话和模型。需要清理时，先备份所需图片，再自行删除数据目录；Mac 的 Python 运行环境也位于这个目录。删除会话只删除对应聊天记录，生成的图片文件仍保留。

## 校验下载包

发布页面提供 `SHA256SUMS.txt`。在下载目录执行：

```sh
# Mac
shasum -a 256 QwenStudio-2.1.0-macos-arm64.zip
```

```powershell
# Windows
Get-FileHash .\QwenStudio-2.1.0-windows-x64.zip -Algorithm SHA256
```

将结果与发布页的校验文件逐字比较。常见错误处理见 [使用说明](usage.zh-CN.md)。
