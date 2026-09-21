# Changelog

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
