# PSL Cricket Analytics and Fantasy Team Selector (PSL Dugout)

A Python project that scores Pakistan Super League players from past ball-by-ball records and selects the best
fantasy XI within a budget and team rules. K-means groups players by playing style. CSP backtracking with branch and
bound, a genetic algorithm and a greedy baseline select teams and are compared on the same seeded cases. A Streamlit
website shows everything.

AL-2002 Artificial Intelligence Lab, Fall 2026, FAST-NUCES Karachi. Idea #21.

## Members

| Member | Roll no. | Planned modules (proposal) | What they built |
|---|---|---|---|
| Mahad Awan (leader) | 24K-3014 | Data cleaning, EDA, scoring, K-means | To be completed by the member |
| Muhammad Basim Iftikhar | 24K-3044 | Constraints, backtracking, greedy, validation | To be completed by the member |
| Huzaifa Masood | 24K-3049 | GA, interface, experiment integration | To be completed by the member |

**AI assistance:** Claude Code (Anthropic) generated the code, tests, website, experiments and report draft from the
group's proposal and instructions. See "Use of AI Assistance" in `docs/report.pdf`.

## Setup

Needs Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run src/app.py           # website at http://localhost:8501
python src/run_experiments.py      # reproduces every table and chart in outputs/ (about 10 to 20 minutes)
python -m pytest                   # 52 tests
```

Run these from the project folder. The processed data is included, so no download is needed. Add `--quick` to the
experiments for a short run in `outputs/quick/`. To rebuild the data from Cricsheet, run `python src/prepare_data.py`
(`--offline` uses zips already in `data/raw/`).

## Features

- Build an XI with your own budget, role, overseas and team limits, and compare the three methods
- Player search and statistics, top performers by season, playing styles, experiment results
- Login required: sign up, stay logged in, saved teams, change password, delete account
- An info icon on every page that explains what it shows

## Local accounts

The site opens on a login screen. On first use, choose **Create account**; no email or internet is needed.
"Stay logged in" (on by default) keeps you logged in on that browser for 30 days. Accounts are kept in `data/local/accounts.db` on your
computer, which git ignores. Passwords are stored as salted scrypt hashes, and five wrong passwords lock an account
for five minutes. There is no password reset. To remove all accounts, stop the
app and delete that file. This is for local use, not for a public server.

## Layout

```
src/
  app.py, app_pages/, ui/, static/   website
  prepare_data.py                    download and process the data
  run_experiments.py                 all experiments with fixed seeds
  psl_selector/                      data, EDA, scoring, clustering, rules, accounts
  psl_selector/selectors/            backtracking, genetic, greedy
tests/                               pytest suite
data/processed/, data/metadata/      player tables; role and overseas evidence
outputs/figures/, outputs/results/   charts, tables and logs
docs/                                proposal and report (PDF and Markdown)
```

## Data

[Cricsheet](https://cricsheet.org/) PSL JSON, seasons 2022/23 to 2026: 143 matches, 131 players with at least 8 matches.
The men's T20I archive is used only for nationality. Cricsheet's terms apply; see https://cricsheet.org/.

## Known limitations

- Roles and overseas status are inferred from match records, with five corrections by hand
  (`data/metadata/manual_overrides.csv`).
- Credits are simulated. Values ignore batting order, venue and opposition, and do not predict future matches.
- Not for betting. Not affiliated with the Pakistan Super League.

The website font is Archivo (SIL Open Font License, `src/static/fonts/OFL.txt`).
