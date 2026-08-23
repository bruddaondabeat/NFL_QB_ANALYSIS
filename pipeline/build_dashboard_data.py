#!/usr/bin/env python3
"""Build the data payload for the QB dashboard (dashboard/index.html).

Two modes:

  --from-exports   Offline. Reshapes the committed tableau_exports/*.csv
                   (2019-2023 baseline; situational splits for 2023 only)
                   into the dashboard payload.

  --live           Pulls play-by-play from nflverse via nflreadpy and
                   recomputes every benchmark for EVERY season in range:
                   per-season situational splits + KPIs, window-pooled
                   KMeans archetypes, and seasonal trajectories. This is
                   what the weekly GitHub Actions cron runs.

Payload schema (v2, season-aware):
  meta                    window, seasons, situational_seasons, latest,
                          latest_week, thresholds
  kpis_window             league rating / elite count over the full window
  kpis_by_season          {season: situational KPIs}
  situational_by_season   {season: [per-QB splits + shrunk rates]}
  archetypes              window-pooled KMeans clusters
  league_avg_by_season    qualified-passer league average rating
  players                 top-N trajectories (rating, EPA by season)

Both modes end by injecting the JSON into dashboard/index.html between the
<script id="qb-data" type="application/json"> ... </script> tags.

Usage:
  python pipeline/build_dashboard_data.py --from-exports
  python pipeline/build_dashboard_data.py --live --seasons 2019 2026
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "tableau_exports"
OUT_JSON = ROOT / "dashboard" / "data" / "qb_data.json"
DASHBOARD_HTML = ROOT / "dashboard" / "index.html"

# Benchmark thresholds — hardened after the 2026-08 stability audit
# (see research/stability_findings.md): small samples were allowed to
# headline leaderboards, so floors went up and rate leaderboards carry
# empirical-Bayes shrunk estimates.
MIN_ARCHETYPE_ATTEMPTS = 200   # window attempts to enter the KMeans model
MIN_DOWN_ATTEMPTS = 20         # attempts on a given down for the 1st-vs-3rd split
MIN_CLUTCH_ATTEMPTS = 20       # attempts inside the clutch window to be ranked
MIN_FOURTH_ATTEMPTS = 5        # 4th-down attempts to be ranked
SHRINK_K_CLUTCH = 20           # prior strength (pseudo-attempts) for clutch cmp%
SHRINK_K_FOURTH = 15           # prior strength for 4th-down conversion rate
CLUTCH_SECONDS = 120           # last two minutes of a half
CLUTCH_SCORE_BAND = (-8, 7)    # one-score game
TS_TOP_N = 20                  # trajectory panel: top N by window passing yards
MIN_SEASON_ATTEMPTS = 100      # per-season attempts to count toward league avg

PBP_COLS = [
    "play_id", "game_id", "week", "season", "season_type", "play_type",
    "passer_player_id", "passer_player_name", "complete_pass",
    "passing_yards", "pass_touchdown", "interception", "down", "qb_epa",
    "cpoe", "half_seconds_remaining", "score_differential", "first_down",
]


def passer_rating(cmp_, att, yds, td, ints):
    """Official NFL passer rating."""
    att = np.asarray(att, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.clip((cmp_ / att - 0.3) * 5, 0, 2.375)
        b = np.clip((yds / att - 3) * 0.25, 0, 2.375)
        c = np.clip(td / att * 20, 0, 2.375)
        d = np.clip(2.375 - ints / att * 25, 0, 2.375)
    return (a + b + c + d) / 6 * 100


def shrink(rate_pct, n, prior_pct, k):
    """Empirical-Bayes: pull a small-sample rate toward the league rate.
    A 12-attempt 80% should not outrank a 40-attempt 65%."""
    bad = lambda v: v is None or (isinstance(v, float) and np.isnan(v))
    if bad(rate_pct) or bad(n) or n <= 0:
        return np.nan
    return (rate_pct / 100 * n + prior_pct / 100 * k) / (n + k) * 100


def round_rec(obj, nd=4):
    if isinstance(obj, dict):
        return {k: round_rec(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_rec(v, nd) for v in obj]
    if isinstance(obj, float):
        if np.isnan(obj):
            return None
        return round(obj, nd)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round_rec(float(obj), nd)
    return obj


# ---------------------------------------------------------------------------
# Mode 1: reshape the committed exports (offline baseline)
# ---------------------------------------------------------------------------

def build_from_exports():
    master = pd.read_csv(EXPORTS / "qb_master_analytics_2019_2023.csv")
    arch = pd.read_csv(EXPORTS / "qb_archetypes_2019_2023.csv")
    ts = pd.read_csv(EXPORTS / "qb_time_series_2019_2023.csv")

    names = arch.set_index("player_id")["display_name"].to_dict()
    master["name"] = master["gsis_id"].map(names).fillna(
        master["passer_name"].str.replace(".", ". ", n=1, regex=False)
    )

    archetypes = [
        {
            "name": r.display_name,
            "id": r.player_id,
            "archetype": r.archetype,
            "cmp_pct": r.completion_pct * 100,
            "ypa": r.yards_per_attempt,
            "td_rate": r.td_rate * 100,
            "int_rate": r.int_rate * 100,
            "rating": r.passer_rating,
            "attempts": int(r.attempts),
        }
        for r in arch.itertuples()
    ]

    situational = []
    for r in master.itertuples():
        situational.append({
            "name": r.name,
            "id": r.gsis_id,
            "archetype": r.archetype if isinstance(r.archetype, str) else None,
            "attempts": int(r.attempts),
            "yards": r.passing_yards,
            "tds": int(r.touchdowns),
            "ints": int(r.interceptions),
            "cmp1": r.completion_pct_1,
            "cmp3": r.completion_pct_3,
            "delta": r.cmp_pct_delta,
            "clutch_att": r.clutch_attempts,
            "clutch_cmp_pct": r.clutch_cmp_pct,
            "clutch_ypa": r.clutch_ypa,
            "clutch_tds": r.clutch_tds,
            "clutch_ints": r.clutch_ints,
            "fourth_att": r.fourth_down_attempts,
            "fourth_conv": r.fourth_down_conversions,
            "fourth_rate": r.fourth_down_conversion_rate,
        })

    league_by_season = (
        ts[ts["attempts"] >= MIN_SEASON_ATTEMPTS]
        .groupby("season")["passer_rating"].mean()
    )
    players = []
    for name, g in ts.sort_values("season").groupby("display_name"):
        players.append({
            "name": name,
            "id": g["player_id"].iloc[0],
            "seasons": [
                {
                    "season": int(r.season),
                    "rating": r.passer_rating,
                    "epa": r.passing_epa,
                    "yards": r.passing_yards,
                    "tds": int(r.passing_tds),
                    "ints": int(r.interceptions),
                    "games": int(r.games),
                }
                for r in g.itertuples()
            ],
        })

    # exports carry situational splits for the 2023 season only
    return assemble(archetypes, {"2023": situational}, players,
                    league_by_season, window="2019–2023", live=False,
                    latest=2023, latest_week=None)


# ---------------------------------------------------------------------------
# Mode 2: live nflverse pull via nflreadpy (weekly cron)
# ---------------------------------------------------------------------------

def load_passes(years):
    """Pass plays for all seasons, one season at a time, slimmed to the
    columns we use — keeps memory flat regardless of window size."""
    import nflreadpy as nfl
    import polars as pl

    frames = []
    for y in years:
        print(f"loading pbp {y} ...", file=sys.stderr, flush=True)
        df = (
            nfl.load_pbp([y])
            .filter((pl.col("play_type") == "pass")
                    & pl.col("passer_player_id").is_not_null())
            .select(PBP_COLS)
            .to_pandas()
        )
        frames.append(df)
    passes = pd.concat(frames, ignore_index=True)
    passes["is_completion"] = passes["complete_pass"].fillna(0)
    return passes


def season_situational(latest, arch_map, id_to_name):
    """Per-QB situational splits for one season's pass plays."""
    def down_cmp(down):
        d = latest[latest["down"] == down].groupby("passer_player_id").agg(
            att=("play_id", "size"), cmp=("is_completion", "sum"))
        d = d[d["att"] >= MIN_DOWN_ATTEMPTS]
        return d["cmp"] / d["att"] * 100

    cmp1, cmp3 = down_cmp(1), down_cmp(3)

    lo, hi = CLUTCH_SCORE_BAND
    clutch = latest[
        (latest["half_seconds_remaining"] <= CLUTCH_SECONDS)
        & latest["score_differential"].between(lo, hi)
    ].groupby("passer_player_id").agg(
        att=("play_id", "size"), cmp=("is_completion", "sum"),
        yds=("passing_yards", "sum"), tds=("pass_touchdown", "sum"),
        ints=("interception", "sum"))

    fourth = latest[latest["down"] == 4].groupby("passer_player_id").agg(
        att=("play_id", "size"), conv=("first_down", "sum"))

    season_tot = latest.groupby("passer_player_id").agg(
        attempts=("play_id", "size"), yards=("passing_yards", "sum"),
        tds=("pass_touchdown", "sum"), ints=("interception", "sum"))
    season_tot = season_tot[season_tot["attempts"] >= MIN_DOWN_ATTEMPTS]

    rows = []
    for pid, r in season_tot.iterrows():
        c = clutch.loc[pid] if pid in clutch.index else None
        f = fourth.loc[pid] if pid in fourth.index else None
        rows.append({
            "name": id_to_name.get(pid, pid),
            "id": pid,
            "archetype": arch_map.get(pid),
            "attempts": int(r["attempts"]),
            "yards": float(r["yards"] or 0),
            "tds": int(r["tds"]),
            "ints": int(r["ints"]),
            "cmp1": cmp1.get(pid, np.nan),
            "cmp3": cmp3.get(pid, np.nan),
            "delta": cmp3.get(pid, np.nan) - cmp1.get(pid, np.nan),
            "clutch_att": float(c["att"]) if c is not None else np.nan,
            "clutch_cmp_pct": float(c["cmp"] / c["att"] * 100) if c is not None else np.nan,
            "clutch_ypa": float((c["yds"] or 0) / c["att"]) if c is not None else np.nan,
            "clutch_tds": float(c["tds"]) if c is not None else np.nan,
            "clutch_ints": float(c["ints"]) if c is not None else np.nan,
            "fourth_att": float(f["att"]) if f is not None else np.nan,
            "fourth_conv": float(f["conv"]) if f is not None else np.nan,
            "fourth_rate": float(f["conv"] / f["att"] * 100) if f is not None else np.nan,
        })
    return rows


