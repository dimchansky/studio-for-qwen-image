# Changelog

## Unreleased

- An **Enhance** button next to Send runs only the prompt enhancer (about a minute) and puts the rewrite
  into the prompt field, applying the aspect ratio it chose when the ratio is left to the enhancer.
  Auto-enhance is switched off afterwards so the prompt is not rewritten twice; “Restore original” undoes
  it. Enhancements run ahead of queued images and are not stored in the chat.
- With Auto-enhance on, the rewritten prompt appears in the progress card as soon as the enhancer is done;
  a stopped or failed job keeps it in the chat. Generation details list the enhancer's own wording and
  show the effective prompt only when it differs.
- Chats can be deleted from the sidebar (trash icon) or the chat menu. A confirmation dialog offers
  to delete the chat's images too; images that another chat uses as references are kept. The chat's job
  logs and inputs, which contain its prompts, are always removed.

## 3.0.0 — Studio for Qwen Image (2026-09-23)

Fork of Qwen Studio 2.2.1 for Apple Silicon Macs with 32 GB of memory. See “What changed compared to
QwenStudio, and why” in the README for the reasoning behind each change.

- Every job runs as up to three disposable processes (prompt enhancer, text encoder, image model) so the
  weights never share memory; 8-bit GGUF transformer, 8-bit SDNQ text encoder, 4-bit MLX prompt enhancers.
- Fixed corrupted edits on Apple GPUs (PyTorch MPS padding bug in the VAE encoder); float16 compute with
  an automatic bfloat16 retry; decoding in float16 after the image model is unloaded.
- Automatic reference-image resolution to keep the cache within budget; cached prompt embeddings.
- Turbo mode (4-step LoRA), a switch between the official and an optional uncensored model, time estimates,
  task templates, box and colour annotations, low-memory warning, diagnostics page, Russian interface.
- Pinned, SHA-256-verified downloads one file at a time with disk-space checks; `setup.sh`, `download.sh`
  and `run.sh` for a browser-based setup.
- Removed the native macOS shell, the Ollama chat, the download-source choice and the Windows version
  (which stays in the upstream project).

The entries below are from the upstream Qwen Studio project.

## 2.2.1 (2026-09-21)

- Fixed Windows Python discovery in freshly extracted downloads. The app checks an existing app environment, Python Launcher, registered installations and current/user/system PATH, then probes the actual interpreter.
- Dependency setup uses the same discovery logic. A working global Python environment can be used directly; repairs install into the app environment. Unsupported versions, 32-bit interpreters and missing dependencies have distinct results.
- Added Windows tests for fresh installs, existing environments, registration without PATH and incompatible interpreters.

修复 Windows 下载版将“尚未建立应用环境”误报为未安装 Python 的问题；检测与安装共用查找逻辑，并显示实际 Python 路径。Mac 功能无变化。

## 2.2.0 (2026-09-21)

- Added a Python-independent environment screen, required-check gate, in-app dependency repair and recovery after runtime failures on both platforms.
- Added a native Windows fallback for missing WebView2.
- Completed Chinese/English UI localization, including dynamic states and native menus, without rewriting user content.
- Added the official PE-T2I / PE-I2I profiles, separately verified downloads and sequential enhancer/diffusion execution.
- Switched the default to official 2K / 40 steps; added ratio inheritance, exact lettering, annotations/masks, negative prompts and serial batches.
- Preserved prompt provenance and per-image seeds; corrected reference-image area budgeting and removed upload downscaling.
- Added dependency-failure, localization, generation-contract and process-boundary checks.

两端加入应用内环境检测、🎉 通过状态和依赖修复，并补齐完整中英文界面。必需项通过后开放主界面；运行环境缺失时重新检测。

## 2.1.0 (2026-09-21)

First public source release containing both desktop platforms.

- Added ModelScope and Hugging Face selection before the first download, with persisted preferences and resumable transfers.
- Synchronized the Windows interface with Mac: animated task tray, red stop actions, a slightly taller in-conversation composer and previews that keep their aspect ratio.
- Included the flat black Q icon on both platforms.
- Added portable storage defaults, first-time dependency setup, bilingual documentation and release packaging.
- Preserved FP32 full-frame decoding and added 2K output presets. Windows PNG metadata now contains generation settings without application file paths.

首次公开源码版本同时提供 Mac 和 Windows。两端同步下载源选择和界面修复，补齐首次安装、图标、中英文说明与下载包。详见发布页的验证范围与已知限制。
