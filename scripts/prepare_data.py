"""Download (if needed) and process Cricsheet PSL data into data/processed/players.csv.

Usage:  python scripts/prepare_data.py [--offline] [--min-matches 8]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from psl_selector import config as C  # noqa: E402
from psl_selector.dataset import PlayerDataset  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached zips in data/raw only")
    ap.add_argument("--min-matches", type=int, default=C.MIN_MATCHES)
    a = ap.parse_args()
    df = PlayerDataset.prepare(min_matches=a.min_matches, offline=a.offline)
    print(df.groupby("role").size().to_string())
    print("overseas:", int(df.overseas.sum()))
    print(f"Wrote {C.PLAYERS_CSV}, {C.METADATA_CSV}, {C.SAMPLE_PLAYERS_CSV}")
