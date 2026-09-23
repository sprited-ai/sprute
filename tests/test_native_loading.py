"""Real upstream architecture, tiny dimensions: regression for FP32 CPU OOM."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))


class NativeLoadingTests(unittest.TestCase):
    def test_linked_anisora_scaled_weights_and_strict_validation(self):
        source = Path(__file__).resolve().parents[1]/'models/_sources/anisora/anisoraV3.2'
        if not source.exists():
            self.skipTest('Install pinned native source with models setup first')
        script = '''
import sys, torch, tempfile
from pathlib import Path
from safetensors.torch import save_file
sys.path.insert(0, sys.argv[1])
import wan.image2video as module
from sprute_lib.loading import linked_anisora
original=module.WanModel
reference=original(dim=32,ffn_dim=64,freq_dim=16,num_heads=4,num_layers=1)
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)/'low_noise_model'; folder.mkdir()
    reference.save_config(folder)
    state={}; expected={}
    for key,value in reference.state_dict().items():
        if key.endswith('.weight'):
            encoded=value.to(torch.float8_e4m3fn)
            state[key]=encoded
            state[key.removesuffix('.weight')+'.scale_weight']=torch.tensor([0.5])
            expected[key]=encoded.to(torch.bfloat16)*0.5
        else:
            state[key]=value.to(torch.bfloat16)
            expected[key]=state[key]
    state['scaled_fp8']=torch.tensor([1.0])
    weights=folder/'diffusion_pytorch_model.safetensors'
    save_file(state,weights)
    with linked_anisora(module,True):
        model=module.WanModel.from_pretrained(tmp,subfolder='low_noise_model')
        for key,value in model.state_dict().items():
            torch.testing.assert_close(value,expected[key],rtol=0,atol=0)
    assert module.WanModel is original
    state.pop(next(iter(expected)))
    save_file(state,weights)
    try:
        with linked_anisora(module,True):
            module.WanModel.from_pretrained(tmp,subfolder='low_noise_model')
    except ValueError:
        pass
    else:
        raise AssertionError('Missing checkpoint parameter was accepted')
    assert module.WanModel is original
'''
        subprocess.run([sys.executable, '-c', script, str(source)],
                       cwd=Path(__file__).resolve().parents[1]/'scripts', check=True)

    def test_meta_load_assigns_bf16_without_initial_fp32_parameters(self):
        source = Path(__file__).resolve().parents[1]/'models/_sources/scail2'
        if not source.exists():
            self.skipTest('Install pinned native source with models setup first')
        script = '''
import json, sys, torch
sys.path.insert(0, sys.argv[1])
import wan.scail as module
from sprute_lib.loading import low_memory_scail
cfg=json.load(open(sys.argv[1]+'/configs/config-14b.json'))
cfg.update(dim=32,ffn_dim=64,freq_dim=16,num_heads=4,num_layers=1)
original=module.SCAIL2Model
reference=original.from_config(cfg)
state={k:v.to(torch.float16) for k,v in reference.state_dict().items()}
with low_memory_scail(module):
    model=module.SCAIL2Model.from_config(cfg)
    assert all(p.is_meta for p in model.parameters())
    model.load_state_dict(state)
    assert all(not p.is_meta and p.dtype==torch.bfloat16 for p in model.parameters())
    for key,value in model.state_dict().items():
        torch.testing.assert_close(value,state[key],rtol=0,atol=0)
assert module.SCAIL2Model is original
'''
        subprocess.run([sys.executable, '-c', script, str(source)],
                       cwd=Path(__file__).resolve().parents[1]/'scripts', check=True)

if __name__ == '__main__':
    unittest.main()