def build_live(seasons):
    import nflreadpy as nfl

    years = list(range(seasons[0], seasons[1] + 1))
    window = f"{years[0]}–{years[-1]}"
    passes = load_passes(years)

    players_tbl = nfl.load_players().to_pandas()
    id_to_name = (players_tbl.dropna(subset=["gsis_id"])
                  .set_index("gsis_id")["display_name"].to_dict())

    # --- Archetype model inputs: window rate stats per passer ---------------
    g = passes.groupby("passer_player_id").agg(
        attempts=("play_id", "size"),
        completions=("is_completion", "sum"),
        yards=("passing_yards", "sum"),
        tds=("pass_touchdown", "sum"),
        ints=("interception", "sum"),
        epa_per_db=("qb_epa", "mean"),
        cpoe=("cpoe", "mean"),
    )
    g = g[g["attempts"] >= MIN_ARCHETYPE_ATTEMPTS]
    g["cmp_pct"] = g["completions"] / g["attempts"] * 100
    g["ypa"] = g["yards"].fillna(0) / g["attempts"]
    g["td_rate"] = g["tds"] / g["attempts"] * 100
    g["int_rate"] = g["ints"] / g["attempts"] * 100
    g["rating"] = passer_rating(g["completions"], g["attempts"],
                                g["yards"].fillna(0), g["tds"], g["ints"])

    # --- KMeans archetypes (3 clusters, labeled by mean rating) -------------
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    feats = g[["cmp_pct", "ypa", "td_rate", "int_rate"]]
    X = StandardScaler().fit_transform(feats)
    g["cluster"] = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(X)
    order = g.groupby("cluster")["rating"].mean().sort_values(ascending=False)
    labels = ["Elite Quarterbacks", "The League Core", "Struggling & Backups"]
    cluster_names = {c: labels[i] for i, c in enumerate(order.index)}
    g["archetype"] = g["cluster"].map(cluster_names)
    g["name"] = g.index.to_series().map(id_to_name).fillna(g.index.to_series())

    archetypes = [
        {"name": r.name, "id": r.Index, "archetype": r.archetype,
         "cmp_pct": r.cmp_pct, "ypa": r.ypa, "td_rate": r.td_rate,
         "int_rate": r.int_rate, "rating": r.rating, "attempts": int(r.attempts),
         "epa_per_db": r.epa_per_db, "cpoe": r.cpoe}
        for r in g.itertuples()
    ]
    arch_map = g["archetype"].to_dict()

    # --- Situational benchmarks: every season in the window -----------------
    situational_by_season = {}
    for y in years:
        rows = season_situational(passes[passes["season"] == y],
                                  arch_map, id_to_name)
        if rows:
            situational_by_season[str(y)] = rows
        print(f"situational {y}: {len(rows)} QBs", file=sys.stderr)

    # --- Trajectories: seasonal passer rating vs league average -------------
    reg = passes[passes["season_type"] == "REG"]
    seas = reg.groupby(["passer_player_id", "season"]).agg(
        completions=("is_completion", "sum"),
        attempts=("play_id", "size"),
        passing_yards=("passing_yards", "sum"),
        passing_tds=("pass_touchdown", "sum"),
        interceptions=("interception", "sum"),
        passing_epa=("qb_epa", "sum"),
        games=("game_id", "nunique"),
    ).reset_index().rename(columns={"passer_player_id": "player_id"})
    seas = seas[seas["attempts"] >= MIN_SEASON_ATTEMPTS].copy()
    seas["passing_yards"] = seas["passing_yards"].fillna(0)
    seas["rating"] = passer_rating(seas["completions"], seas["attempts"],
                                   seas["passing_yards"], seas["passing_tds"],
                                   seas["interceptions"])
    league_by_season = seas.groupby("season")["rating"].mean()

    top_ids = (seas.groupby("player_id")["passing_yards"].sum()
               .nlargest(TS_TOP_N).index)
    players = []
    for pid in top_ids:
        gp = seas[seas["player_id"] == pid].sort_values("season")
        players.append({
            "name": id_to_name.get(pid, pid),
            "id": pid,
            "seasons": [
                {"season": int(r.season), "rating": r.rating,
                 "epa": r.passing_epa, "yards": r.passing_yards,
                 "tds": int(r.passing_tds), "ints": int(r.interceptions),
                 "games": int(r.games)}
                for r in gp.itertuples()
            ],
        })

    latest = int(passes["season"].max())
    latest_week = int(passes.loc[passes["season"] == latest, "week"].max())
    return assemble(archetypes, situational_by_season, players,
                    league_by_season, window=window, live=True,
                    latest=latest, latest_week=latest_week)


