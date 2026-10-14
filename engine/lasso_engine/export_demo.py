"""Export the compact demo pack the services need at runtime.

    python -m lasso_engine.export_demo --data ../data/league --model ../data/model --out ../data/demo

The pack contains the held-out season's events (the "live" matches), the
public tables and the trained Gaffer. It never includes ``truth/``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from .training import TEST_SEASON


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/league")
    ap.add_argument("--model", default="../data/model")
    ap.add_argument("--out", default="../data/demo")
    args = ap.parse_args()
    data, model, out = Path(args.data), Path(args.model), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.read_parquet(data / "clubs.parquet").to_parquet(out / "clubs.parquet", index=False)
    players = pd.read_parquet(data / "players.parquet")
    players[players.season == TEST_SEASON].to_parquet(out / "players.parquet", index=False)
    matches = pd.read_parquet(data / "matches.parquet")
    matches.to_parquet(out / "matches.parquet", index=False)
    ev = pd.read_parquet(data / "events" / f"season={TEST_SEASON}.parquet")
    ev.to_parquet(out / "events.parquet", index=False, compression="zstd")
    for f in ("gaffer.json", "prematch.parquet"):
        shutil.copy(model / f, out / f)
    print("demo pack:", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
