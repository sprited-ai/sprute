"""Load existing scaled-FP8 UMT5 weights into the native Wan encoder."""
import re
import sys
from contextlib import contextmanager
import torch
from accelerate import init_empty_weights
from safetensors import safe_open
from sprute_lib.fp8 import FP8Linear


@contextmanager
def linked_text_encoder(pipeline_module, checkpoint):
    if not checkpoint:
        yield
        return
    original = pipeline_module.T5EncoderModel
    t5 = sys.modules[original.__module__]

    class LinkedEncoder(original):
        def __init__(self, text_len, dtype=torch.bfloat16, device='cpu',
                     checkpoint_path=None, tokenizer_path=None, shard_fn=None):
            if shard_fn is not None:
                raise ValueError('FP8 UMT5 adapter does not support distributed sharding')
            self.text_len, self.dtype, self.device = text_len, dtype, device
            self.checkpoint_path, self.tokenizer_path = checkpoint, tokenizer_path
            self.model = load_encoder(t5, checkpoint).to(device)
            self.tokenizer = t5.HuggingfaceTokenizer(
                name=tokenizer_path, seq_len=text_len, clean='whitespace')

    pipeline_module.T5EncoderModel = LinkedEncoder
    try:
        yield
    finally:
        pipeline_module.T5EncoderModel = original


def checkpoint_key(name):
    if name == 'token_embedding.weight':
        return 'shared.weight'
    if name == 'norm.weight':
        return 'encoder.final_layer_norm.weight'
    name = re.sub(r'^blocks\.(\d+)\.', r'encoder.block.\1.', name)
    for source, target in [
        ('norm1.', 'layer.0.layer_norm.'), ('norm2.', 'layer.1.layer_norm.'),
        ('attn.', 'layer.0.SelfAttention.'),
        ('pos_embedding.embedding.', 'layer.0.SelfAttention.relative_attention_bias.'),
        ('ffn.gate.0.', 'layer.1.DenseReluDense.wi_0.'),
        ('ffn.fc1.', 'layer.1.DenseReluDense.wi_1.'),
        ('ffn.fc2.', 'layer.1.DenseReluDense.wo.')]:
        name = name.replace(source, target)
    return name


def load_encoder(t5_module, checkpoint):
    with init_empty_weights():
        model = t5_module.umt5_xxl(encoder_only=True, return_tokenizer=False,
                                  dtype=torch.bfloat16, device='meta')
    state, scales = {}, {}
    with safe_open(str(checkpoint), framework='pt') as weights:
        for name, parameter in model.state_dict().items():
            key = checkpoint_key(name)
            value = weights.get_tensor(key)
            if value.shape != parameter.shape:
                raise ValueError(f'UMT5 shape mismatch: {key}')
            if value.dtype == torch.float8_e4m3fn:
                layer = name.removesuffix('.weight')
                if not isinstance(model.get_submodule(layer), torch.nn.Linear):
                    raise ValueError(f'Unsupported FP8 UMT5 parameter: {name}')
                scales[layer] = weights.get_tensor(key.removesuffix('.weight')+'.scale_weight')
                state[name] = value
            else:
                state[name] = value.to(torch.bfloat16)
    model.load_state_dict(state, strict=True, assign=True)
    for name, scale in scales.items():
        layer = model.get_submodule(name)
        parent, _, child = name.rpartition('.')
        setattr(model.get_submodule(parent), child,
                FP8Linear(layer.weight.detach(), None, scale))
    if not scales:
        raise ValueError('Checkpoint has no FP8 UMT5 layers')
    return model.eval().requires_grad_(False)