# ---------------------------------------------------------------------------
# Shared: per-season KPIs + shrinkage, assembly, injection
# ---------------------------------------------------------------------------

def season_kpis(situational):
    """Situational KPIs + shrunk rates for one season (mutates rows)."""
    sit = pd.DataFrame(situational)

    cl = sit[(sit["clutch_att"].notna()) & (sit["clutch_att"] > 0)]
    prior_clutch = float((cl["clutch_cmp_pct"] / 100 * cl["clutch_att"]).sum()
                         / cl["clutch_att"].sum() * 100) if len(cl) else 60.0
    fo = sit[(sit["fourth_att"].notna()) & (sit["fourth_att"] > 0)]
    prior_fourth = float((fo["fourth_rate"] / 100 * fo["fourth_att"]).sum()
                         / fo["fourth_att"].sum() * 100) if len(fo) else 45.0
    for row in situational:
        row["clutch_cmp_adj"] = shrink(row.get("clutch_cmp_pct"),
                                       row.get("clutch_att"),
                                       prior_clutch, SHRINK_K_CLUTCH)
        row["fourth_rate_adj"] = shrink(row.get("fourth_rate"),
                                        row.get("fourth_att"),
                                        prior_fourth, SHRINK_K_FOURTH)
    sit = pd.DataFrame(situational)

    deltas = sit["delta"].dropna()
    clutch_ranked = sit[sit["clutch_att"] >= MIN_CLUTCH_ATTEMPTS] \
        .sort_values("clutch_cmp_adj", ascending=False)
    fourth_ranked = sit[sit["fourth_att"] >= MIN_FOURTH_ATTEMPTS]

    return {
        "avg_third_down_delta": float(deltas.mean()) if len(deltas) else None,
        "pct_declining_on_third": float((deltas < 0).mean() * 100) if len(deltas) else None,
        "clutch_leader": clutch_ranked.iloc[0]["name"] if len(clutch_ranked) else None,
        "clutch_leader_pct": float(clutch_ranked.iloc[0]["clutch_cmp_pct"]) if len(clutch_ranked) else None,
        "clutch_leader_adj": float(clutch_ranked.iloc[0]["clutch_cmp_adj"]) if len(clutch_ranked) else None,
        "clutch_league_rate": prior_clutch,
        "fourth_down_league_rate": float(
            fourth_ranked["fourth_conv"].sum() / fourth_ranked["fourth_att"].sum() * 100
        ) if len(fourth_ranked) else None,
    }


