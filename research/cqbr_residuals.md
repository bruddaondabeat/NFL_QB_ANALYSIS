# cQBR residual EDA — what ESPN sees that public data can't

Generated 2026-08-23 · cQBR v1 vs official ESPN QBR · 215 qualified QB-seasons 2019–2025 · residual = cQBR − qbr_total (positive = cQBR over-rates vs ESPN).

MAE vs adjusted QBR (`qbr_total`): **3.94** · vs raw QBR (`qbr_raw`, pre-opponent-adjustment): **3.84**.

## What correlates with the disagreement

| Candidate explanation | r vs resid (total) | r vs resid (raw) |
|---|---|---|
| Sack rate (ESPN charges QB ~55%, EPA charges 100%) | -0.007 | +0.035 |
| aDOT / air yards per attempt (credit division: depth) | -0.152 | -0.153 |
| YAC share of passing yards (credit division: receivers) | +0.275 | +0.272 |
| Scramble + designed-run share of action plays | -0.187 | -0.201 |
| Fumble rate | +0.053 | +0.048 |
| ESPN's own opponent adjustment (qbr_total − qbr_raw) | -0.208 | +0.159 |

## Most over-rated by cQBR (ESPN sees less than EPA does)

```
           name  season  cqbr  qbr_total  resid  sack_rate  adot  yac_share
 Tua Tagovailoa    2025  51.0       37.5   13.5        7.3   6.8       53.0
     Cam Newton    2020  51.7       39.4   12.3        7.8   6.8       47.3
   Nick Mullens    2020  48.3       36.3   12.0        5.5   6.3       50.7
  Philip Rivers    2020  66.6       55.0   11.6        3.4   7.2       53.4
Jimmy Garoppolo    2022  67.8       56.3   11.5        5.5   6.9       59.2
     Joe Burrow    2020  58.8       48.5   10.3        7.4   8.6       42.5
Gardner Minshew    2020  53.9       44.0    9.9        7.6   7.8       45.0
Jacoby Brissett    2025  50.9       41.2    9.7        8.2   7.6       46.3
   Kirk Cousins    2020  65.4       55.8    9.6        7.1   8.0       45.4
 Tua Tagovailoa    2024  66.3       57.1    9.2        5.0   5.7       59.6
```

## Most under-rated by cQBR (ESPN sees more than EPA does)

```
            name  season  cqbr  qbr_total  resid  sack_rate  adot  yac_share
    Joshua Dobbs    2023  36.9       51.8  -14.9        6.7   8.0       40.7
Ryan Fitzpatrick    2019  56.2       68.3  -12.1        7.4   9.0       35.1
    Carson Wentz    2019  53.1       62.8   -9.7        5.8   8.1       44.7
  Justin Herbert    2023  54.5       64.1   -9.6        6.0   7.7       49.6
 Gardner Minshew    2023  50.1       59.6   -9.5        6.5   7.3       47.4
    Daniel Jones    2019  47.8       55.7   -7.9        7.6   8.0       45.9
Matthew Stafford    2024  53.6       61.5   -7.9        5.1   7.5       45.9
    Daniel Jones    2020  46.2       54.0   -7.8        9.2   7.6       37.9
  Russell Wilson    2021  53.1       60.6   -7.5        7.6   9.9       44.4
      Geno Smith    2022  55.5       62.8   -7.3        7.5   7.6       41.6
```

## Systematic per-player bias (3+ seasons, mean residual)

cQBR consistently UNDER-rates (ESPN likes them more):

```
                  seasons  bias  cqbr   qbr
name                                       
Carson Wentz            4  -5.3  44.7  49.9
Justin Herbert          6  -4.0  59.3  63.4
Matthew Stafford        7  -3.9  60.5  64.3
Russell Wilson          6  -3.4  52.7  56.1
Kyler Murray            6  -3.3  54.5  57.8
Lamar Jackson           7  -3.3  63.9  67.2
Daniel Jones            6  -2.7  51.8  54.6
Geno Smith              4  -2.6  49.1  51.7
```

cQBR consistently OVER-rates (EPA likes them more):

```
                 seasons  bias  cqbr   qbr
name                                      
Sam Darnold            5   2.7  48.7  46.0
Jared Goff             7   3.0  59.2  56.2
Joe Burrow             5   3.1  61.7  58.6
Kirk Cousins           6   3.5  59.7  56.2
Ryan Tannehill         4   3.7  66.1  62.4
Tua Tagovailoa         6   4.2  58.6  54.4
Aaron Rodgers          6   4.2  60.4  56.1
Jimmy Garoppolo        3   7.0  65.8  58.8
```

## v2 candidate experiment (LOSO, same protocol as fit_cqbr.py)

| Model | LOSO r | MAE | within 5 pts |
|---|---|---|---|
| x (v1: weighted EPA only) | 0.906 | 4.00 | 67% |
| x + yac_share | 0.912 | 3.90 | 68% |
| **x + yac_share + scramble_share** | **0.913** | **3.87** | 68% |
| x + yac_share + scramble_share + adot | 0.913 | 3.88 | 69% |

Adding the two credit-division proxies (YAC share, scramble/run share)
clears the promotion gate (MAE 3.87 < v1's 4.00). aDOT adds nothing once
YAC share is in. Recommended v2: three coefficients on
(weighted EPA/play, yac_share, scramble_share) — requires the pipeline
scorer to compute the two extra per-QB-season features.

## Reading the findings

1. **YAC share is the biggest public-data blind spot (r = +0.28 with the
   residual).** ESPN hands yards-after-catch beyond expectation to the
   receiver; EPA gives them all to the QB. The most over-rated list is a
   who's-who of YAC systems (Tua 53–60% YAC share, Garoppolo 59%), and
   the per-player bias table says the same thing across seasons.
2. **Dual-threat and deep-ball QBs are under-rated by pure EPA** —
   scramble/run share (r = −0.19) and aDOT (r = −0.15) both push the
   other way (Lamar, Kyler, Herbert, Stafford, Wilson biases −3 to −4).
3. **Sack rate is a null (r ≈ 0)** — ESPN's ~55% sack attribution does
   not create season-level bias vs qb_epa's 100% charge.
4. **The opponent-adjustment signature is exactly where theory says:**
   residual vs adjusted QBR correlates −0.21 with ESPN's own adjustment,
   flips to +0.16 vs raw QBR, and MAE is tighter against raw (3.84) than
   adjusted (3.94). A season-level opponent layer remains unnecessary;
   revisit at weekly grain.
