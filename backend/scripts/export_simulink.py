from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.exports import export_for_matlab
from backend.app.services.repository import recent_window


if __name__ == "__main__":
    df = recent_window(24 * 7)
    print(json.dumps(export_for_matlab(df, horizon_hours=24 * 7), indent=2))

