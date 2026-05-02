from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .config import ensure_project_dirs


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_preview(df: pd.DataFrame, path: Path, rows: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.head(rows).to_csv(path, index=False)


def bootstrap_paths() -> None:
    ensure_project_dirs()


def latest_records(df: pd.DataFrame, n: int) -> list[dict[str, Any]]:
    return df.tail(n).replace({pd.NA: None}).to_dict(orient="records")


def rounded_records(df: pd.DataFrame, digits: int = 3) -> list[dict[str, Any]]:
    output = df.copy()
    numeric_columns = output.select_dtypes(include="number").columns
    output[numeric_columns] = output[numeric_columns].round(digits)
    return output.replace({pd.NA: None}).to_dict(orient="records")
