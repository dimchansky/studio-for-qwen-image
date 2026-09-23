"""Download the official demo inputs used by the hardware checks into data/testimages/space (~5 MB).

Source: the example cases of the official Qwen-Image-2.1 Hugging Face Space.
"""
import urllib.request

from common import DATA

BASE = 'https://huggingface.co/spaces/Qwen/Qwen-Image-2.1/resolve/main/examples/'
FILES = ['cases.json'] + [f'{name}.webp' for name in (
    '2d02ee93-6278-4aa9-8fb9-3ca8d4c89dbb',  # hairstyle edit (single reference, VAE check)
    'd085337f-fdc8-419c-8f6f-fd21f32a612e', 'a5fa8e4a-9064-402e-b7d2-3d6254af97cb',  # separate mask
    '7922c916-518b-4c07-a7d1-819ecc4ae88c',  # coloured box annotations
    '895cfefb-8b12-4d57-89ea-e396f1554440',  # white painted region
    '8c265cf7-51ec-44fd-9436-30fbd96491de',  # old photo restoration
    '447da49d-dcd0-46ec-9ca8-20127c0f07d1', '0f2d052b-6ccf-46e2-821d-d073ead679ac',  # outfit, five references
    '3f4d7519-6c33-491f-bad8-661f1bf03601', '0f5d38f9-d04a-498e-aaef-9dae01da8c6d',
    '3acf3276-0572-490e-b8ce-334833a6ca20')]

target = DATA / 'testimages' / 'space'
target.mkdir(parents=True, exist_ok=True)
for name in FILES:
    path = target / name
    if path.exists():
        continue
    with urllib.request.urlopen(BASE + name, timeout=60) as response:
        path.write_bytes(response.read())
    print('Downloaded', path)
print('Test images are in', target)