def assemble(archetypes, situational_by_season, players, league_by_season,
             window, live, latest, latest_week):
    # qualification floor applies in both modes (exports CSVs predate it)
    archetypes = [a for a in archetypes if a["attempts"] >= MIN_ARCHETYPE_ATTEMPTS]
    arch = pd.DataFrame(archetypes)

    kpis_by_season = {s: season_kpis(rows)
                      for s, rows in situational_by_season.items()}

    payload = {
        "meta": {
            "updated": date.today().isoformat(),
            "window": window,
            "source": "nflverse via nflreadpy",
            "mode": "live" if live else "baseline-exports",
            "latest": int(latest),
            "latest_week": latest_week,
            "situational_seasons": sorted(situational_by_season.keys()),
            "thresholds": {
                "archetype_attempts": MIN_ARCHETYPE_ATTEMPTS,
                "down_attempts": MIN_DOWN_ATTEMPTS,
                "clutch_attempts": MIN_CLUTCH_ATTEMPTS,
                "fourth_attempts": MIN_FOURTH_ATTEMPTS,
                "shrink_k_clutch": SHRINK_K_CLUTCH,
                "shrink_k_fourth": SHRINK_K_FOURTH,
            },
        },
        "kpis_window": {
            "league_avg_rating": float(np.average(arch["rating"],
                                                  weights=arch["attempts"])),
            "elite_count": int((arch["archetype"] == "Elite Quarterbacks").sum()),
            "qualified_qbs": int(len(arch)),
        },
        "kpis_by_season": kpis_by_season,
        "archetypes": archetypes,
        "situational_by_season": situational_by_season,
        "league_avg_by_season": {int(k): float(v)
                                 for k, v in league_by_season.items()},
        "players": players,
    }
    return round_rec(payload)


def inject(payload):
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    OUT_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    print(f"wrote {OUT_JSON}")

    if DASHBOARD_HTML.exists():
        html = DASHBOARD_HTML.read_text()
        safe = blob.replace("</", "<\\/")
        new = re.sub(
            r'(<script id="qb-data" type="application/json">).*?(</script>)',
            lambda m: m.group(1) + safe + m.group(2),
            html, flags=re.S)
        DASHBOARD_HTML.write_text(new)
        print(f"injected payload into {DASHBOARD_HTML}")
    else:
        print(f"note: {DASHBOARD_HTML} not found; JSON written only")


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--from-exports", action="store_true")
    mode.add_argument("--live", action="store_true")
    today = date.today()
    latest_season = today.year if today.month >= 9 else today.year - 1
    ap.add_argument("--seasons", nargs=2, type=int, default=[2019, latest_season],
                    metavar=("FIRST", "LAST"))
    args = ap.parse_args()

    payload = build_live(args.seasons) if args.live else build_from_exports()
    inject(payload)


if __name__ == "__main__":
    main()
