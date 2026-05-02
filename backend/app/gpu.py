from __future__ import annotations


def require_cuda_device():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for GPU training. Install backend requirements with the CUDA wheel index."
        ) from exc

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU is required for ML training. Install NVIDIA drivers, CUDA-enabled PyTorch, "
            "then rerun from the project virtual environment."
        )

    torch.backends.cudnn.benchmark = True
    return torch.device("cuda")


def gpu_summary() -> dict[str, str | int | bool]:
    try:
        import torch
    except ImportError:
        return {"torch_installed": False, "cuda_available": False}

    if not torch.cuda.is_available():
        return {"torch_installed": True, "cuda_available": False}

    device_index = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(device_index)
    return {
        "torch_installed": True,
        "cuda_available": True,
        "device_index": device_index,
        "device_name": torch.cuda.get_device_name(device_index),
        "memory_gb": round(props.total_memory / (1024**3), 2),
    }

