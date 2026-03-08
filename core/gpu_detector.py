"""GPU detection utilities."""
import subprocess
import re


def get_gpu_info() -> dict:
    """Get GPU information including name and VRAM.
    
    Returns:
        dict with keys: available (bool), name (str), vram_gb (float), message (str)
    """
    try:
        # Try using nvidia-smi first (NVIDIA GPUs)
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                lines = output.split('\n')
                if lines:
                    parts = lines[0].split(',')
                    gpu_name = parts[0].strip()
                    vram_mb = float(parts[1].strip()) if len(parts) > 1 else 0
                    vram_gb = vram_mb / 1024
                    return {
                        "available": True,
                        "name": gpu_name,
                        "vram_gb": vram_gb,
                        "message": f"{gpu_name} ({vram_gb:.1f}GB VRAM)"
                    }
    except Exception:
        pass
    
    try:
        # Try using torch to detect CUDA GPU
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            # Try to get VRAM, may not be accurate
            vram_gb = 0
            try:
                props = torch.cuda.get_device_properties(0)
                vram_gb = props.total_memory / (1024**3)
            except Exception:
                pass
            return {
                "available": True,
                "name": gpu_name,
                "vram_gb": vram_gb,
                "message": f"{gpu_name} ({vram_gb:.1f}GB VRAM)" if vram_gb > 0 else gpu_name
            }
    except Exception:
        pass
    
    return {
        "available": False,
        "name": "No GPU detected",
        "vram_gb": 0,
        "message": "No GPU detected - Local Processing requires a GPU"
    }


def is_gpu_available() -> bool:
    """Check if GPU is available."""
    return get_gpu_info()["available"]


def get_gpu_capacity() -> str:
    """Get GPU capacity category.
    
    Returns:
        str: "high" (16GB+), "medium" (8-16GB), "low" (<8GB), or "none"
    """
    info = get_gpu_info()
    if not info["available"]:
        return "none"
    
    vram = info["vram_gb"]
    if vram >= 16:
        return "high"
    elif vram >= 8:
        return "medium"
    else:
        return "low"


def get_gpu_warning() -> str | None:
    """Get warning message if GPU is insufficient.
    
    Returns:
        str or None: Warning message if GPU is not suitable
    """
    info = get_gpu_info()
    if not info["available"]:
        return "⚠️ No GPU detected. Local Processing requires a GPU with CUDA support."
    
    vram = info["vram_gb"]
    if vram < 8:
        return f"⚠️ Low VRAM ({vram:.1f}GB). Model generation may fail or be very slow. 16GB+ recommended."
    elif vram < 16:
        return f"⚠️ Moderate VRAM ({vram:.1f}GB). May work for simple models. 16GB+ recommended for best results."
    
    return None
