#!/usr/bin/env python3
"""Fit and validate cQBR — Fourth & Data's transparent QBR approximation.

This is the RESEARCH half of the metric architecture: it refits the two
logistic coefficients against official ESPN QBR, validates leave-one-season
-out, and writes a versioned spec to research/metrics/. The weekly data
pipeline only ever LOADS the promoted spec (cqbr_current.json) and scores —
it never refits, so the published metric stays stable until a new version
is deliberately promoted.

Recipe (see research/qbr_research_brief.md for provenance):
  action plays  = pass or rush plays credited to the QB (passer, else
                  rusher), excluding spikes and kneels; qb_epa and win
                  probability present
  epa           = qb_epa floored at -4.5 (nflfastR convention)
  weight        = 1.0 normally; 0.9 when pregame-snap WP is in the
                  10-20% / 80-90% bands; 0.6 past 90/10 (garbage-time
                  DOWN-weighting only — ESPN dropped clutch up-weighting)
  x             = weighted mean epa per action play (per QB-season)
  cQBR          = 100 / (1 + exp(-(a + b*x)))

Promotion gate: a new version replaces cqbr_current.json only if its
leave-one-season-out MAE beats the current version's recorded MAE.

Usage:
  python research/fit_cqbr.py                # fit on 2019-latest, validate
  python research/fit_cqbr.py --promote      # also write cqbr_current.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "research" / "metrics"
SEASONS = list(range(2019, 2026))
MIN_ACTION_PLAYS = 200          # qualified QB-season for fitting
EPA_FLOOR = -4.5
WP_WEIGHTS = {"extreme": 0.6, "band": 0.9}   # <10%/>90% ; 10-20%/80-90%

CQBR_COLS = ["play_id", "season", "season_type", "pass", "rush",
             "passer_player_id", "rusher_player_id", "qb_epa", "wp",
             "down", "qb_spike", "qb_kneel"]


def action_plays(years):
    """QB action plays for cQBR, one season at a time (bounded memory)."""
    import nflreadpy as nfl
    import polars as pl
    frames = []
    for y in years:
        print(f"loading pbp {y} ...", file=sys.stderr, flush=True)
        df = (nfl.load_pbp([y])
              .filter(((pl.col("pass") == 1) | (pl.col("rush") == 1))
                      & (pl.col("season_type") == "REG"))
              .select(CQBR_COLS)
              .to_pandas())
        frames.append(df)
    d = pd.concat(frames, ignore_index=True)
    d = d[(d["qb_spike"] != 1) & (d["qb_kneel"] != 1)]
    d["qb_id"] = d["passer_player_id"].fillna(d["rusher_player_id"])
    d = d.dropna(subset=["qb_id", "qb_epa", "wp", "down"])
    return d


def cqbr_inputs(d):
    """Per QB-season weighted EPA/play (the single model input)."""
    d = d.copy()
    d["epa_f"] = d["qb_epa"].clip(lower=EPA_FLOOR)
    w = np.ones(len(d))
    wp = d["wp"].to_numpy()
    w[(wp < 0.10) | (wp > 0.90)] = WP_WEIGHTS["extreme"]
    w[((wp >= 0.10) & (wp < 0.20)) | ((wp > 0.80) & (wp <= 0.90))] = WP_WEIGHTS["band"]
    d["w"] = w
    d["wepa"] = d["epa_f"] * d["w"]
    g = d.groupby(["qb_id", "season"]).agg(
        wepa=("wepa", "sum"), wsum=("w", "sum"), n=("play_id", "size"))
    g["x"] = g["wepa"] / g["wsum"]
    return g.reset_index()


def sigmoid(x, a, b):
    return 100.0 / (1.0 + np.exp(-(a + b * np.asarray(x, dtype=float))))


def fit(x, y):
    from scipy.optimize import curve_fit
    p, _ = curve_fit(sigmoid, x, y, p0=[0.0, 3.5], maxfev=10000)
    return float(p[0]), float(p[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()

    import nflreadpy as nfl
    import polars as pl

    # official QBR (season level) + espn_id -> gsis_id mapping
    qbr = pl.read_csv(
        "https://github.com/nflverse/nflverse-data/releases/download/"
        "espn_data/qbr_season_level.csv").to_pandas()
    qbr = qbr[(qbr["season"].isin(SEASONS))
              & (qbr["season_type"] == "Regular")
              & (qbr["qualified"] == True)]
    players = nfl.load_players().to_pandas()
    espn_to_gsis = (players.dropna(subset=["espn_id", "gsis_id"])
                    .astype({"espn_id": "int64"})
                    .set_index("espn_id")["gsis_id"].to_dict())
    qbr["gsis_id"] = pd.to_numeric(qbr["player_id"], errors="coerce") \
        .map(espn_to_gsis)
    qbr = qbr.dropna(subset=["gsis_id"])

    g = cqbr_inputs(action_plays(SEASONS))
    g = g[g["n"] >= MIN_ACTION_PLAYS]
    m = g.merge(qbr[["gsis_id", "season", "qbr_total", "qbr_raw"]],
                left_on=["qb_id", "season"], right_on=["gsis_id", "season"])
    print(f"fit set: {len(m)} QB-seasons "
          f"({m['season'].min()}-{m['season'].max()})", file=sys.stderr)

    # leave-one-season-out validation
    preds = []
    per_season = {}
    for s in sorted(m["season"].unique()):
        tr, te = m[m["season"] != s], m[m["season"] == s]
        a, b = fit(tr["x"], tr["qbr_total"])
        p = sigmoid(te["x"], a, b)
        err = p - te["qbr_total"].to_numpy()
        preds.append(pd.DataFrame({"season": s, "pred": p,
                                   "actual": te["qbr_total"].to_numpy()}))
        per_season[int(s)] = {"n": int(len(te)),
                              "mae": float(np.abs(err).mean()),
                              "r": float(np.corrcoef(p, te["qbr_total"])[0, 1])}
    pv = pd.concat(preds)
    loso_r = float(np.corrcoef(pv["pred"], pv["actual"])[0, 1])
    loso_mae = float((pv["pred"] - pv["actual"]).abs().mean())
    within5 = float(((pv["pred"] - pv["actual"]).abs() <= 5).mean() * 100)
    within10 = float(((pv["pred"] - pv["actual"]).abs() <= 10).mean() * 100)

    # final coefficients on all seasons
    a, b = fit(m["x"], m["qbr_total"])
    print(f"final fit a={a:.4f} b={b:.4f} | LOSO r={loso_r:.3f} "
          f"MAE={loso_mae:.2f} | within5={within5:.0f}% within10={within10:.0f}%",
          file=sys.stderr)

    METRICS.mkdir(parents=True, exist_ok=True)
    existing = sorted(METRICS.glob("cqbr_v*.json"))
    version = len(existing) + 1
    spec = {
        "metric": "cQBR",
        "version": version,
        "fitted": date.today().isoformat(),
        "train_seasons": [int(s) for s in sorted(m["season"].unique())],
        "n_qb_seasons": int(len(m)),
        "coef": {"a": round(a, 4), "b": round(b, 4)},
        "epa_floor": EPA_FLOOR,
        "wp_weights": WP_WEIGHTS,
        "min_action_plays": MIN_ACTION_PLAYS,
        "validation": {
            "method": "leave-one-season-out",
            "target": "official ESPN qbr_total (nflverse espn_data)",
            "r": round(loso_r, 4), "mae": round(loso_mae, 3),
            "within_5pts_pct": round(within5, 1),
            "within_10pts_pct": round(within10, 1),
            "per_season": per_season,
        },
        "notes": "Transparent approximation of ESPN Total QBR. Cannot "
                 "replicate ESPN's charted inputs (pressure, drops) or "
                 "credit-division layer; see research/qbr_research_brief.md.",
    }
    vpath = METRICS / f"cqbr_v{version}.json"
    vpath.write_text(json.dumps(spec, indent=1))
    print(f"wrote {vpath}", file=sys.stderr)

    current = METRICS / "cqbr_current.json"
    if args.promote:
        if current.exists():
            prev = json.loads(current.read_text())
            if spec["validation"]["mae"] > prev["validation"]["mae"]:
                print(f"PROMOTION BLOCKED: candidate MAE "
                      f"{spec['validation']['mae']} worse than current "
                      f"v{prev['version']} MAE {prev['validation']['mae']}",
                      file=sys.stderr)
                sys.exit(1)
        current.write_text(json.dumps(spec, indent=1))
        print(f"promoted v{version} -> {current}", file=sys.stderr)
    else:
        print("dry run (no --promote); cqbr_current.json unchanged",
              file=sys.stderr)


if __name__ == "__main__":
    main()
