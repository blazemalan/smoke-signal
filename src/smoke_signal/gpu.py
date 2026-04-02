"""GPU detection and VRAM checks."""

import os
import platform
import sys

# On Windows, add nvidia DLL directories to PATH before importing torch.
# pip-installed PyTorch puts cuDNN/cuBLAS DLLs in site-packages/nvidia/*/bin/
# but Windows doesn't know to look there unless we add them.
if platform.system() == "Windows":
    _site_packages = os.path.join(sys.prefix, "Lib", "site-packages", "nvidia")
    if os.path.isdir(_site_packages):
        for _subdir in os.listdir(_site_packages):
            _bin = os.path.join(_site_packages, _subdir, "bin")
            if os.path.isdir(_bin) and _bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")

import torch


VRAM_ESTIMATES_MB = {
    "large-v3": {"float16": 10000, "float32": 20000},
    "large-v3-turbo": {"float16": 8000, "float32": 16000},
    "medium": {"float16": 5000, "float32": 10000},
    "small": {"float16": 2000, "float32": 4000},
    "base": {"float16": 1000, "float32": 2000},
    "tiny": {"float16": 500, "float32": 1000},
}

DIARIZATION_VRAM_MB = 2000  # pyannote 4.0.x peak


def check_gpu() -> dict:
    """Check GPU availability and return info dict."""
    if not torch.cuda.is_available():
        return {
            "available": False,
            "device": "cpu",
            "name": None,
            "vram_total_mb": 0,
            "vram_free_mb": 0,
            "cuda_version": None,
            "compute_capability": None,
        }

    props = torch.cuda.get_device_properties(0)
    vram_total = props.total_memory // (1024 * 1024)
    vram_free = (props.total_memory - torch.cuda.memory_allocated(0)) // (1024 * 1024)

    cc = f"{props.major}.{props.minor}"

    return {
        "available": True,
        "device": "cuda",
        "name": props.name,
        "vram_total_mb": vram_total,
        "vram_free_mb": vram_free,
        "cuda_version": torch.version.cuda,
        "compute_capability": cc,
    }


def estimate_vram(model_name: str, compute_type: str) -> int:
    """Return estimated peak VRAM in MB for transcription."""
    ct = "float16" if compute_type != "float32" else "float32"
    return VRAM_ESTIMATES_MB.get(model_name, VRAM_ESTIMATES_MB["large-v3"]).get(ct, 10000)


def check_vram_sufficient(model_name: str, compute_type: str, gpu_info: dict) -> tuple[bool, str]:
    """Check if GPU has enough VRAM for the chosen model."""
    if not gpu_info["available"]:
        return False, "No CUDA GPU detected. Transcription will run on CPU (very slow)."

    needed = estimate_vram(model_name, compute_type)
    available = gpu_info["vram_total_mb"]

    if available < needed:
        return False, (
            f"Model {model_name} ({compute_type}) needs ~{needed}MB VRAM, "
            f"but GPU has {available}MB. Try a smaller model (--model medium) "
            f"or use float16 (--compute-type float16)."
        )

    return True, f"VRAM OK: {available}MB available, ~{needed}MB needed for {model_name} ({compute_type})"
