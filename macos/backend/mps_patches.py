"""Workarounds for PyTorch MPS bugs that affect Qwen-Image-2.1.

torch <= 2.14 corrupts rank-5 `F.pad` on MPS (pytorch#194922, fixed only in 2.15
nightlies). The Qwen-Image-2.1 VAE uses one such pad in `QwenImage21AvgDown3D`, so
every VAE *encode* (edits, references) comes out broken on Apple GPUs. Prepending
zero frames with `torch.cat` is mathematically identical and unaffected.
"""
import torch


def _avg_down_forward(self, x):
    pad_t = (self.factor_t - x.shape[2] % self.factor_t) % self.factor_t
    if pad_t:
        x = torch.cat([x.new_zeros((x.shape[0], x.shape[1], pad_t, *x.shape[3:])), x], dim=2)
    batch, channels, frames, height, width = x.shape
    ft, fs = self.factor_t, self.factor_s
    x = x.view(batch, channels, frames // ft, ft, height // fs, fs, width // fs, fs)
    x = x.permute(0, 1, 3, 5, 7, 2, 4, 6).contiguous()
    x = x.view(batch, self.out_channels, self.group_size, frames // ft, height // fs, width // fs)
    return x.mean(dim=2)


_avg_down_forward._studio_patched = True


def install():
    from diffusers.models.autoencoders import autoencoder_kl_qwenimage21 as vae
    vae.QwenImage21AvgDown3D.forward = _avg_down_forward


def installed():
    from diffusers.models.autoencoders import autoencoder_kl_qwenimage21 as vae
    return getattr(vae.QwenImage21AvgDown3D.forward, '_studio_patched', False)
