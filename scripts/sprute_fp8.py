"""Scaled FP8 linear inference using PyTorch CUDA kernels (no Comfy dependency)."""
import torch
from torch import nn
import torch.nn.functional as F


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
        if x.device.type != 'cuda':
            raise RuntimeError('FP8 execution requires a supported CUDA GPU')
        shape = x.shape
        flat = x.reshape(-1, shape[-1])
        scale = flat.abs().amax().float().clamp_min(1e-12) / 448.0
        quantized = (flat.float() / scale).clamp(-448, 448).to(torch.float8_e4m3fn)
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
