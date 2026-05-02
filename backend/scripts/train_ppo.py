from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rl.train_ppo import train_ppo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train CUDA PPO policy for microgrid dispatch.")
    parser.add_argument("--timesteps", type=int, default=80000)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(train_ppo(total_timesteps=args.timesteps), indent=2, default=str))

