"""Run the CMO Scientific Engine locally with stdlib only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cmo_scientific_engine import run_pipeline


def main() -> int:
    if len(sys.argv) != 3:
        print(
            json.dumps(
                {
                    "error": "usage",
                    "detail": "python scripts/run_cmo_pipeline.py <input_json> <output_json>",
                },
                indent=2,
            )
        )
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    payload = json.loads(input_path.read_text())
    result = run_pipeline(payload)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
