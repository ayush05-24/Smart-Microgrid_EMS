from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.pipeline import run_data_and_control_pipeline


if __name__ == "__main__":
    result = run_data_and_control_pipeline()
    print(json.dumps(result, indent=2, default=str))

