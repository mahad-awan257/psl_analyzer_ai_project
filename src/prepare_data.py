"""Download (if needed) and process Cricsheet PSL data into data/processed/players.csv.

Usage:  python src/prepare_data.py [--offline] [--min-matches 8]
"""
import argparse
import sys
import urllib.error
import zipfile

from psl_selector import config as C
from psl_selector.dataset import PlayerDataset


def main() -> int:
    """Build the processed data. Returns a process exit code."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached zips in data/raw only")
    ap.add_argument("--min-matches", type=int, default=C.MIN_MATCHES)
    a = ap.parse_args()
    try:
        df = PlayerDataset.prepare(min_matches=a.min_matches, offline=a.offline)
    except FileNotFoundError as err:
        print(f"Missing file: {err}", file=sys.stderr)
        return 1
    except urllib.error.URLError as err:
        print(f"Download failed: {err.reason}. Check the internet connection, or use --offline.", file=sys.stderr)
        return 1
    except zipfile.BadZipFile:
        print("A file in data/raw is not a valid zip. Delete it and run this again.", file=sys.stderr)
        return 1
    print(df.groupby("role").size().to_string())
    print("overseas:", int(df.overseas.sum()))
    print(f"Wrote {C.PLAYERS_CSV}, {C.METADATA_CSV}, {C.SAMPLE_PLAYERS_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
