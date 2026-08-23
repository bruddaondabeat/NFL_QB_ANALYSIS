#!/usr/bin/env python3
"""Residual EDA: where does cQBR disagree with official ESPN QBR, and why?

cQBR (garbage-time-weighted EPA/play -> logistic) tracks official QBR at
r ~ 0.91 / MAE ~ 4. The residuals (cQBR - official) are the interesting
part: they point at what ESPN's proprietary layers (credit division by
pass depth/YAC, charted pressure, ~55% sack attribution, opponent
adjustment) see that public play-by-play cannot.

For each qualified QB-season (2019-2025) this script computes candidate
explanations and correlates them with the residual:

  sack_rate       sacks / dropbacks. ESPN charges the QB only ~55% of sack
                  value; qb_epa charges 100%. Predicts: high-sack QBs
                  UNDER-rated by cQBR (negative residual correlation... or
                  rather residual negative for high sack rate means cQBR
                  lower than ESPN).
  adot            mean air yards per attempt. ESPN credits deep throwers
                  more; cQBR should under-rate them.
  yac_share       share of passing yards after the catch. ESPN credits the
                  receiver for YAC beyond expectation; cQBR should
                  over-rate screen/YAC-dependent passers.
  scramble_share  share of action plays that are scrambles/designed runs.
  fumble_rate     fumbles per action play (ESPN's flat penalty differs
                  from EPA's context-dependent one).
  opp_adjust      ESPN's own opponent adjustment, qbr_total - qbr_raw.
                  cQBR has no opponent layer, so residuals vs qbr_total
                  should partially mirror this directly.

Outputs research/cqbr_residuals.md with correlations, the most over/
under-rated QB-seasons, and per-player systematic bias.
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
from fit_cqbr import (SEASONS, MIN_ACTION_PLAYS, cqbr_inputs, sigmoid)  # noqa: E402

EXTRA_COLS = ["play_id", "season", "season_type", "pass", "rush",
              "passer_player_id", "rusher_player_id", "qb_epa", "wp",
              "down", "qb_spike", "qb_kneel", "sack", "qb_scramble",
              "air_yards", "yards_after_catch", "passing_yards",
              "complete_pass", "fumble", "play_type"]


def load_action(years):
    import nflreadpy as nfl
    import polars as pl
    frames = []
    for y in years:
        print(f"loading pbp {y} ...", file=sys.stderr, flush=True)
        df = (nfl.load_pbp([y])
              .filter(((pl.col("pass") == 1) | (pl.col("rush") == 1))
                      & (pl.col("season_type") == "REG"))
              .select(EXTRA_COLS)
              .to_pandas())
        frames.append(df)
    d = pd.concat(frames, ignore_index=True)
    d = d[(d["qb_spike"] != 1) & (d["qb_kneel"] != 1)]
    d["qb_id"] = d["passer_player_id"].fillna(d["rusher_player_id"])
    return d.dropna(subset=["qb_id", "qb_epa", "wp", "down"])


def features(d):
    att = d[(d["play_type"] == "pass") & (d["sack"] != 1)
            & d["passer_player_id"].notna()]
    f = d.groupby(["qb_id", "season"]).agg(
        n=("play_id", "size"),
        sacks=("sack", "sum"),
        scrambles=("qb_scramble", "sum"),
        rushes=("rush", "sum"),
        fumbles=("fumble", "sum"),
    )
    a = att.groupby(["qb_id", "season"]).agg(
        adot=("air_yards", "mean"),
        yac=("yards_after_catch", "sum"),
        pyds=("passing_yards", "sum"),
        dropback_n=("play_id", "size"),
    )
    f = f.join(a)
    f["sack_rate"] = f["sacks"] / (f["dropback_n"] + f["sacks"]) * 100
    f["yac_share"] = f["yac"] / f["pyds"].where(f["pyds"] > 0) * 100
    f["scramble_share"] = (f["scrambles"] + f["rushes"]) / f["n"] * 100
    f["fumble_rate"] = f["fumbles"] / f["n"] * 100
    return f.reset_index()


def main():
    import json
    import nflreadpy as nfl

    spec = json.loads((ROOT / "research" / "metrics" / "cqbr_current.json").read_text())
    a, b = spec["coef"]["a"], spec["coef"]["b"]

    d = load_action(SEASONS)
    g = cqbr_inputs(d)
    g = g[g["n"] >= MIN_ACTION_PLAYS]
    g["cqbr"] = sigmoid(g["x"], a, b)

    qbr = pd.read_csv(ROOT / "research" / "data" / "qbr_official_season.csv")
    qbr = qbr[(qbr["season"].isin(SEASONS)) & (qbr["season_type"] == "Regular")
              & (qbr["qualified"] == True)]
    players = nfl.load_players().to_pandas()
    espn_to_gsis = (players.dropna(subset=["espn_id", "gsis_id"])
                    .astype({"espn_id": "int64"})
                    .set_index("espn_id")["gsis_id"].to_dict())
    gsis_to_name = (players.dropna(subset=["gsis_id"])
                    .set_index("gsis_id")["display_name"].to_dict())
    qbr["gsis_id"] = pd.to_numeric(qbr["player_id"], errors="coerce").map(espn_to_gsis)
    qbr = qbr.dropna(subset=["gsis_id"])

    m = g.merge(qbr[["gsis_id", "season", "qbr_total", "qbr_raw"]],
                left_on=["qb_id", "season"], right_on=["gsis_id", "season"])
    m = m.merge(features(d), on=["qb_id", "season"], how="left",
                suffixes=("", "_f"))
    m["name"] = m["qb_id"].map(gsis_to_name).fillna(m["qb_id"])
    m["resid"] = m["cqbr"] - m["qbr_total"]          # + = cQBR over-rates
    m["resid_raw"] = m["cqbr"] - m["qbr_raw"]        # vs pre-opponent-adj
    m["opp_adjust"] = m["qbr_total"] - m["qbr_raw"]  # ESPN's own adjustment
    print(f"{len(m)} QB-seasons | resid mean {m['resid'].mean():+.2f} "
          f"sd {m['resid'].std():.2f}", file=sys.stderr)

    cand = ["sack_rate", "adot", "yac_share", "scramble_share",
            "fumble_rate", "opp_adjust"]
    corr_total = {c: float(m[c].corr(m["resid"])) for c in cand}
    corr_raw = {c: float(m[c].corr(m["resid_raw"])) for c in cand}

    # residual vs raw QBR should be tighter (no opponent layer to miss)
    mae_total = float(m["resid"].abs().mean())
    mae_raw = float(m["resid_raw"].abs().mean())

    per_player = (m.groupby("name")
                  .agg(seasons=("season", "size"), bias=("resid", "mean"),
                       cqbr=("cqbr", "mean"), qbr=("qbr_total", "mean"))
                  .query("seasons >= 3").sort_values("bias"))

    over = m.nlargest(10, "resid")[["name", "season", "cqbr", "qbr_total", "resid",
                                    "sack_rate", "adot", "yac_share"]]
    under = m.nsmallest(10, "resid")[["name", "season", "cqbr", "qbr_total", "resid",
                                      "sack_rate", "adot", "yac_share"]]

    L = [
        "# cQBR residual EDA — what ESPN sees that public data can't",
        "",
        f"Generated {date.today().isoformat()} · cQBR v{spec['version']} vs official "
        f"ESPN QBR · {len(m)} qualified QB-seasons {min(SEASONS)}–{max(SEASONS)} · "
        f"residual = cQBR − qbr_total (positive = cQBR over-rates vs ESPN).",
        "",
        f"MAE vs adjusted QBR (`qbr_total`): **{mae_total:.2f}** · vs raw QBR "
        f"(`qbr_raw`, pre-opponent-adjustment): **{mae_raw:.2f}**.",
        "",
        "## What correlates with the disagreement",
        "",
        "| Candidate explanation | r vs resid (total) | r vs resid (raw) |",
        "|---|---|---|",
    ]
    labels = {
        "sack_rate": "Sack rate (ESPN charges QB ~55%, EPA charges 100%)",
        "adot": "aDOT / air yards per attempt (credit division: depth)",
        "yac_share": "YAC share of passing yards (credit division: receivers)",
        "scramble_share": "Scramble + designed-run share of action plays",
        "fumble_rate": "Fumble rate",
        "opp_adjust": "ESPN's own opponent adjustment (qbr_total − qbr_raw)",
    }
    for c in cand:
        L.append(f"| {labels[c]} | {corr_total[c]:+.3f} | {corr_raw[c]:+.3f} |")
    L += [
        "",
        "## Most over-rated by cQBR (ESPN sees less than EPA does)",
        "", "```", over.round(1).to_string(index=False), "```", "",
        "## Most under-rated by cQBR (ESPN sees more than EPA does)",
        "", "```", under.round(1).to_string(index=False), "```", "",
        "## Systematic per-player bias (3+ seasons, mean residual)",
        "",
        "cQBR consistently UNDER-rates (ESPN likes them more):",
        "", "```", per_player.head(8).round(1).to_string(), "```", "",
        "cQBR consistently OVER-rates (EPA likes them more):",
        "", "```", per_player.tail(8).round(1).to_string(), "```", "",
    ]
    (ROOT / "research" / "cqbr_residuals.md").write_text("\n".join(L) + "\n")
    m.to_csv(ROOT / "research" / "data" / "cqbr_residuals.csv", index=False)
    print("wrote research/cqbr_residuals.md (+ data csv)", file=sys.stderr)


if __name__ == "__main__":
    main()
