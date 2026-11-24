"""Central configuration: paths, seasons, scoring weights and default team rules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
METADATA_DIR = DATA_DIR / "metadata"
SAMPLE_DIR = DATA_DIR / "sample"
OUTPUTS_DIR = ROOT / "outputs"
RESULTS_DIR = OUTPUTS_DIR / "results"
FIGURES_DIR = OUTPUTS_DIR / "figures"

PSL_ZIP_URL = "https://cricsheet.org/downloads/psl_json.zip"
T20I_ZIP_URL = "https://cricsheet.org/downloads/t20s_male_json.zip"
PSL_ZIP = RAW_DIR / "psl_json.zip"
T20I_ZIP = RAW_DIR / "t20s_json.zip"

PLAYER_MATCH_CSV = PROCESSED_DIR / "player_match_stats.csv"
PLAYERS_CSV = PROCESSED_DIR / "players.csv"
METADATA_CSV = METADATA_DIR / "player_metadata.csv"
OVERRIDES_CSV = METADATA_DIR / "manual_overrides.csv"
SAMPLE_PLAYERS_CSV = SAMPLE_DIR / "players_sample.csv"

# Last four completed PSL seasons in the Cricsheet archive (PSL 8 - PSL 11).
SEASONS = ["2022/23", "2023/24", "2025", "2026"]
# Older seasons count for less when computing a player's value.
SEASON_WEIGHTS = {"2022/23": 0.6, "2023/24": 0.75, "2025": 0.9, "2026": 1.0}
MIN_MATCHES = 8          # eligibility threshold over the selected seasons
SHRINKAGE_MATCHES = 6    # Bayesian shrinkage strength toward the role mean

ROLES = ["WK", "BAT", "AR", "BOWL"]
ROLE_NAMES = {"WK": "Wicketkeeper", "BAT": "Batter", "AR": "All-rounder", "BOWL": "Bowler"}

# Default team rules (all adjustable in SelectionProblem / dashboard).
DEFAULT_RULES = {
    "team_size": 11,
    "budget": 100.0,
    "role_limits": {"WK": (1, 1), "BAT": (3, 5), "AR": (1, 3), "BOWL": (3, 5)},
    "max_overseas": 4,
}

# Simulated credits: value percentile mapped onto this range in 0.5 steps.
CREDIT_MIN, CREDIT_MAX = 6.0, 11.0

# GA defaults from the proposal.
GA_DEFAULTS = {"population_size": 100, "generations": 200, "mutation_rate": 0.10,
               "crossover_rate": 0.9, "tournament_size": 3, "elitism": 2}
TIME_LIMIT_S = 30.0
SEED = 42
