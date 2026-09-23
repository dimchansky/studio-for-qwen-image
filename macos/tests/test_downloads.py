"""Model manifest, per-file downloads with SHA-256 checks, disk refusal and readiness markers."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import download
import model_store

class Manifest(unittest.TestCase):
    def test_every_file_is_pinned(self):
        destinations=set()
        for key,component in model_store.MANIFEST.items():
            self.assertEqual(component['total'],sum(f['size'] for f in component['files']))
            for item in component['files']:
                self.assertRegex(item['revision'],r'^[0-9a-f]{40}$')
                self.assertRegex(item['sha256'],r'^[0-9a-f]{64}$')
                self.assertNotIn(item['dest'],destinations);destinations.add(item['dest'])
                self.assertFalse(item['dest'].startswith('/') or '..' in item['dest'])
        for key in ('base','text_encoder','transformer_official','transformer_uc','turbo','pe_t2i','pe_i2i'):self.assertIn(key,model_store.MANIFEST)
        for task in ('t2i','edit'):
            names={Path(f['dest']).name for f in model_store.files(model_store.PE_COMPONENTS[task])}
            self.assertIn('system_prompt.txt',names)
    def test_required_components(self):
        self.assertEqual(model_store.required_components(),['base','text_encoder','transformer_official'])
        self.assertEqual(model_store.required_components('uc',True,'edit'),['base','text_encoder','transformer_uc','turbo','pe_i2i'])
        with self.assertRaises(KeyError):model_store.required_components('other')

class Fetch(unittest.TestCase):
    def item(self,data,**extra):
        return dict(repo='owner/repo',revision='0'*40,path='weights/model.bin',dest='component/model.bin',size=len(data),sha256=hashlib.sha256(data).hexdigest(),**extra)
    def fake_download(self,content):
        def hf_hub_download(repo,path,revision,local_dir):
            target=Path(local_dir)/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content);return str(target)
        return hf_hub_download
    def test_verified_file_is_moved_into_place(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'QWEN_STUDIO_DISK_RESERVE_GB':'0'}):
            models=Path(temp);data=b'weights'
            with patch('huggingface_hub.hf_hub_download',self.fake_download(data)):download.fetch(models,self.item(data))
            self.assertEqual((models/'component/model.bin').read_bytes(),data)
            self.assertFalse(list((models/model_store.STAGING).rglob('model.bin')))
    def test_checksum_mismatch_is_discarded(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{'QWEN_STUDIO_DISK_RESERVE_GB':'0'}):
            models=Path(temp)
            with patch('huggingface_hub.hf_hub_download',self.fake_download(b'tampered')):
                with self.assertRaises(RuntimeError):download.fetch(models,self.item(b'expected'))
            self.assertFalse((models/'component/model.bin').exists())
            self.assertFalse(list(models.rglob('model.bin')))
    def test_disk_space_is_checked_first(self):
        with tempfile.TemporaryDirectory() as temp:
            called=[]
            with patch('download.shutil.disk_usage',return_value=type('usage',(),{'free':10})()), patch('huggingface_hub.hf_hub_download',lambda *a,**k:called.append(1)):
                with self.assertRaises(RuntimeError) as error:download.fetch(Path(temp),self.item(b'x'*100))
            self.assertIn('Not enough disk space',str(error.exception));self.assertFalse(called)
    def test_ready_needs_marker_and_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            models=Path(temp);files=model_store.files('turbo')
            self.assertFalse(model_store.ready(models,'turbo'))
            for item in files:
                target=models/item['dest'];target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('wb') as stream:stream.truncate(item['size'])
            self.assertFalse(model_store.ready(models,'turbo'))
            model_store.marker(models,'turbo').parent.mkdir(parents=True);model_store.marker(models,'turbo').write_text('{}')
            self.assertTrue(model_store.ready(models,'turbo'))
            self.assertEqual(model_store.status(models,'turbo')['bytes'],model_store.MANIFEST['turbo']['total'])

if __name__=='__main__':unittest.main()
