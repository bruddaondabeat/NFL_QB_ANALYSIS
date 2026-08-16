# Extension Projects

Three self-contained projects that build on the core NFL QB Analysis. Each one
runs entirely from data already in this repository (no network calls), produces
an interactive HTML dashboard you can open locally or serve from GitHub Pages,
and exports a tidy CSV to `output/` for Tableau or further analysis.

| # | Project | Dashboard | Data export |
|---|---------|-----------|-------------|
| 1 | **QB Archetype Drift, 2021–2024** — the core project's KMeans archetype model refit across four seasons (including the previously unused 2024 PFR export), with a Sankey flow of every QB's movement between archetypes | [`qb-archetype-drift.html`](qb-archetype-drift.html) | `output/qb_archetypes_2021_2024.csv` |
| 2 | **QB Similarity Engine** — nine-feature style fingerprints for every qualifying 2019–2023 season, cosine-similarity "closest comps," and a PCA style map | [`qb-similarity-map.html`](qb-similarity-map.html) | `output/qb_season_comps_2019_2023.csv` |
| 3 | **2025 Contract Value Board** — current QB contracts parsed from `NFL Player Salary.txt`, joined to 2024 efficiency (ANY/A), scored as performance percentile minus cost percentile | [`qb-contract-value.html`](qb-contract-value.html) | `output/qb_contract_value_2025.csv` |

## Live pages (GitHub Pages)

- [QB Archetype Drift](https://bruddaondabeat.github.io/NFL_QB_ANALYSIS/extensions/qb-archetype-drift.html)
- [QB Similarity Engine](https://bruddaondabeat.github.io/NFL_QB_ANALYSIS/extensions/qb-similarity-map.html)
- [2025 Contract Value Board](https://bruddaondabeat.github.io/NFL_QB_ANALYSIS/extensions/qb-contract-value.html)

## Running the projects

```bash
pip install pandas numpy scikit-learn plotly
cd extensions
python archetype_drift.py
python qb_similarity.py
python contract_value.py
```

Each script regenerates its HTML page and CSV export in place.

## How the pieces fit

- `qb_data.py` — shared loaders. Notably, it repairs the PFR standard-passing
  CSVs in `Raw Data/` (their Player and Awards fields contain raw newlines, so
  logical rows span multiple physical lines) and parses the three-line-per-player
  layout of `NFL Player Salary.txt`.
- `page.py` — shared page scaffolding and a validated, colorblind-safe palette so
  all three dashboards read as one system.
- `assets/plotly.min.js` — a single local copy of Plotly shared by the three
  pages, so they work offline and on GitHub Pages without a CDN.

## Method notes

- **Archetype Drift** clusters on the original model's four axes (completion %,
  yards/attempt, TD rate, INT rate), standardized and pooled across 2021–2024 so
  all seasons share one cluster boundary. Qualifying threshold: 150 attempts.
- **Similarity Engine** fingerprints each season with completion %, Y/A, TD rate,
  INT rate, sack rate, EPA/dropback, air yards/attempt, rush yards/game, and
  rushing EPA/game, then ranks neighbors by cosine similarity.
- **Contract Value Board** uses ANY/A — adjusted net yards per attempt — as the
  single efficiency yardstick, and flags rookie-scale vs veteran deals. Contract
  teams are 2025 teams, which can differ from where a QB played in 2024.
