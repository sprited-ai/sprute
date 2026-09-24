"""Memory-safe construction for the pinned SCAIL2 upstream pipeline."""
from contextlib import contextmanager
import logging


@contextmanager
def linked_anisora(module, enabled, precision='bf16'):
    """Read existing KJ scaled-FP8 weights into the upstream BF16 architecture."""
    if not enabled:
        yield
        return
    from pathlib import Path
    import torch
    from safetensors import safe_open
    from accelerate import init_empty_weights
    original_class = module.WanModel

    class LinkedModel(original_class):
        @classmethod
        def from_pretrained(cls, path, subfolder, **kwargs):
            folder = Path(path)/subfolder
            config = cls.load_config(str(folder))
            with init_empty_weights():
                model = cls.from_config(config)
            expected = model.state_dict()
            with safe_open(str(folder/'diffusion_pytorch_model.safetensors'), framework='pt') as f:
                keys = set(f.keys())
                scales = {k for k in keys if k.endswith('.scale_weight')}
                if keys - scales - {'scaled_fp8'} != set(expected):
                    raise ValueError('AniSora checkpoint keys do not match upstream architecture')
                state = {}
                quantized_layers = {}
                linear_names = {name for name, layer in model.named_modules()
                                if isinstance(layer, torch.nn.Linear)}
                for name, parameter in expected.items():
                    tensor = f.get_tensor(name)
                    if tensor.shape != parameter.shape:
                        raise ValueError(f'AniSora tensor shape mismatch: {name}')
                    scale = name.removesuffix('.weight') + '.scale_weight'
                    layer_name = name.removesuffix('.weight')
                    if (precision == 'fp8' and name.endswith('.weight')
                            and layer_name in linear_names and scale in scales):
                        if tensor.dtype != torch.float8_e4m3fn:
                            raise ValueError(f'Expected FP8 checkpoint tensor: {name}')
                        state[name] = tensor
                        quantized_layers[layer_name] = f.get_tensor(scale)
                        continue
                    value = tensor.to(torch.bfloat16)
                    if name.endswith('.weight') and scale in scales:
                        value.mul_(f.get_tensor(scale).to(torch.bfloat16))
                    state[name] = value
            model.load_state_dict(state, strict=True, assign=True)
            if precision == 'fp8':
                from sprute_lib.fp8 import FP8Linear
                for name, scale in quantized_layers.items():
                    layer = model.get_submodule(name)
                    parent_name, _, child = name.rpartition('.')
                    parent = model.get_submodule(parent_name) if parent_name else model
                    setattr(parent, child, FP8Linear(layer.weight.detach(),
                        None if layer.bias is None else layer.bias.detach(), scale))
                if not quantized_layers:
                    raise ValueError('No scaled FP8 linear layers found')
            logging.info('Loaded linked AniSora %s: %s (%d FP8 linears)',
                         subfolder, precision, len(quantized_layers))
            return model

    module.WanModel = LinkedModel
    try:
        yield
    finally:
        module.WanModel = original_class


@contextmanager
def low_memory_scail(module):
    """Avoid upstream's full FP32 initialization + simultaneous checkpoint copy.

    Scoped to construction in our single worker. Upstream files are untouched.
    load_state_dict(assign=True) binds real weights into a meta-device model.
    """
    import torch
    from accelerate import init_empty_weights
    original_class = module.SCAIL2Model

    class LowMemoryModel(original_class):
        @classmethod
        def from_config(cls, config, **kwargs):
            if isinstance(config, (str, bytes)):
                config = cls.load_config(config)
            logging.info('Creating SCAIL2 structure on meta device (no FP32 weight allocation)')
            with init_empty_weights():
                return super().from_config(config, **kwargs)

        def load_state_dict(self, state_dict, strict=True, assign=False):
            if any(p.is_meta for p in self.parameters()):
                logging.info('Binding SCAIL2 checkpoint in BF16')
                # Comfy scaled-FP8 checkpoints store one multiplier per weight.
                state_dict.pop('scaled_fp8', None)
                for name in [k for k in state_dict if k.endswith('.scale_weight')]:
                    weight = name.removesuffix('.scale_weight') + '.weight'
                    scale = state_dict.pop(name)
                    if weight not in state_dict or scale.numel() != 1:
                        raise ValueError(f'Invalid SCAIL2 weight scale: {name}')
                    state_dict[weight] = state_dict[weight].to(torch.bfloat16) * scale.to(torch.bfloat16)
                # Replace each mapped tensor as we go, not a second full dictionary.
                for name in list(state_dict):
                    value = state_dict[name]
                    if value.is_floating_point() and value.dtype != torch.bfloat16:
                        state_dict[name] = value.to(dtype=torch.bfloat16)
                result = super().load_state_dict(state_dict, strict=strict, assign=True)
                if any(p.is_meta for p in self.parameters()):
                    raise RuntimeError('SCAIL2 checkpoint left uninitialized parameters')
                return result
            return super().load_state_dict(state_dict, strict=strict, assign=assign)

    module.SCAIL2Model = LowMemoryModel
    try:
        yield
    finally:
        module.SCAIL2Model = original_class
