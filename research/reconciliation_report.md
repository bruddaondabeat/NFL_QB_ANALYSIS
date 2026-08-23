# Official-stat reconciliation report

Generated 2026-08-22. Per-QB regular-season passing lines derived from nflverse play-by-play, diffed against Pro Football Reference standard passing tables (official numbers), QBs with 10+ official attempts.

Rule sets: **naive** = `play_type == 'pass'` with a credited passer; **official** = naive minus two-point conversion plays and sacks (official passing stats exclude both).

ESPN Total QBR is proprietary and out of scope; passer rating is the official formula and validated below.

## 2021

Filter diagnostics: 20064 pass/spike plays with a credited passer; of those 1244 sacks, 108 two-point plays, 67 spikes.

### Rule set: naive (play_type == pass) — matched 66 of 66 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 4.5% | 19.32 | 51 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 4.5% within ±0.1 | 5.540 | 13.18 |

### Rule set: official (+spikes, -2pt, -sacks) — matched 66 of 66 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 100.0% | 0.00 | 0 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 100.0% within ±0.1 | 0.025 | 0.05 |

Largest remaining attempt gaps:

```
         Player  Att_pfr  Att_pbp  Yds_pfr  Yds_pbp
      Tom Brady      719      719     5316   5316.0
 Justin Herbert      672      672     5014   5014.0
Patrick Mahomes      658      658     4839   4839.0
```

## 2022

Filter diagnostics: 19454 pass/spike plays with a credited passer; of those 1297 sacks, 88 two-point plays, 61 spikes.

### Rule set: naive (play_type == pass) — matched 73 of 73 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 4.1% | 17.95 | 59 |
| Yds | 98.6% | 0.01 | 1 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 4.1% within ±0.1 | 5.706 | 14.51 |

### Rule set: official (+spikes, -2pt, -sacks) — matched 73 of 73 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 100.0% | 0.00 | 0 |
| Yds | 98.6% | 0.01 | 1 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 98.6% within ±0.1 | 0.027 | 0.12 |

Largest remaining attempt gaps:

```
         Player  Att_pfr  Att_pbp  Yds_pfr  Yds_pbp
      Tom Brady      733      733     4694   4694.0
 Justin Herbert      699      699     4739   4739.0
Patrick Mahomes      648      648     5250   5250.0
```

## 2023

Filter diagnostics: 19802 pass/spike plays with a credited passer; of those 1410 sacks, 77 two-point plays, 67 spikes.

### Rule set: naive (play_type == pass) — matched 70 of 71 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 1.4% | 19.61 | 67 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 1.4% within ±0.1 | 6.126 | 16.51 |

### Rule set: official (+spikes, -2pt, -sacks) — matched 70 of 71 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 100.0% | 0.00 | 0 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 100.0% within ±0.1 | 0.026 | 0.05 |

Largest remaining attempt gaps:

```
         Player  Att_pfr  Att_pbp  Yds_pfr  Yds_pbp
     Sam Howell      612      612     3946   3946.0
     Jared Goff      605      605     4575   4575.0
Patrick Mahomes      597      597     4183   4183.0
```

## 2024

Filter diagnostics: 19224 pass/spike plays with a credited passer; of those 1314 sacks, 99 two-point plays, 71 spikes.

### Rule set: naive (play_type == pass) — matched 67 of 67 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 4.5% | 19.84 | 74 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 4.5% within ±0.1 | 6.001 | 17.56 |

### Rule set: official (+spikes, -2pt, -sacks) — matched 67 of 67 PFR QBs with 10+ attempts

| Stat | exact match | mean abs diff | max abs diff |
|---|---|---|---|
| Cmp | 100.0% | 0.00 | 0 |
| Att | 100.0% | 0.00 | 0 |
| Yds | 100.0% | 0.00 | 0 |
| TD | 100.0% | 0.00 | 0 |
| Int | 100.0% | 0.00 | 0 |
| Rate | 100.0% within ±0.1 | 0.024 | 0.05 |

Largest remaining attempt gaps:

```
         Player  Att_pfr  Att_pbp  Yds_pfr  Yds_pbp
     Joe Burrow      652      652     4918   4918.0
  Aaron Rodgers      584      584     3897   3897.0
Patrick Mahomes      581      581     3928   3928.0
```

