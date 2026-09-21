# Contributing / 参与开发

Bug reports should include the app version, OS, GPU/memory, reproduction steps and a short error excerpt. Use a public test image and remove personal content from logs. / 提交问题时请提供版本、系统、硬件、重现步骤和精简错误信息，并检查图片与日志是否含个人内容。

For changes, open a focused pull request explaining the user-visible behavior and checks performed. Keep unrelated reformatting out of the change. / PR 请说明用户会看到什么变化，以及完成了哪些检查。

## Layout

`macos/native` contains the AppKit shell; `windows/desktop` contains the WinForms shell. Each platform has its own `backend`. The files in `macos/web` and `windows/web` are identical. Apply shared UI changes to both and run `python scripts/check_shared_ui.py`.

The image pipeline is pinned to a Diffusers commit. Update both requirements files and the model manifest deliberately. Do not silently replace the decoder with lower precision or tiled output to avoid memory errors.

## Localization / 界面翻译

Application-owned copy belongs in `web/locales.json` on both platforms. Dynamic formats belong in `locale-patterns.json`; rebuild `locale-data.js` with `python scripts/build_locales.py`. Keep user messages, model output, chat titles and file paths under `translate="no"`. Raw upstream logs are diagnostic content, not application copy. Native shells share the same catalog.

应用文案统一加入两端 `web/locales.json`，动态模板放在 `locale-patterns.json`。生成词条脚本后运行翻译检查。用户消息、模型回复、会话名称、文件路径不参与翻译；原生外壳与网页共用词条。

## Local checks

Use a separate environment without model weights:

```sh
python -m pip install psutil filelock
python -m unittest discover -s macos/tests -p 'test_*.py' -v
python -m unittest discover -s windows/tests -p 'test_*.py' -v
python scripts/check_shared_ui.py
node --check macos/web/app.js
node tests/i18n.test.cjs
python -m unittest discover -s tests -v
```

Run Mac tests on macOS/Linux and Windows tests on Windows/macOS/Linux. Tests use isolated temporary data and controlled workers. They do not download weights or verify generated-image quality. Do not run both platform suites in the same Python process because their backend module names overlap.

Compile native shells separately:

```sh
# Mac, with Xcode Command Line Tools
cd macos
./build.sh
```

```powershell
# Windows, with .NET 10 SDK
cd windows
.\build.ps1
```

On a Mac development machine, a prepared existing virtual environment can be used by launching the built executable with `QWEN_STUDIO_PYTHON=/absolute/path/to/python3`. A custom `QWEN_STUDIO_DATA` keeps test conversations separate from everyday use.

## Release

Update versions in the native shells, build scripts, release documents and download links. Build the platform shell, then run:

```sh
python scripts/package.py --platform windows --version 2.2.0
python scripts/package.py --platform macos --version 2.2.0
```

The packager uses an allowlist and excludes models, local configuration, virtual environments and logs. Review archives and their SHA-256 hashes before uploading. The release workflow builds both packages from a version tag and attaches them to a draft GitHub Release. Maintainers review the draft before publishing.

Document native or GPU checks that were not performed. A passing shell build is not a GPU inference test.
