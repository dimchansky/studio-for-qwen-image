# Usage guide

[简体中文](usage.zh-CN.md) | [Home](../README.en.md)

## Generate and edit images

Choose image or chat mode in a new conversation. Once a conversation has messages, the composer becomes shorter and mode controls move into the plus menu. That menu also provides reference-image upload, gallery access and generation settings.

Enter a prompt and click Send, or press `Cmd Enter` on Mac / `Ctrl Enter` on Windows. Tasks can be queued; Stop cancels the selected task. Click a result to open the full-image viewer, switch to original size or save it. Continue editing adds the result to the composer as a reference image.

Previews update at selected inference steps and can differ from the final result. They preserve the image aspect ratio. The task tray stays outside the message viewport; scrolling up lets you read earlier messages.

## Controls

| Control | Meaning |
| --- | --- |
| Size | Output dimensions. The 2K presets use upstream aspect-ratio sizes and require substantially more memory |
| Steps | Denoising iterations, from 1 to 60; default 40. Fewer steps can help explore a composition |
| Seed | `-1` chooses a random seed. A nonnegative integer fixes initial noise for prompt comparisons |
| Transparent background | Adds the upstream RGBA prompt request; the resulting alpha channel depends on the model output |
| Thinking intensity | Controls supported Ollama chat models, independently of image inference steps |

A seed does not guarantee identical pixels across devices, dependency versions or image dimensions. Uploads keep their original dimensions and alpha channel; images larger than 25 megapixels are rejected. The enhancer and image pipeline each apply their own area-based reference budget. See [Generation capabilities](generation.en.md) for enhancement, text, ratio, mask and advanced controls.

## Chat

Start local Ollama and download a chat model first. The list comes from Ollama; names indicating embedding, OCR or cloud models are filtered out. For thinking-capable models, gpt-oss gets low, medium and high levels; other supported models may expose an on/off control.

The chat assistant can help write prompts but does not automatically call an image tool. Switch to image mode to generate. Chat responses currently render as plain text.

## Language and environment

Choose 简体中文, English or System default under Settings → Interface. The environment screen has the same selection, which persists across launches. Menus, downloads, tasks, image previews and application errors change together. Chat history, user titles and model responses keep their original text.

A discovered missing dependency returns the app to its environment screen. Passed items show 🎉, and required failures block entry. Select Install or repair dependencies to view installation progress and run checks again afterward. Use the supplied links for hardware or driver issues.

## Troubleshooting

### Model not ready

Check progress and the model location in settings. The first download requires a source choice. Retry interrupted transfers to resume them. Details are in `download.log` in the data directory. Do not mix weights from different releases.

### Out of memory

Close memory-intensive applications and retry at 512 or 768. Reducing dimensions usually lowers peak memory more than reducing steps. 2K is an available output option; completion depends on your device and workload.

### Color bands, seams or dirty-looking images

Use the latest release with its pinned dependencies. Full-frame FP32 decoding and disabled VAE tiling address decoder artifacts. They cannot eliminate mistakes produced by the model itself. Include dimensions, steps, seed and a shareable example when reporting a problem.

### Windows fails to start or cannot find a GPU

Read the failed items on the environment screen. The native fallback offers a WebView2 download link; Install or repair dependencies handles Python packages. Keep the package directory intact and check `desktop.log`. GPU failures may require a compatible NVIDIA driver or PyTorch CUDA build.

### Mac cannot start Python

Select Install or repair dependencies and check that the original Python installation still exists. Virtual environments depend on the Python installation that created them. Removing or replacing it may require rebuilding the runtime. Check `app.log` in the data directory.

### Share diagnostics

Include OS, GPU or unified memory, app version, reproduction steps and the error text. Logs and PNG metadata on both platforms may contain prompts. Older logs or image metadata may also include local paths. Review them before posting publicly.
