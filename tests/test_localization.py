"""Fail CI when application copy is added without an English translation."""
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

class TranslationCoverage(unittest.TestCase):
    def test_all_static_markup(self):
        for platform in ('macos','windows'):
            web=ROOT/platform/'web';catalog=json.loads((web/'locales.json').read_text(encoding='utf-8'))
            for filename in ('index.html','environment.html'):
                parsed=Markup();parsed.feed((web/filename).read_text(encoding='utf-8'))
                missing=set(parsed.copy)-set(catalog)-{'今天，想创作些什么？'} # dedicated bilingual welcome sequences
                self.assertFalse(missing,(platform,filename,missing))
    def test_backend_application_copy(self):
        # These fragments form documented templates, diagnostic matching or SQL.
        fragments={'流程图|图表|海报|信息图|时间线','英文|英语|English','正在生成 ','校验失败，请重试：','内存不足。请关闭其他大型应用，将图片尺寸降至 512，再重试。\n','未检测到 gpu 加速','未检测到可用的','当前显卡不支持','需要修复环境'}
        for platform in ('macos','windows'):
            catalog=json.loads((ROOT/platform/'web/locales.json').read_text(encoding='utf-8'))
            missing=set()
            for file in (ROOT/platform/'backend').glob('*.py'):
                for node in ast.walk(ast.parse(file.read_text(encoding='utf-8-sig'))):
                    if isinstance(node,ast.Constant) and isinstance(node.value,str) and CJK.search(node.value) and not node.value.startswith('UPDATE '):
                        if node.value not in catalog and node.value not in fragments:missing.add(node.value)
            self.assertFalse(missing,(platform,missing))

if __name__=='__main__':unittest.main()
