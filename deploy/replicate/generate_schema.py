"""Generate the legacy SDK schema for modern Cog builders."""
import json
import os
from pathlib import Path
import subprocess
import sys
from importlib.metadata import version

if version("cog") != "0.16.8":
    raise RuntimeError("Run with the pinned cog==0.16.8 SDK")
result = subprocess.run([sys.executable, "-m", "cog.command.openapi_schema"],
    env={**os.environ, "COG_PREDICT_TYPE_STUB": "predict.py:Predictor", "COG_GPU": "0"},
    capture_output=True, text=True, check=True)
schema = json.loads(result.stdout)

def normalize(value):
    # OpenAPI 3.0 reference objects cannot have nullable/title siblings.
    if isinstance(value, dict):
        for child in list(value.values()):
            normalize(child)
        if "$ref" in value and len(value) > 1:
            value["allOf"] = [{"$ref": value.pop("$ref")}]
    elif isinstance(value, list):
        for child in value:
            normalize(child)

normalize(schema)
Path("openapi-upload.json").write_text(json.dumps(schema, indent=2))
print("Wrote openapi-upload.json without running model setup")
