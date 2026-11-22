# PSL Cricket Analytics and Fantasy Team Selector

AL-2002 Artificial Intelligence, Semester Lab Project (Fall 2026), FAST-NUCES Karachi.
Idea #21, Part B (Applied / Data).

| Member | Roll no. | Owns |
|---|---|---|
| Mahad Awan (leader) | 24K-3014 | Data cleaning, EDA, scoring, K-means (`cricsheet.py`, `dataset.py`, `scoring.py`, `clustering.py`) |
| Muhammad Basim Iftikhar | 24K-3044 | Constraints, backtracking, greedy, validation (`problem.py`, `selectors/backtracking.py`, `selectors/greedy.py`, `tests/`) |
| Huzaifa Masood | 24K-3049 | GA, dashboard, experiments (`selectors/genetic.py`, `app.py`, `experiments.py`) |

The app takes historical PSL ball-by-ball data and scores every player. K-means groups players into
playing-style profiles. The app then picks the best fantasy XI under a budget and team rules, using three
methods: **CSP backtracking (branch and bound)**, a **genetic algorithm** and a **greedy baseline**.
A Streamlit dashboard shows the statistics, the profiles, the selected XI and the experiment results.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/prepare_data.py          # downloads Cricsheet zips, builds data/processed/players.csv
python -m pytest                        # 23 tests (includes brute-force optimality checks)
python scripts/run_experiments.py       # full evaluation -> results/ (about 15-20 min; --quick for a smoke run)
streamlit run app.py                    # dashboard at http://localhost:8501
```

Processed data is committed, so the dashboard and experiments work without downloading anything.
Without network access, put `psl_json.zip` and `t20s_json.zip` in `data/raw/` and run
`python scripts/prepare_data.py --offline`. If `players.csv` is missing, `PlayerDataset` falls back to
`data/sample/players_sample.csv`: the top 10 players per role, which is enough for a valid XI.

## Project layout

```
psl_selector/
  config.py            seasons, weights, default rules, GA parameters, paths
  cricsheet.py         JSON -> per player-match stats + fantasy points
  player.py            Player dataclass
  dataset.py           PlayerDataset: download, aggregate, role/overseas metadata, build pool
  scoring.py           role-normalized value + simulated credits
  clustering.py        K-means profiles, silhouette selection, PCA
  problem.py           SelectionProblem: constraints, utility, forward-checking feasibility test
  selectors/
    base.py            TeamSelector (select_team) + SelectionResult
    backtracking.py    BacktrackingSelector: CSP backtracking, MRV, forward checking, Lagrangian bound
    genetic.py         GeneticSelector: tournament, set crossover, swap mutation, elitism, repair
    greedy.py          GreedySelector: value-per-credit with feasibility checks
  experiments.py       ExperimentRunner: 20 cases, GA seeds 42-51, brute-force checks, charts
