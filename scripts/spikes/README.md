# Hardware checks

Small scripts that measure speed, memory and correctness on your Mac with the real models. Each one writes
a JSON summary to `data/spikes/`. Run them from this folder with the studio's environment; stop the studio
first, because two jobs at once do not fit into 32 GB:

```bash
cd scripts/spikes
../../.venv/bin/python fetch_test_images.py        # official demo inputs, ~5 MB
../../.venv/bin/python s0_env.py                    # versions, GPU memory limit, the MPS padding bug
```

| Script | What it checks | M1 Max 32 GB result |
|---|---|---|
| `s0_env.py` | Versions, `torch.mps.recommended_max_memory()`, reproduces the PyTorch MPS rank-5 `F.pad` bug and verifies the patch | Bug present (max error 5.3); patch exact |
| `s3_vae_psnr.py` | VAE encode → decode quality on CPU, MPS and MPS with the patch | 42.15 / 10.09 / 42.15 dB |
| `s3b_vae_decode_mem.py` | Decode memory: fp32, fp16, tiled | +18 GB / +8.6 GB (78.6 dB) / +3 GB |
| `s2_text_encoder.py` | 8-bit text encoder on MPS in bf16 and fp16, cross-checked on the CPU | Finite, cosine 0.998, fp16 faster |
| `s1_gguf_load.py [official\|uc]` | GGUF transformer load, sanity image, seconds per step in fp16 and bf16 | 9.6 s vs 16.3 s per step at 1024² |
| `run_job.py NAME --prompt … [--image …]` | One real job through the studio's workers, with memory and swap | See `batch1.sh` |
| `batch1.sh` | Edits (one reference, mask, marks, five references), Turbo, transparent PNG, both prompt enhancers, the uncensored model | All pass, 1.5–5.5 min per job |

`run_job.py` accepts the same options as the interface: `--size 1024x1024`, `--preset turbo|standard|quality|custom`,
`--steps`, `--variant official|uc`, `--transparent`, `--enhance`, `--ratio-mode fixed|auto|reference`,
`--negative … --cfg 2`, `--count`, `--no-kv-cache`.
