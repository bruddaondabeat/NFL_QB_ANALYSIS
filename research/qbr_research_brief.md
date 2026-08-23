# QBR Research Brief — Methodology, Open Alternatives, and a Validated Recipe

*Prepared 2026-08-22 by a research agent for the Fourth & Data project. Companion
scripts: `qbr_validate.py` (aggregation + correlations), `qbr_model.py` (LOSO CV
across candidate specs), `qbr_final.py` (recommended formula + leaderboard check).*

## 1. How Total QBR actually works

**Origin and structure.** Total QBR was built by ESPN's Stats & Information Group
(Dean Oliver, Alok Pattani, Albert Larcada, Ben Alamar, Jeff Bennett) and launched
**August 5, 2011**, developed from analysis of ~60,000 NFL plays from 2008–2010
([Wikipedia](https://en.wikipedia.org/wiki/Total_quarterback_rating)). It is
fundamentally an **EPA-per-play metric with a division-of-credit layer and a
leverage weighting layer, then rescaled to 0–100**.

The documented pipeline has six stages
([Wikipedia](https://en.wikipedia.org/wiki/Total_quarterback_rating),
[ESPN explainer](https://www.espn.com/blog/statsinfo/post/_/id/123701/how-is-total-qbr-calculated-we-explain-our-quarterback-rating)):

1. Every QB "action play" — passes, scrambles, designed runs, sacks, fumbles,
   interceptions and returns, and defensive pass interference penalties — gets an
   EPA value. EPA context is down, yards to go, distance to end zone, and time
   remaining.
2. Difficulty adjustment by pass type, pass depth, and whether the QB was pressured.
3. **Division of credit**: on completed passes the EPA is split among QB, receivers,
   and offensive line based on how far the ball traveled in the air, what share of
   yards came after the catch versus *expected* YAC, and whether the QB was under
   pressure. "Deeper throws give a higher share of credit to the QB, while screen
   passes give relatively less credit to the QB and more to the receiver."
4. **Garbage-time down-weighting** of up to 30%, keyed on win probability at the snap.
5. Opponent adjustment (added later — see below).
6. Scaling to 0–100 with 50 as average.

The published formula skeleton is `RawQBR = g(AdjustedEPA / ActionPlays)`, where
`g()` is the scaling function. ESPN describes `g()` as "a fairly standard logistic
regression" ([ESPN explainer](https://www.espn.com/blog/statsinfo/print?id=123701)) —
this matters a lot for section 4.

**The clutch/leverage story has reversed.** The 2011 version *up-weighted* clutch
plays. ESPN dropped that: "Unlike the initial version of QBR released in 2011,
plays are no longer up-weighted for 'clutch situations,' but we felt it was
important to keep the down-weighting feature." So current QBR only *discounts*
low-leverage plays; it never rewards high-leverage ones. Any reconstruction that
up-weights clutch plays is reproducing the deprecated 2011 metric.

**Sack attribution** is roughly split: "a little more than half of the blame for
sacks is on the quarterback," rising to about 60% when the defense sends extra
rushers ([ESPN FAQ](https://www.espn.com/nfl/story/_/id/6909058/nfl-total-qbr-faq)).

**Major revisions.** Formula modifications occurred in 2012 and 2013. The biggest
documented change came in **2016**, when ESPN added opponent adjustment — a direct
reversal of the original design
([ESPN 2016](https://www.espn.com/nfl/story/_/id/17653521/how-total-qbr-calculated-explain-our-improved-qb-rating)).
That revision also created the **raw QBR vs. adjusted QBR** split still visible in
the data: "The new, adjusted QBR is now the number you'll find under the Total QBR
column... The unadjusted QBR is now called 'raw QBR'."

**Documented vs. proprietary.** Public: the component list, the conceptual
credit-division rules, the existence of garbage-time discounting and opponent
adjustment, and the 0–100 percentile interpretation ("a QBR of 80 means that the
QB's performance is better than 80% of the game performances by QBs since 2006").
Proprietary: **every actual coefficient**. ESPN's EP model, the credit-split
weights, the exact leverage weight function, the opponent-adjustment magnitude,
and the scaling function parameters have never been released.

One under-appreciated blocker for exact reproduction: QBR requires **manual video
charting** (pressure, drops vs. overthrows), with each game charted twice to
reconcile inconsistencies. Those inputs simply do not exist in free public
play-by-play, so an exact reconstruction is impossible in principle, not just in
practice.

## 2. Has anyone publicly reverse-engineered QBR?

Yes, though the work is thinner than expected, and the best example is on the
college side.

**The main artifact is [akeaswaran/cfb_qbr](https://github.com/akeaswaran/cfb_qbr).**
It contains two working models that estimate ESPN QBR from public play-by-play:
`qbr.R` fits a GAM (`mgcv::gam(label ~ s(qbr_epa))`) predicting **raw** QBR from a
single clutch-weighted EPA input; `qbr_xgb.R` fits an XGBoost model predicting
**opponent-adjusted** QBR from EPA split by play type.

The repo publishes concrete numeric choices ESPN never did:

```r
qbr_epa = if_else(EPA < -5.0, -5.0, EPA)          # floor catastrophic plays
qbr_epa = if_else(fumble_vec == 1, -3.5, qbr_epa) # flat fumble penalty
weight  = if_else(home_wp < .1 | home_wp > .9, .6, 1)
weight  = if_else((home_wp >= .1 & home_wp < .2) | (home_wp >= .8 & home_wp < .9), .9, weight)
```

That is a three-tier garbage-time discount — full credit in a normal game state,
0.9 in the 10–20%/80–90% WP bands, and 0.6 past 90/10. The 0.6 floor lines up
with ESPN's documented "up to 30%" discount language. **Caveat: fit on CFB data,
no stated NFL correlation — a recipe source, not a validated NFL result.**

**What does not exist:** no Open Source Football post reconstructing QBR, and no
peer-reviewed paper reverse-engineering it. The nflverse community's posture has
been to *mirror* ESPN's published QBR rather than rebuild it.

## 3. The closest open metrics

**dakota** — from the nflfastR source (`add_dakota()`): **not a linear EPA+CPOE
blend with published coefficients**. It is a **GAM loaded from a pre-fit binary**
(`dakota_model.Rdata`), inputs are `qb_epa` floored at −4.5 per play (mean) and
mean CPOE, min 5 attempts. Its purpose is *next-season prediction*, and its output
is on an EPA-per-play scale, not 0–100 — a poor drop-in for a QBR-like display
metric.

**EPA/play with WP leverage weighting** — fully computable from pbp (`qb_epa`,
`wp`). The single closest open analogue to QBR (see §4).

**ANY/A** — `(pass_yards + 20*TD − 45*INT − sack_yards) / (attempts + sacks)`.
Fully computable. nfelo found ANY/A and passer rating explain margin of victory
surprisingly well ([nfelo](https://www.nfeloapp.com/analysis/what-are-the-best-metrics-for-nfl-quarterbacks/)).

**nfelo QB model** — open source at
[greerreNFL/nfeloqb](https://github.com/greerreNFL/nfeloqb); continues 538's
discontinued QB Elo. Elo-scaled, not 0–100.

**PFF WAR** — proprietary. Useful public benchmark from the Sloan paper:
**year-to-year r: QBR 0.43, EPA 0.45, passer rating 0.37**
([Sloan](https://www.sloansportsconference.com/research-papers/pff-war-modeling-player-value-in-american-football)).

**Data note.** nflverse publishes official ESPN QBR directly — use the live
`espn_data` release (2006–2025, season & week level), not the stale espnscrapeR
CSVs (end at 2023):

```
https://github.com/nflverse/nflverse-data/releases/download/espn_data/qbr_season_level.csv
https://github.com/nflverse/nflverse-data/releases/download/espn_data/qbr_week_level.csv
```

Columns include `qbr_total`, `qbr_raw`, `qb_plays`, `epa_total`. Gotcha: the file
includes non-QBs who threw a pass — filter on `qb_plays` before joining names.

## 4. Concrete recommendation — validated

Candidates were built and cross-validated against official QBR on nflverse pbp,
2021–2024, 129 qualified QB-seasons (≥150 attempts):

| Candidate input | Pearson r | R² |
|---|---|---|
| Clutch-weighted EPA/play | **0.908** | 0.825 |
| Plain `qb_epa`/play | 0.902 | 0.814 |
| Success rate | 0.819 | 0.671 |
| ANY/A | 0.809 | 0.655 |
| CPOE | 0.579 | 0.335 |

Two findings: **adding CPOE to EPA buys essentially nothing** for matching QBR
(coefficient collapses to +0.046) — QBR is an EPA metric, not an accuracy metric.
**Season-level opponent adjustment also added nothing** (schedule strength washes
out over a season; revisit for weekly ratings).

**Recommended formula ("cQBR")** — a single clutch-weighted EPA input mapped
through a logistic function, mirroring ESPN's own documented `g()`:

```python
# 1. QB action plays: pass or rush, attributed to passer (else rusher)
# 2. Floor catastrophic plays at qb_epa >= -4.5 (nflfastR convention)
# 3. Garbage-time DOWN-weighting only (never up-weight):
#    weight 0.6 when wp < .10 or > .90; 0.9 in the .10-.20 / .80-.90 bands
# 4. x = weighted mean EPA per action play
# 5. cQBR = 100 / (1 + exp(-(-0.0871 + 3.6673 * x)))
```

**Leave-one-season-out validation** (coefficients never see the season they score):

- Pearson **r = 0.907** (R² = 0.822), Spearman **ρ = 0.892**
- **MAE = 3.84** QBR points, RMSE = 4.82
- **70%** of QB-seasons within 5 QBR points, **98%** within 10
- Mean absolute leaderboard rank difference: **3.3 places**
- 2024 sanity check: Josh Allen 74.5 / Lamar Jackson 74.3 vs official 74.8 / 74.8

**Warning:** percentile-rank scaling (the "obvious" transparent alternative) fails
badly on calibration — r stays 0.891 but **MAE explodes to 17.5** because ESPN's
percentile is over *game-level* performances since 2006, not the season's ~30
qualified QBs. Use the logistic map.

**Practical guidance.** Refit `a` and `b` on held QBR seasons and publish those two
numbers — that is the whole model. Call it something clearly distinct (cQBR,
"Composite QBR") and state plainly it approximates ESPN's metric (the charted
pressure/drop inputs and credit-division layer cannot be replicated). Keep
`qbr_raw` as a secondary validation target (it correlated slightly better,
r = 0.912, than `qbr_total`).

## Sources

- [ESPN — Total QBR: An explainer](https://www.espn.com/blog/statsinfo/post/_/id/123701/how-is-total-qbr-calculated-we-explain-our-quarterback-rating) ([print version](https://www.espn.com/blog/statsinfo/print?id=123701))
- [ESPN — Total QBR FAQ (2011)](https://www.espn.com/nfl/story/_/id/6909058/nfl-total-qbr-faq)
- [ESPN — How is Total QBR calculated? (2016 opponent adjustment)](https://www.espn.com/nfl/story/_/id/17653521/how-total-qbr-calculated-explain-our-improved-qb-rating)
- [Wikipedia — Total quarterback rating](https://en.wikipedia.org/wiki/Total_quarterback_rating)
- [GitHub — akeaswaran/cfb_qbr](https://github.com/akeaswaran/cfb_qbr)
- [GitHub — nflverse/espnscrapeR-data](https://github.com/nflverse/espnscrapeR-data)
- [GitHub — nflverse/nflverse-data, espn_data release](https://github.com/nflverse/nflverse-data/releases/tag/espn_data)
- [GitHub — nflverse/nflfastR, R/aggregate_game_stats.R (add_dakota)](https://github.com/nflverse/nflfastR/blob/master/R/aggregate_game_stats.R)
- [GitHub — greerreNFL/nfeloqb](https://github.com/greerreNFL/nfeloqb)
- [nfelo — What are the best metrics for NFL Quarterbacks](https://www.nfeloapp.com/analysis/what-are-the-best-metrics-for-nfl-quarterbacks/)
- [Open Source Football — nflfastR EP, WP, CP, xYAC, xPass models](https://opensourcefootball.com/posts/2020-09-28-nflfastr-ep-wp-and-cp-models/)
- [Open Source Football — Era Adjusted QB Elo](https://opensourcefootball.com/posts/2020-08-22-ranking-qbs-using-era-adjusted-elo/)
- [Sloan — PFF WAR: Modeling Player Value in American Football](https://www.sloansportsconference.com/research-papers/pff-war-modeling-player-value-in-american-football)
