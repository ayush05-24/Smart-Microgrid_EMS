from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.ml.lstm import TrainingConfig, train_all_forecasters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train GPU LSTM forecasters for solar and load.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--sequence-length", type=int, default=48)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = TrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        sequence_length=args.sequence_length,
    )
    print(json.dumps(train_all_forecasters(config), indent=2, default=str))

