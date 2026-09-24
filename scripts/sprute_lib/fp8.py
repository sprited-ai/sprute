"""Scaled FP8 linear inference using PyTorch CUDA kernels (no Comfy dependency)."""
import torch
from torch import nn
import torch.nn.functional as F
from functools import lru_cache


def check_fp8_backend(device):
    """Probe the actual kernel once per device, rather than guessing from GPU names."""
    device = torch.device(device)
    if device.type != 'cuda':
        raise RuntimeError('This FP8 backend currently supports CUDA only; '
                           'this is a backend limitation, not a limitation of FP8.')
    index = device.index if device.index is not None else torch.cuda.current_device()
    _probe_fp8_kernel(index)


@lru_cache(maxsize=None)
def _probe_fp8_kernel(index):
    device = torch.device('cuda', index)
    try:
        a = torch.ones((16, 16), device=device, dtype=torch.float8_e4m3fn)
        scale = torch.ones((), device=device, dtype=torch.float32)
        result = torch._scaled_mm(a, a.t(), scale_a=scale, scale_b=scale,
                                  out_dtype=torch.bfloat16, use_fast_accum=False)
        torch.cuda.synchronize(device)
        if not torch.all(result == 16).item():
            raise RuntimeError('FP8 kernel returned an unexpected result')
    except torch.cuda.OutOfMemoryError:
        raise
    except (RuntimeError, NotImplementedError, AttributeError) as exc:
        raise RuntimeError(
            f'This FP8 backend failed its kernel check on {device} '
            f'(PyTorch {torch.__version__}). Use --precision bf16 for turntable '
            f'or --turntable-precision bf16 for run. Original error: {exc}') from exc


class FP8Linear(nn.Module):
    def __init__(self, weight, bias, scale):
        super().__init__()
        if weight.dtype != torch.float8_e4m3fn or weight.ndim != 2:
            raise ValueError('Expected an E4M3 FP8 linear weight')
        self.register_buffer('weight', weight)
        self.register_buffer('scale_weight', scale.float().reshape(()))
        self.register_buffer('bias', None if bias is None else bias.to(torch.bfloat16))

    def _apply(self, fn, recurse=True):
        # Upstream calls model.to(bfloat16). Move buffers but preserve quantization.
        weight = self._buffers.pop('weight')
        scale = self._buffers.pop('scale_weight')
        try:
            super()._apply(fn, recurse)
            probe = fn(torch.empty(0, device=weight.device))
            self._buffers['weight'] = weight.to(device=probe.device)
            self._buffers['scale_weight'] = scale.to(device=probe.device, dtype=torch.float32)
        except BaseException:
            self._buffers['weight'] = weight
            self._buffers['scale_weight'] = scale
            raise
        return self

    def forward(self, x):
        check_fp8_backend(x.device)
        shape = x.shape
        flat = x.reshape(-1, shape[-1])
        scale = flat.abs().amax().float().clamp_min(1e-12) / 448.0
        # Division owns fresh storage; clamp it in place to avoid another FP32 copy.
        quantized = (flat.float() / scale).clamp_(-448, 448).to(torch.float8_e4m3fn)
        # cuBLAS FP8 requires row counts aligned to 16.
        rows = flat.shape[0]
        if rows % 16:
            quantized = F.pad(quantized, (0, 0, 0, 16 - rows % 16))
        result = torch._scaled_mm(quantized.contiguous(), self.weight.t(),
            scale_a=scale, scale_b=self.scale_weight,
            out_dtype=torch.bfloat16, use_fast_accum=False)
        result = result[:rows]
        if self.bias is not None:
            result = result + self.bias
        return result.reshape(*shape[:-1], self.weight.shape[0]).to(x.dtype)


def quantize_linears(model):
    """Quantize after LoRA fusion; retain norms, convolutions and embeddings."""
    count = 0
    for name, layer in list(model.named_modules()):
        if not isinstance(layer, nn.Linear):
            continue
        if layer.in_features % 16 or layer.out_features % 16:
            continue
        weight = layer.weight.detach().float()
        scale = weight.abs().amax().clamp_min(1e-12) / 448.0
        encoded = (weight / scale).clamp(-448, 448).to(torch.float8_e4m3fn)
        parent, _, child = name.rpartition('.')
        setattr(model.get_submodule(parent), child,
                FP8Linear(encoded, None if layer.bias is None else layer.bias.detach(), scale))
        count += 1
    return count
