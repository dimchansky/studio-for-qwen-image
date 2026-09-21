"""Download endpoints for the same pinned, SHA-256-verified model files."""
from urllib.parse import quote, urlencode

HF_REVISION = 'b3179ad355be050328e483a9dfdd9e60cd62adfa'
SOURCES = [
    {'id': 'modelscope', 'label': 'ModelScope 魔搭', 'description': '中国大陆推荐'},
    {'id': 'huggingface', 'label': 'Hugging Face', 'description': '国际源'},
]

def validate_source(source):
    if source not in {item['id'] for item in SOURCES}:
        raise ValueError('请选择模型下载源。')
    return source

def download_url(item, source):
    validate_source(source)
    if source == 'modelscope':
        return 'https://modelscope.cn/api/v1/models/'+item.get('repo','Qwen/Qwen-Image-2.1')+'/repo?' + urlencode({'Revision': item['revision'], 'FilePath': item['path']})
    return f"https://huggingface.co/{item.get('repo','Qwen/Qwen-Image-2.1')}/resolve/{item.get('hf_revision',HF_REVISION)}/" + quote(item['path'], safe='/')