scripts/prepare_data.py, scripts/run_experiments.py
app.py                 Streamlit dashboard
tests/                 pytest suite
data/processed/        players.csv, player_match_stats.csv, silhouette_scores.csv
data/metadata/         player_metadata.csv (role + overseas with evidence), manual_overrides.csv
results/               experiment_results.csv, summary.csv, ga_history.csv, RESULTS.md, figures/
docs/REPORT.md         project report
```

## Data

* **Source:** [Cricsheet](https://cricsheet.org/) PSL JSON (`psl_json.zip`). The men's T20I archive
  (`t20s_male_json.zip`) is used only to work out nationality. The data is public and needs no API key.
  Use follows the [Cricsheet licence](https://cricsheet.org/licensing/); data is © Cricsheet.
* **Seasons:** 2022/23, 2023/24, 2025 and 2026 (PSL 8 to 11), which is **143 matches**. **268 players**
  appeared, and **131 are eligible** (8 or more matches): 12 WK, 48 BAT, 17 AR, 54 BOWL, 55 overseas.
* **Roles** come from playing evidence, recorded in `player_metadata.csv`:
  * **WK:** at least one PSL stumping and fewer than 0.5 overs bowled per match.
  * **BAT:** fewer than 1 over bowled per match.
  * **AR:** at least 1 over per match and at least 7 balls faced per match.
  * **BOWL:** everyone else.
* **Overseas:** a player is overseas if they played T20Is for a country other than Pakistan. Cricsheet's
  T20I archive has no Afghanistan matches, so Rashid Khan, Gurbaz, Nabi and Naveen-ul-Haq are set in
  `manual_overrides.csv`, along with the uncapped T Kohler-Cadmore. You can edit that file and re-run
  `prepare_data.py`.
* **Fantasy points** use a documented Dream11-like T20 scheme (`cricsheet.fantasy_points`): runs,
  boundaries, milestones, strike-rate and economy bonuses, wickets, maidens and fielding.

## Formulation

* **Variables:** x_i ∈ {0,1} for each player.
* **Constraints:** Σx_i = 11; Σc_i·x_i ≤ budget; 1 WK; 3–5 BAT; 1–3 AR; 3–5 BOWL; at most 4 overseas.
  Every rule can be changed in `SelectionProblem` and in the dashboard.
* **Utility:** Σ value_i·x_i, where `value` is computed as follows:
  1. Take fantasy points per match, weighted by season (0.6 for 2022/23 up to 1.0 for 2026).
  2. Shrink toward the role mean (strength: 6 matches).
  3. Z-score within the player's role and map to 50 + 15z, clipped to [5, 100].
* **Credits (simulated):** the overall percentile of raw points per match, mapped onto 6.0–11.0 in
  0.5 steps. Cost is role-agnostic and value is role-normalized, so value per credit varies from player
  to player.
* **Agent:** utility-based. The environment is fully observable, deterministic, static, discrete and
  single-agent.

## Methods

* **Backtracking** (`selectors/backtracking.py`): decides one player at a time, trying include before
  exclude.
  * **MRV:** while a role is below its minimum, branch on the role with the fewest spare candidates.
  * **Forward checking:** checks role minima and maxima, overseas, the slots left, and the cheapest
    possible completion against the remaining budget.
  * **Bound:** a Lagrangian relaxation of the budget. For λ ≥ 0, the best completion is at most
    λ·budget_left + max Σ(v_i − λc_i). The max is a prefix sum when players are sorted by v − λc, and λ is
    chosen once at the root to make the bound as tight as possible.
  * The search is exact, and tests confirm it against brute force. A 30 s limit returns the best XI so far.
* **Genetic algorithm** (`selectors/genetic.py`): each chromosome is a set of 11 players. It uses
  tournament selection (k=3), set crossover (keeps players common to both parents), and same-role swap
  mutation (rate 0.10 per gene) with elitism of 2. A repair step fixes role limits, size, overseas and
  budget, and the fitness function penalizes any team that is still invalid. Defaults: population 100,
  200 generations.
* **Greedy** (`selectors/greedy.py`): takes players in order of value per credit and keeps each one only
  if a valid XI can still be completed.

## Results

See `results/RESULTS.md` (generated) and `docs/REPORT.md`. At the default rules (budget 100), the
backtracking optimum is **739.5** (proven in about 0.01 s). The GA finds the same XI, and greedy reaches
710.2:

| # | Player | Role | Overseas | Credits | Value |
|---|---|---|---|---|---|
| 1 | Sarfraz Ahmed | WK | No | 6.0 | 32.3 |
| 2 | Babar Azam | BAT | No | 11.0 | 94.6 |
| 3 | Muhammad Naeem | BAT | No | 8.0 | 49.0 |
| 4 | PBB Rajapaksa | BAT | Yes | 7.0 | 44.1 |
| 5 | Omair Yousuf | BAT | No | 7.0 | 42.4 |
| 6 | DA Miller | BAT | Yes | 6.5 | 40.0 |
| 7 | Shadab Khan | AR | No | 11.0 | 94.5 |
| 8 | JO Holder | BOWL | Yes | 11.0 | 91.5 |
| 9 | Shaheen Shah Afridi | BOWL | No | 11.0 | 87.2 |
| 10 | Rashid Khan | BOWL | Yes | 11.0 | 86.1 |
| 11 | Hasan Ali | BOWL | No | 10.5 | 77.8 |

## Scope and limitations

**Out of scope:** live scores, betting, paid APIs, deep learning, and any guarantee of future performance.
The role and overseas labels come from data rules plus a short list of overrides, so spot-check them
before relying on them. Credits are simulated and are not official fantasy prices.
