"""The MPS VAE patch must be exact: identical to diffusers on CPU and to CPU on the GPU."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import torch
from diffusers.models.autoencoders.autoencoder_kl_qwenimage21 import QwenImage21AvgDown3D
import mps_patches

class AvgDownPatch(unittest.TestCase):
    def test_patch_matches_original(self):
        original=QwenImage21AvgDown3D.forward
        torch.manual_seed(0)
        for frames in (1,2,3):
            block=QwenImage21AvgDown3D(96,192,factor_t=2,factor_s=2)
            sample=torch.randn(1,96,frames,64,48)
            expected=original(block,sample)
            mps_patches.install()
            try:self.assertTrue(torch.equal(expected,block(sample)),frames)
            finally:QwenImage21AvgDown3D.forward=original
    @unittest.skipUnless(torch.backends.mps.is_available(),'needs an Apple GPU')
    def test_patch_is_exact_on_mps(self):
        original=QwenImage21AvgDown3D.forward
        block=QwenImage21AvgDown3D(96,192,factor_t=2,factor_s=2)
        sample=torch.randn(1,96,1,128,128)
        expected=original(block,sample)
        mps_patches.install()
        try:
            try:result=block(sample.to('mps')).cpu()
            except RuntimeError as error:
                # CI virtual machines expose MPS without usable GPU memory.
                if 'out of memory' in str(error).lower():self.skipTest('MPS has no usable memory here')
                raise
            self.assertEqual(float((result-expected).abs().max()),0.0)
        finally:QwenImage21AvgDown3D.forward=original

if __name__=='__main__':unittest.main()
