"""Build macos/backend/models.json: pinned Hugging Face files with sizes and SHA-256.

Run once when a pinned revision changes:  python3 scripts/build_manifest.py
LFS files take their SHA-256 from the Hub; small files are downloaded and hashed.
"""
import fnmatch
import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import quote

OUTPUT = Path(__file__).resolve().parent.parent / 'macos/backend/models.json'

# (component, label, required, [(repo, revision, patterns, strip_prefix, dest_dir)])
COMPONENTS = [
    ('base', 'Qwen-Image-2.1 configs, processor and VAE', True, [
        ('Qwen/Qwen-Image-2.1', 'b3179ad355be050328e483a9dfdd9e60cd62adfa',
         ['LICENSE', 'model_index.json', 'processor/*', 'scheduler/*', 'transformer/config.json', 'vae/*'], '', 'Qwen-Image-2.1')]),
    ('text_encoder', 'Text encoder Qwen3-VL-8B (SDNQ int8)', True, [
        ('OzzyGT/Qwen_Image_2_1_sdnq_dynamic_8bit', 'def359371741deed082c363f8ab76bc57ff742a5',
         ['text_encoder/*'], 'text_encoder/', 'text_encoder-sdnq8')]),
    ('transformer_official', 'Transformer (official, GGUF Q8_0)', True, [
        ('unsloth/Qwen-Image-2.1-GGUF', '2c31ccd392b367a6637841a143813320a02dff55',
         ['qwen-image-2.1-Q8_0.gguf'], '', 'transformers')]),
    ('transformer_uc', 'Transformer (uncensored, GGUF Q8_0)', False, [
        ('abenzerps/Qwen-Image-2.1-Uncensored-GGUF', '26fee668287d4f4050e5734a553adf8c201aeb42',
         ['qwen-image-2.1-UC-Q8_0.gguf'], '', 'transformers')]),
    ('turbo', 'Viggle turbo LoRA (4 steps)', False, [
        ('Viggle/Qwen-Image-2.1-viggle-turbo', 'bafc91e4cc934f5fb1406b22496a0bed9b99c548',
         ['LICENSE', 'NOTICE', 'Qwen-Image-2.1-viggle-turbo-4step-lora-r64.safetensors', 'scheduler/scheduler_config.json'],
         '', 'loras/viggle-turbo')]),
    ('pe_t2i', 'Prompt enhancer PE-T2I (MLX 4-bit)', False, [
        ('prithivMLmods/Qwen-Image-2.1-PE-T2I-MLX', '2d26ac502b16396fdd4b0cc21cc667831a7f6454',
         ['4bit/*.json', '4bit/*.jinja', '4bit/*.safetensors'], '4bit/', 'pe/t2i-mlx4'),
        ('Qwen/Qwen-Image-2.1-PE-T2I', 'f3ed7985c788ad75b3ab7223e0c4c51e2a43545b',
         ['system_prompt.txt', 'LICENSE'], '', 'pe/t2i-mlx4')]),
    ('pe_i2i', 'Prompt enhancer PE-I2I (MLX 4-bit)', False, [
        ('prithivMLmods/Qwen-Image-2.1-PE-I2I-MLX', '75172ef3e7b681eae8f82b9ca20f81885557018d',
         ['4bit/*.json', '4bit/*.jinja', '4bit/*.safetensors'], '4bit/', 'pe/i2i-mlx4'),
        ('Qwen/Qwen-Image-2.1-PE-I2I', '72927bc08afc99b7888ceb7d7d51a12db3700bbd',
         ['system_prompt.txt', 'LICENSE'], '', 'pe/i2i-mlx4')]),
]


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def small_file_sha256(repo, revision, path):
    url = f'https://huggingface.co/{repo}/resolve/{revision}/{quote(path, safe="/")}'
    with urllib.request.urlopen(url, timeout=60) as response:
        return hashlib.sha256(response.read()).hexdigest()


def main():
    manifest = {'components': {}}
    for key, label, required, sources in COMPONENTS:
        files = []
        for repo, revision, patterns, strip, dest in sources:
            tree = fetch_json(f'https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true')
            chosen = [x for x in tree if x['type'] == 'file' and any(fnmatch.fnmatch(x['path'], p) for p in patterns)]
            missing = [p for p in patterns if not any(fnmatch.fnmatch(x['path'], p) for x in chosen)]
            if missing:
                raise SystemExit(f'{repo}@{revision[:8]}: no files match {missing}')
            for item in sorted(chosen, key=lambda x: x['path']):
                lfs = item.get('lfs')
                sha = lfs['oid'] if lfs else small_file_sha256(repo, revision, item['path'])
                files.append(dict(repo=repo, revision=revision, path=item['path'],
                                  dest=f"{dest}/{item['path'].removeprefix(strip)}", size=item['size'], sha256=sha))
        manifest['components'][key] = dict(label=label, required=required, files=files,
                                           total=sum(f['size'] for f in files))
        print(f"{key:22} {len(files):3} files  {manifest['components'][key]['total'] / 1e9:7.2f} GB")
    OUTPUT.write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    print('Wrote', OUTPUT)


if __name__ == '__main__':
    main()
