#!/usr/bin/env python3
"""Year-over-year stability audit for every dashboard metric.

Question: when a QB posts a number in season N, how much does it tell you
about season N+1? Metrics with low year-over-year correlation are presented
on the dashboard as *descriptive* (a record of what happened), not
*predictive* (a skill ranking).

Pulls play-by-play one season at a time (bounded memory), computes the
dashboard's per-QB metrics per season, then correlates consecutive seasons
for the same QB across the full qualified population.

Outputs:
  research/data/qb_season_metrics.csv   per-QB per-season metric table
  research/stability_findings.md        human-readable audit report
  research/stability_findings.json      machine-readable YoY correlations
"""

import gc
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SEASONS = list(range(2021, 2026))

MIN_SEASON_ATTEMPTS = 150   # qualified passer for efficiency metrics
MIN_DOWN_ATTEMPTS = 20      # per-down floor for the 1st-vs-3rd split
MIN_CLUTCH_ATTEMPTS = 10    # audit floor (deliberately low, to measure noise)
MIN_FOURTH_ATTEMPTS = 5

CLUTCH_SECONDS = 120
CLUTCH_SCORE_BAND = (-8, 7)


def passer_rating(cmp_, att, yds, td, ints):
    att = np.asarray(att, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.clip((cmp_ / att - 0.3) * 5, 0, 2.375)
        b = np.clip((yds / att - 3) * 0.25, 0, 2.375)
        c = np.clip(td / att * 20, 0, 2.375)
        d = np.clip(2.375 - ints / att * 25, 0, 2.375)
    return (a + b + c + d) / 6 * 100


def season_metrics(season):
    """Per-QB metrics for one season under the official attempt rule
    (validated vs PFR in research/reconciliation_report.md): play_type in
    {pass, qb_spike} with a credited passer, minus 2pt plays and sacks."""
    import nflreadpy as nfl
    import polars as pl
    print(f"season {season}: loading pbp ...", file=sys.stderr, flush=True)
    p = (nfl.load_pbp([season])
         .filter(pl.col("play_type").is_in(["pass", "qb_spike"])
                 & pl.col("passer_player_id").is_not_null())
         .select(["play_id", "play_type", "passer_player_id",
                  "passer_player_name", "complete_pass", "passing_yards",
                  "pass_touchdown", "interception", "down", "qb_epa", "cpoe",
                  "half_seconds_remaining", "score_differential",
                  "first_down", "two_point_attempt", "sack"])
         .to_pandas())
    p = p[(p["two_point_attempt"] != 1) & (p["sack"] != 1)].copy()
    gc.collect()
    p["is_completion"] = p["complete_pass"].fillna(0)
    epa_col = "qb_epa"

    g = p.groupby("passer_player_id").agg(
        attempts=("play_id", "size"),
        completions=("is_completion", "sum"),
        yards=("passing_yards", "sum"),
        tds=("pass_touchdown", "sum"),
        ints=("interception", "sum"),
        epa_per_db=(epa_col, "mean"),
        cpoe=("cpoe", "mean"),
        name=("passer_player_name", "first"),
    )
    g = g[g["attempts"] >= MIN_SEASON_ATTEMPTS].copy()
    g["cmp_pct"] = g["completions"] / g["attempts"] * 100
    g["ypa"] = g["yards"].fillna(0) / g["attempts"]
    g["rating"] = passer_rating(g["completions"], g["attempts"],
                                g["yards"].fillna(0), g["tds"], g["ints"])

    def down_cmp(down):
        d = p[p["down"] == down].groupby("passer_player_id").agg(
            att=("play_id", "size"), cmp=("is_completion", "sum"))
        d = d[d["att"] >= MIN_DOWN_ATTEMPTS]
        return d["cmp"] / d["att"] * 100

    cmp1, cmp3 = down_cmp(1), down_cmp(3)
    g["third_down_delta"] = cmp3.reindex(g.index) - cmp1.reindex(g.index)

    lo, hi = CLUTCH_SCORE_BAND
    cl = p[(p["half_seconds_remaining"] <= CLUTCH_SECONDS)
           & p["score_differential"].between(lo, hi)]
    cg = cl.groupby("passer_player_id").agg(att=("play_id", "size"),
                                            cmp=("is_completion", "sum"))
    cg = cg[cg["att"] >= MIN_CLUTCH_ATTEMPTS]
    g["clutch_att"] = cg["att"].reindex(g.index)
    g["clutch_cmp_pct"] = (cg["cmp"] / cg["att"] * 100).reindex(g.index)

    f = p[p["down"] == 4].groupby("passer_player_id").agg(
        att=("play_id", "size"), conv=("first_down", "sum"))
    f = f[f["att"] >= MIN_FOURTH_ATTEMPTS]
    g["fourth_att"] = f["att"].reindex(g.index)
    g["fourth_rate"] = (f["conv"] / f["att"] * 100).reindex(g.index)

    g["season"] = season
    del p
    gc.collect()
    return g.reset_index().rename(columns={"passer_player_id": "player_id"})


def yoy(df, col):
    pairs = []
    for pid, grp in df.sort_values("season").groupby("player_id"):
        grp = grp.dropna(subset=[col])
        vals = list(zip(grp["season"], grp[col]))
        for (s1, v1), (s2, v2) in zip(vals, vals[1:]):
            if s2 == s1 + 1:
                pairs.append((v1, v2))
    if len(pairs) < 8:
        return None, len(pairs)
    a = pd.DataFrame(pairs, columns=["y1", "y2"])
    return float(a["y1"].corr(a["y2"])), len(pairs)


def main():
    frames = [season_metrics(s) for s in SEASONS]
    df = pd.concat(frames, ignore_index=True)
    (ROOT / "data").mkdir(exist_ok=True)
    df.to_csv(ROOT / "data" / "qb_season_metrics.csv", index=False)
    print(f"saved {len(df)} QB-seasons", file=sys.stderr)

    metrics = [
        ("epa_per_db", "EPA per dropback"),
        ("cpoe", "CPOE"),
        ("rating", "Passer rating"),
        ("cmp_pct", "Completion %"),
        ("ypa", "Yards / attempt"),
        ("third_down_delta", "3rd-down delta (cmp% 3rd - 1st)"),
        ("clutch_cmp_pct", "Clutch cmp% (last 2:00, one-score)"),
        ("fourth_rate", "4th-down conversion rate"),
    ]
    results = {}
    for col, label in metrics:
        r, n = yoy(df, col)
        results[col] = {"label": label, "yoy_r": r, "pairs": n}
        print(f"{label:38s} r = {r if r is None else round(r, 3)}  (n={n})",
              file=sys.stderr)

    league_decline = (
        df.dropna(subset=["third_down_delta"])
          .groupby("season")["third_down_delta"]
          .agg(share_declining=lambda s: float((s < 0).mean() * 100),
               mean_delta="mean")
    )

    payload = {
        "generated": date.today().isoformat(),
        "seasons": SEASONS,
        "qualification": {
            "season_attempts": MIN_SEASON_ATTEMPTS,
            "down_attempts": MIN_DOWN_ATTEMPTS,
            "clutch_attempts": MIN_CLUTCH_ATTEMPTS,
            "fourth_attempts": MIN_FOURTH_ATTEMPTS,
        },
        "yoy": results,
        "league_third_down": {
            int(k): {"share_declining": round(v["share_declining"], 1),
                     "mean_delta": round(v["mean_delta"], 2)}
            for k, v in league_decline.iterrows()
        },
    }
    (ROOT / "stability_findings.json").write_text(json.dumps(payload, indent=1))

    lines = [
        "# Metric stability audit",
        "",
        f"Generated {payload['generated']} from nflverse play-by-play, "
        f"seasons {SEASONS[0]}–{SEASONS[-1]}, qualified passers "
        f"(≥{MIN_SEASON_ATTEMPTS} attempts/season).",
        "",
        "Year-over-year Pearson r for the same QB in consecutive seasons.",
        "High r → the metric reflects a persistent trait; low r → mostly",
        "situation and noise, so the dashboard presents it as a record,",
        "not a prediction.",
        "",
        "| Metric | YoY r | pairs |",
        "|---|---|---|",
    ]
    for col, label in metrics:
        r = results[col]["yoy_r"]
        lines.append(f"| {label} | "
                     f"{'—' if r is None else format(r, '.3f')} | "
                     f"{results[col]['pairs']} |")
    lines += [
        "",
        "## League-level 3rd-down decline by season",
        "",
        "| Season | % of QBs declining | mean delta (pts) |",
        "|---|---|---|",
    ]
    for season, row in payload["league_third_down"].items():
        lines.append(f"| {season} | {row['share_declining']}% | "
                     f"{row['mean_delta']} |")
    (ROOT / "stability_findings.md").write_text("\n".join(lines) + "\n")
    print("wrote stability_findings.md / .json", file=sys.stderr)


if __name__ == "__main__":
    main()
