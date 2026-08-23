# Metric stability audit

Generated 2026-08-22 from nflverse play-by-play, seasons 2021–2025, qualified passers (≥150 attempts/season).

Year-over-year Pearson r for the same QB in consecutive seasons.
High r → the metric reflects a persistent trait; low r → mostly
situation and noise, so the dashboard presents it as a record,
not a prediction.

| Metric | YoY r | pairs |
|---|---|---|
| EPA per dropback | 0.405 | 117 |
| CPOE | 0.375 | 117 |
| Passer rating | 0.379 | 117 |
| Completion % | 0.390 | 117 |
| Yards / attempt | 0.371 | 117 |
| 3rd-down delta (cmp% 3rd - 1st) | -0.046 | 117 |
| Clutch cmp% (last 2:00, one-score) | 0.253 | 113 |
| 4th-down conversion rate | -0.011 | 92 |

## League-level 3rd-down decline by season

| Season | % of QBs declining | mean delta (pts) |
|---|---|---|
| 2021 | 89.5% | -7.38 |
| 2022 | 82.5% | -6.51 |
| 2023 | 85.7% | -6.83 |
| 2024 | 90.7% | -7.94 |
| 2025 | 90.5% | -7.28 |
