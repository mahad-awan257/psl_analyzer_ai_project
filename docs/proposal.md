FAST - NATIONAL UNIVERSITY OF COMPUTER AND EMERGING SCIENCES

FAST School of Computing | Karachi Campus

# PROJECT PROPOSAL

Semester Lab Project | AL-2002 Artificial Intelligence | Fall 2026

## Group Information

| Name / Roll number | Section | Role in the project |
|---|---|---|
| Mahad Awan / 24K-3014 | A | Leader; data and analytics |
| Muhammad Basim Iftikhar / 24K-3044 | A | CSP and baseline |
| Huzaifa Masood / 24K-3049 | A | GA and interface |

| Project Title | PSL Cricket Analytics and Fantasy Team Selector |
|---|---|
| Project Idea / Category | Idea #21 \| Part B - Applied / Data \| High |
| GitHub Repository URL | To be added |
| Date of Submission | To be filled |

## 1. Project Title and Summary

We will build a Python app that studies PSL player records and selects an XI within a budget. K-means will group similar players. Backtracking and a genetic algorithm will choose teams. A simple dashboard will show player statistics, the selected XI and results.

## 2. Problem Statement and Motivation

Picking a strong XI is difficult when the budget and team rules must also be met. Choosing only famous players may create an expensive or unbalanced team. We will use past PSL records to score players and find suitable combinations. We will compare three selection methods to see how team score and speed differ.

## 3. Problem Formulation

### 3.1 PEAS Description

| Component | Description |
|---|---|
| Performance measure | High team value, valid composition and low runtime. |
| Environment | Historical PSL player pool, costs and selection rules. |
| Actuators | Select, remove or replace players; return an XI. |
| Sensors | Player statistics, roles, budget and selected-team counts. |

### 3.2 Environment and Agent Type

Fully observable, deterministic, static, discrete and single-agent. A utility-based agent chooses a team with a high score while following the rules.

### 3.3 Problem Representation

| Element | Representation |
|---|---|
| State / initial state | Selected players, cost and role counts; initially an empty team. |
| Variables and actions | Each player has x_i in {0,1}; select or exclude a player. |
| Goal / constraints | 11 unique players; cost <= budget; 1 wicketkeeper, 3-5 batters, 1-3 all-rounders, 3-5 bowlers; at most 4 overseas players. |
| Utility / fitness | Sum of role-normalized historical player values. Only feasible XIs are accepted. |

Team rules are adjustable. Roles are checked separately from clusters. Costs use simulated credits.

## 4. Proposed AI Approach

| Technique | Role / implementation |
|---|---|
| K-means | Player-profile discovery; scikit-learn library. |
| CSP backtracking | Own code; feasibility pruning, forward checking and MRV where applicable. |
| Genetic algorithm | Own code; selection, crossover, mutation, elitism and constraint repair. |
| Baseline: greedy | Own code; value-per-credit selection with feasibility checks. |

Backtracking will build a team step by step and reject choices that break the rules. The genetic algorithm will improve candidate teams through selection, crossover and mutation. Invalid teams will be repaired or rejected. All methods will use the same player scores and costs.

### 4.1 Planned Class Design

Player stores player details. PlayerDataset loads and cleans data. SelectionProblem checks team rules. TeamSelector is a base class with a select_team() method. BacktrackingSelector, GeneticSelector and GreedySelector inherit from it and override this method. ExperimentRunner compares results.

## 5. Scope

In scope: player statistics, clustering, scoring, team selection, a dashboard and comparisons. Out of scope: live scores, betting, paid APIs, deep learning and future-performance guarantees.

## 6. Data or Environment Source

| Field | Plan |
|---|---|
| Source name and URL | Cricsheet PSL JSON: https://cricsheet.org/downloads/psl_json.zip |
| Type / access | Public dataset; no API key. Target: 3-5 completed seasons, subject to coverage. |
| Approximate size | 100-180 matches; 60-120 eligible players after cleaning. |
| Metadata / costs | Verified role and overseas-status CSV with references; documented simulated credits. |
| Licence / terms | Follow https://cricsheet.org/licensing/ and retain attribution. |
| Offline fallback | Cache raw and processed files locally; provide a small sample and preparation instructions. |

## 7. Evaluation Plan

Test all methods on the same 20 player pools and budgets, including cases with no valid XI. Use seed 42 for test cases and seeds 42-51 for repeated GA runs. Compare team score, valid-team rate and runtime. Use small cases to find exact best teams and a 30-second limit for larger cases.

Charts: team score by method, runtime by pool size and GA score by generation. Start with 100 candidates, 200 generations and a 0.10 mutation rate. Check cluster quality using silhouette scores.

## 8. Division of Work

| Member | Modules / components owned | Share |
|---|---|---|
| Mahad Awan | Data cleaning, EDA, scoring and K-means; coordination. | 34% |
| Muhammad Basim Iftikhar | Constraints, backtracking, greedy and validation. | 33% |
| Huzaifa Masood | GA, dashboard and experiment integration. | 33% |

## 9. Milestones and Timeline

| Demonstrable milestone | Target | Owner |
|---|---|---|
| Validated dataset and player metadata | Proposal + 1 week | Mahad |
| EDA, profiles and scoring ready | Proposal + 2 weeks | Mahad |
| Backtracking and greedy return valid XIs | Proposal + 3 weeks | Basim |
| GA and dashboard integrated | Proposal + 4 weeks | Huzaifa |
| Experiments, report and clean-clone check | Week 15 | All |

## 10. Expected Outcome and Risks

The app will show player statistics and return a valid XI, or state that no team meets the rules. Missing data will be handled with a smaller verified player pool. Slow backtracking will be handled with pruning and time limits. Each member will write and document their own modules.
