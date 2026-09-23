"""Fail CI when application copy is added without English and Russian translations."""
import ast
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
CJK=re.compile('[\u4e00-\u9fff]')

class Markup(HTMLParser):
    def __init__(self):super().__init__();self.copy=[]
    def handle_data(self,value):
        if CJK.search(value):self.copy.append(value.strip())
    def handle_starttag(self,tag,attrs):
        for name,value in attrs:
            if name in ('title','alt','aria-label','placeholder','label') and value and CJK.search(value):self.copy.append(value.strip())

WEB=ROOT/'macos/web'
CATALOGS={code:json.loads((WEB/'locales'/f'{code}.json').read_text(encoding='utf-8')) for code in ('en','ru')}

class TranslationCoverage(unittest.TestCase):
    def test_all_static_markup(self):
        parsed=Markup();parsed.feed((WEB/'index.html').read_text(encoding='utf-8'))
        for code,catalog in CATALOGS.items():
            # Contextual entries (context:text) also cover their text; the welcome line has its own copy.
            keys=set(catalog)|{k.split(':',1)[1] for k in catalog if ':' in k}
            missing=set(parsed.copy)-keys-{'今天，想创作些什么？'}
            missing={m for m in missing if not re.fullmatch(r'\d+ × \d+（\d+:\d+）',m)}  # translated by a pattern
            self.assertFalse(missing,(code,missing))
    def test_backend_application_copy(self):
        # These fragments form documented templates, diagnostic matching or SQL.
        fragments={'流程图|图表|海报|信息图|时间线','英文|英语|English','正在生成 ','内存不足。请关闭其他大型应用，或选择较小的尺寸、较少的参考图，再重试。\n',
                   '未检测到 gpu 加速','未检测到可用的','当前显卡不支持','需要修复环境','“([^”\n]+)”|「([^」\n]+)」|"([^"\n]+)"',
                   '请先在“模型设置”中下载：','下载中断。点击继续下载可重试；已完成的文件会保留。'}
        for code,catalog in CATALOGS.items():
            missing=set()
            for file in (ROOT/'macos/backend').glob('*.py'):
                for node in ast.walk(ast.parse(file.read_text(encoding='utf-8-sig'))):
                    if isinstance(node,ast.Constant) and isinstance(node.value,str) and CJK.search(node.value) and not node.value.startswith('UPDATE '):
                        if node.value not in catalog and node.value not in fragments:missing.add(node.value)
            self.assertFalse(missing,(code,missing))

if __name__=='__main__':unittest.main()
