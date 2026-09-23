"""PyTorch SDPA fallback for official Wan modules when FlashAttention isn't installed."""
import sys

def sdpa(q, k, v, q_lens=None, k_lens=None, dropout_p=0., softmax_scale=None,
         q_scale=None, causal=False, window_size=(-1, -1), deterministic=False,
         dtype=None, version=None, **kwargs):
    import torch
    from torch.nn.functional import scaled_dot_product_attention
    if window_size != (-1, -1):
        raise ValueError('Native Sprute SDPA fallback supports full attention only')
    # Slice each sequence, so padding never contributes to attention.
    result = torch.zeros_like(q)
    for b in range(q.shape[0]):
        nq = int(q_lens[b]) if q_lens is not None else q.shape[1]
        nk = int(k_lens[b]) if k_lens is not None else k.shape[1]
        qb = q[b, :nq].transpose(0, 1).unsqueeze(0).to(v.dtype)
        kb = k[b, :nk].transpose(0, 1).unsqueeze(0).to(v.dtype)
        vb = v[b, :nk].transpose(0, 1).unsqueeze(0)
        if q_scale is not None:
            qb = qb*q_scale
        output = scaled_dot_product_attention(qb, kb, vb, dropout_p=dropout_p,
                    is_causal=causal, scale=softmax_scale)
        result[b, :nq] = output.squeeze(0).transpose(0, 1).to(q.dtype)
    return result

def install_if_needed():
    from wan.modules import attention as module
    if module.FLASH_ATTN_2_AVAILABLE or module.FLASH_ATTN_3_AVAILABLE:
        return 'flash-attention'
    original = module.flash_attention
    for name, loaded in list(sys.modules.items()):
        if name.startswith('wan.') and getattr(loaded, 'flash_attention', None) is original:
            loaded.flash_attention = sdpa
    return 'torch-sdpa'
