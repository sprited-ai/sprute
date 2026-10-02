"""Execute one hosted request; stdout/stderr are inherited for live Cog logs."""
import json
from pathlib import Path
import sys

from predict import Predictor


def main():
    request = Path(sys.argv[1]).resolve(strict=True)
    inputs = json.loads(request.read_text())
    predictor = Predictor()
    predictor.setup()
    predictor.output = request.parent
    predictor.run_pipeline(**inputs)


if __name__ == "__main__":
    main()
