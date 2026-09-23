# Contributing

Bug reports should include the Mac model, chip, memory, macOS version, the commit you run, steps to
reproduce and the relevant part of `data/jobs/<id>.log`. Remove personal prompts, images and paths.

For changes, open a focused pull request that explains what users will notice and which checks you ran.
Keep unrelated reformatting out of it.

## Layout

- `macos/backend/server.py` — HTTP API, queue, sessions and downloads (no model code).
- `macos/backend/image_jobs.py` — runs a job as disposable processes: `enhancer_worker.py` (MLX),
  `encode_worker.py` (text encoder) and `worker.py` (image model and VAE).
- `macos/backend/model_loader.py`, `staged_pipeline.py`, `mps_patches.py` — loading, prompt-embedding
  capture/replay and Apple GPU workarounds.
- `macos/backend/models.json` — pinned model files; rebuild with `python3 scripts/build_manifest.py`.
- `macos/web` — the interface (vanilla JavaScript, no build step).

Diffusers is pinned to a commit and `staged_pipeline.py` relies on the pipeline's internals: when you
update it, run the unit tests and the hardware checks in `scripts/spikes`.

## Localization

Chinese is the source language of the interface. Put new strings into `macos/web/locales/en.json` and
`ru.json` (dynamic text into `patterns-*.json`), then run `python3 scripts/build_locales.py`. Keep user
messages, prompts, titles and paths under `translate="no"`.

## Checks

```bash
.venv/bin/python -m unittest discover -s macos/tests -p 'test_*.py'
.venv/bin/python -m unittest discover -s tests && node tests/i18n.test.cjs
for f in macos/web/*.js; do node --check "$f"; done
```
