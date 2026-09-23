"""Shared helpers for feasibility spikes: paths, memory sampling, JSON summaries."""
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'macos/backend'
sys.path.insert(0, str(BACKEND))
DATA = Path(os.environ.get('QWEN_STUDIO_DATA', ROOT / 'data'))
MODELS = DATA / 'models'
SPIKES = DATA / 'spikes'
SPIKES.mkdir(parents=True, exist_ok=True)


def swap_used_gb():
    out = subprocess.run(['sysctl', '-n', 'vm.swapusage'], capture_output=True, text=True).stdout
    # "total = 6144.00M  used = 4594.44M  free = ..."
    used = out.split('used =')[1].split()[0]
    return float(used.rstrip('M')) / 1024


def versions():
    import importlib
    result = {'python': platform.python_version(), 'macos': platform.mac_ver()[0]}
    for name in ('torch', 'diffusers', 'transformers', 'sdnq', 'gguf', 'peft', 'mlx', 'mlx_vlm', 'accelerate'):
        try:
            module = importlib.import_module(name)
            result[name] = getattr(module, '__version__', 'installed')
        except Exception as error:  # noqa: BLE001 - record, do not fail the probe
            result[name] = f'unavailable: {error}'
    return result


class MemWatch:
    """Sample process RSS, MPS driver allocation and swap in the background."""

    def __init__(self, interval=0.5):
        import psutil
        self.process = psutil.Process()
        self.interval = interval
        self.peak_rss = 0
        self.peak_mps = 0
        self.swap_start = swap_used_gb()
        self.swap_peak = self.swap_start
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        import torch
        while not self._stop.is_set():
            self.sample(torch)
            self._stop.wait(self.interval)

    def sample(self, torch=None):
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
        if torch is not None and torch.backends.mps.is_available():
            self.peak_mps = max(self.peak_mps, torch.mps.driver_allocated_memory())
        self.swap_peak = max(self.swap_peak, swap_used_gb())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()

    def summary(self):
        return {'peak_rss_gb': round(self.peak_rss / 1024**3, 2), 'peak_mps_gb': round(self.peak_mps / 1024**3, 2),
                'swap_start_gb': round(self.swap_start, 2), 'swap_peak_gb': round(self.swap_peak, 2)}


def save(name, result):
    result = {'spike': name, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), **result}
    path = SPIKES / f'{name}.json'
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    print('Saved', path)
    return result
