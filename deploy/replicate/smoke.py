"""One bounded public-model prediction; never retries a create request."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

API = "https://api.replicate.com/v1"
MODEL = "sprited/sprute"
TERMINAL = {"succeeded", "failed", "canceled", "aborted"}


def validate_schema(schema):
    """Reject malformed image labels before a prediction can get stuck starting."""
    if not isinstance(schema, dict):
        raise ValueError("Model has no OpenAPI schema")
    definitions = schema.get("components", {}).get("schemas", {})
    if not all(name in definitions for name in ("Input", "Output")):
        raise ValueError("Model schema is missing Input or Output")
    def check(value):
        if isinstance(value, dict):
            if "" in value:
                raise ValueError("Model schema contains an empty key; check Docker label $ref escaping")
            if "$ref" in value:
                ref = value["$ref"]
                if not ref.startswith("#/components/schemas/") or ref.rsplit("/", 1)[-1] not in definitions:
                    raise ValueError(f"Unresolved model schema reference: {ref}")
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
    check(schema)


def run(version, token, output, *, acknowledged_active_id=None):
    output.mkdir(parents=True, exist_ok=False)

    def request(path, data=None, headers=None):
        req = Request(API + path, data=None if data is None else json.dumps(data).encode(),
                      headers={"Authorization": "Bearer " + token,
                               "User-Agent": "sprute-replicate-smoke/0.2",
                               "Content-Type": "application/json", **(headers or {})})
        with urlopen(req, timeout=30) as response:
            return json.load(response)

    model = request("/models/" + MODEL)
    if model.get("visibility") != "public":
        raise RuntimeError("Refusing private-model billing. Make sprited/sprute public first.")
    version_info = request(f"/models/{MODEL}/versions/{version}")
    if version_info.get("id") != version:
        raise RuntimeError("Version does not belong to sprited/sprute")
    validate_schema(version_info.get("openapi_schema"))
    recent = request("/predictions")
    if any(p.get("model") == MODEL and p["status"] not in TERMINAL
           and p.get("id") != acknowledged_active_id
           for p in recent.get("results", [])):
        raise RuntimeError("An existing Sprute prediction is still active; inspect it first.")

    payload = {"version": version, "input": {
        "prompt": "pixelated retro pixel art cute NPC girl wearing a pink dress",
        "stop_after": "generate", "motions": "run", "seed": 42,
    }}
    (output / "request.json").write_text(json.dumps(payload, indent=2))
    prediction = None
    started = time.monotonic()
    try:
        # The server deadline survives loss of this client or its SSH session.
        # If this POST times out, do NOT retry: the server may have accepted it.
        prediction = request("/predictions", payload, {"Cancel-After": "10m"})
        print("Prediction:", prediction["id"], flush=True)
        while True:
            (output / "prediction.json").write_text(json.dumps(prediction, indent=2))
            print(prediction["status"], round(time.monotonic() - started), "seconds", flush=True)
            if prediction["status"] in TERMINAL:
                break
            if time.monotonic() - started >= 600:
                raise TimeoutError("10-minute test deadline exceeded")
            time.sleep(min(10, max(0, 600 - (time.monotonic() - started))))
            if time.monotonic() - started >= 600:
                raise TimeoutError("10-minute test deadline exceeded")
            prediction = request("/predictions/" + prediction["id"])
    finally:
        if prediction is not None and prediction["status"] not in TERMINAL:
            try:
                canceled = request("/predictions/" + prediction["id"] + "/cancel", {})
                (output / "cancellation.json").write_text(json.dumps(canceled, indent=2))
                if canceled["status"] not in TERMINAL:
                    raise RuntimeError(f"Cancellation returned {canceled['status']}")
                print("Confirmed terminal status:", canceled["status"], flush=True)
            except Exception as error:
                details = error.read().decode(errors="replace") if isinstance(error, HTTPError) else str(error)
                (output / "cancellation-failed.json").write_text(json.dumps({
                    "id": prediction["id"], "error": details,
                    "stopped": False, "action": "Do not submit more predictions; resolve this request first.",
                }, indent=2))
                raise RuntimeError(
                    f"STOP NOT CONFIRMED for {prediction['id']}. No more predictions should be submitted. {details}"
                ) from error
    if prediction["status"] != "succeeded":
        raise RuntimeError(f"Prediction {prediction['status']}: {prediction.get('error')}")
    print("Succeeded. Outputs and peak-memory report URLs are in prediction.json.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--acknowledge-active-id", help="Explicitly acknowledged stuck prediction; other active requests still block testing")
    args = parser.parse_args()
    token = args.token_file.read_text().strip() if args.token_file else os.environ["REPLICATE_API_TOKEN"]
    run(args.version, token, args.out, acknowledged_active_id=args.acknowledge_active_id)
