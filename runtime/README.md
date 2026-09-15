# Isolated runtime dependency evidence

For the current SCAIL walking models, start with the
[model installation guide](../docs/animation-scail-setup.md).
`install-models.py` installs pinned weights and `verify-models.py` checks existing
files. Run `python3 runtime/test-install-models.py` from the checkout to exercise
the installer's integrity and failure handling. These helpers do not install
the runtime dependencies described below.

`requirements-linux-cu128.txt` pins the104 distributions installed successfully
in experiment074's fresh virtual environment. `python-artifacts.json` records
the exact wheel URLs and hashes returned by pip, plus the resolver environment.
This profile targets Linux x86_64 and Python3.12 with CUDA12.8 PyTorch wheels.
It is not a macOS, Windows or CPU requirements file.

The tested install used ComfyUI0.33.1 and VideoHelperSuite1.7.9 requirements under
an observed-version constraints file. pip check passed and the isolated server
started with all14 required node classes and4 model names. Experiment075 then
completed one65-frame WAN S-view video in91.21seconds; all frames were inspected
in contact sheets. This is runtime execution evidence, not motion-quality approval. The flattened104-line
requirements file was generated from that successful install; installing directly
from this derived file has not yet been tested. Existing model weights were
shared by symlink after their full hashes had been verified; they were not
redownloaded. The GPU host still has the NVML mismatch documented in
[the runtime inventory](../docs/animation-runtime.md).

The code/package pins are in [animation-runtime-lock.json](../docs/animation-runtime-lock.json).
Model files, notices, frame-review tools and motion templates are separate pieces.
A complete beginner installer and cross-machine reproduction remain in development.

Newer execution evidence: 083 directly installed the derived requirements;
232 used that environment with a clean code checkout for successful SCAIL S-view
inference. 235 ran `prepare-server.py` into a new folder with actual pip hash
enforcement: all 104 versions, URLs and hashes matched and `pip check` passed.
235 server startup/inference remain untested. See the individual experiment
records for their distinct scopes; these all share the same Linux GPU host.
