# Third-party notices

The MIT license in this repository covers the application code. Dependencies, model weights and adapted
components keep their own terms. Python packages are installed from PyPI by `setup.sh`, and model files are
downloaded separately by the user; neither is redistributed in this repository.

| Component | Use | License or terms |
| --- | --- | --- |
| [Qwen Studio](https://github.com/rigorhormist/QwenStudio) | The application this project is forked from | MIT |
| [Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1) | Image model (configs, VAE; transformer via GGUF conversions) | [Qwen Research License](LICENSE.model.txt), non-commercial |
| [PE-T2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I) / [PE-I2I](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I) | Official prompt enhancers (system prompts, licence files) | Qwen Research License |
| [unsloth/Qwen-Image-2.1-GGUF](https://huggingface.co/unsloth/Qwen-Image-2.1-GGUF) | 8-bit GGUF transformer (official weights) | Model card terms; derived from Qwen-Image-2.1 |
| [abenzerps/Qwen-Image-2.1-Uncensored-GGUF](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-GGUF) | Optional community-modified transformer | Model card terms (Qwen Research License); modification not documented |
| [OzzyGT/Qwen_Image_2_1_sdnq_dynamic_8bit](https://huggingface.co/OzzyGT/Qwen_Image_2_1_sdnq_dynamic_8bit) | 8-bit text encoder | Model card terms; derived from Qwen-Image-2.1 |
| [prithivMLmods Qwen-Image-2.1-PE MLX](https://huggingface.co/prithivMLmods/Qwen-Image-2.1-PE-T2I-MLX) | 4-bit MLX prompt enhancers | Model card terms; derived from the official enhancers |
| [Viggle/Qwen-Image-2.1-viggle-turbo](https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo) | 4-step turbo LoRA | License and NOTICE files downloaded with the LoRA |
| [Diffusers](https://github.com/huggingface/diffusers), [Transformers](https://github.com/huggingface/transformers), [Accelerate](https://github.com/huggingface/accelerate), [PEFT](https://github.com/huggingface/peft), [huggingface_hub](https://github.com/huggingface/huggingface_hub) | Inference pipeline, text encoder, LoRA, downloads | Apache-2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) | Tensor runtime (Apple GPU via MPS) | BSD-style |
| [MLX](https://github.com/ml-explore/mlx), [mlx-vlm](https://github.com/Blaizzy/mlx-vlm) | Prompt enhancers on the Apple GPU | MIT |
| [SDNQ](https://github.com/Disty0/sdnq) | 8-bit text encoder runtime, installed from PyPI by `setup.sh` and imported at run time (not included here) | GPL-3.0-only |
| [gguf](https://github.com/ggml-org/llama.cpp/tree/master/gguf-py) | GGUF file reader (part of llama.cpp) | MIT |
| [Pillow](https://github.com/python-pillow/Pillow), [psutil](https://github.com/giampaolo/psutil), [filelock](https://github.com/tox-dev/filelock), [NumPy](https://github.com/numpy/numpy) | Image I/O and utilities | Their own permissive licenses |
| [Ramotion/CircleMenu](https://github.com/Ramotion/circle-menu) | Circular menu geometry and animation, ported to JavaScript | [MIT notice](macos/web/CIRCLE_MENU_LICENSE.txt) |

The Q icon comes from Qwen Studio; it is not a Qwen logo. The name describes compatibility and does not
imply endorsement: the Qwen Research License does not allow “Qwen” as the primary name of derivative
products, so this project is called *Studio for Qwen Image*.
