# Metric stability audit

Generated 2026-08-22 from nflverse play-by-play, seasons 2021–2025, qualified passers (≥150 attempts/season).

Year-over-year Pearson r for the same QB in consecutive seasons.
High r → the metric reflects a persistent trait; low r → mostly
situation and noise, so the dashboard presents it as a record,
not a prediction.

| Metric | YoY r | pairs |
|---|---|---|
| EPA per dropback | 0.451 | 117 |
| CPOE | 0.375 | 117 |
| Passer rating | 0.408 | 117 |
| Completion % | 0.535 | 117 |
| Yards / attempt | 0.391 | 117 |
| 3rd-down delta (cmp% 3rd - 1st) | -0.199 | 117 |
| Clutch cmp% (last 2:00, one-score) | 0.352 | 113 |
| 4th-down conversion rate | 0.100 | 97 |

## League-level 3rd-down decline by season

| Season | % of QBs declining | mean delta (pts) |
|---|---|---|
| 2021 | 89.5% | -9.81 |
| 2022 | 90.0% | -9.34 |
| 2023 | 86.0% | -9.57 |
| 2024 | 95.3% | -10.91 |
| 2025 | 95.2% | -10.07 |
