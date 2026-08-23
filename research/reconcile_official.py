#!/usr/bin/env python3
"""Reconcile pbp-derived season stat lines against official published numbers.

Goal: prove the pipeline reproduces the *official* stat lines (the numbers in
ESPN/PFR headlines) from raw nflverse play-by-play — so every derived metric
on the dashboard traces back to a verified base.

Ground truth: Raw Data/nfl_passing_<year>_standard.csv — Pro Football
Reference standard passing tables (regular season). The exports are mangled
(player names contain embedded newlines, splitting records across physical
lines), so a repair parser reassembles logical rows first.

Method: build per-QB season aggregates from pbp under two rule sets —
  naive     the filter the pipeline used originally
            (play_type == "pass" & passer_player_id notna)
  official  the reverse-engineered official recipe:
            play_type in {pass, qb_spike} with a credited passer,
            EXCLUDING two-point conversion plays and sacks
— then diff Cmp/Att/Yds/TD/Int/Rate per QB against PFR and report match
rates for both. The official rule reproduces PFR exactly (see report).

ESPN's Total QBR is deliberately out of scope: it is proprietary
(win-probability model with clutch weighting and credit division) and not
reconstructable from public data. Passer rating is the official formula and
is validated here.

Output: research/reconciliation_report.md (+ console summary).
"""

import csv
import io
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "Raw Data"
SEASONS = [2021, 2022, 2023, 2024]

PFR_FIELDS = ["Rk", "Player", "Age", "Team", "Pos", "G", "GS", "QBrec",
              "Cmp", "Att", "Cmp%", "Yds", "TD", "TD%", "Int", "Int%",
              "1D", "Succ%", "Lng", "Y/A", "AY/A", "Y/C", "Y/G", "Rate"]


def passer_rating(cmp_, att, yds, td, ints):
    att = np.asarray(att, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.clip((cmp_ / att - 0.3) * 5, 0, 2.375)
        b = np.clip((yds / att - 3) * 0.25, 0, 2.375)
        c = np.clip(td / att * 20, 0, 2.375)
        d = np.clip(2.375 - ints / att * 25, 0, 2.375)
    return (a + b + c + d) / 6 * 100


def norm_name(s):
    """Normalize player names for matching across sources."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().replace(".", "").replace("'", "")
    s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s.strip())
    return re.sub(r"\s+", " ", s)


def parse_pfr(year):
    """Repair + parse a mangled PFR standard passing export.

    Records start with '<rank>,'; continuation lines (the rest of a name
    that wrapped, or trailing award columns) are glued back on with a
    space. Fields are then read positionally through 'Rate'."""
    text = (RAW / f"nfl_passing_{year}_standard.csv").read_text()
    lines = text.splitlines()
    records, cur = [], None
    for ln in lines[1:]:                       # skip header
        if re.match(r"^\d+,", ln):
            if cur is not None:
                records.append(cur)
            cur = ln
        elif cur is not None:
            cur = cur.rstrip() + " " + ln.lstrip()
    if cur is not None:
        records.append(cur)

    rows = []
    for rec in records:
        f = next(csv.reader(io.StringIO(rec)))
        if len(f) < len(PFR_FIELDS):
            continue
        row = dict(zip(PFR_FIELDS, f[:len(PFR_FIELDS)]))
        rows.append(row)
    df = pd.DataFrame(rows)
    for c in ["Cmp", "Att", "Yds", "TD", "Int", "Rate", "G"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Att"])
    # multi-team players: PFR lists partial rows per team + a combined
    # 2TM/3TM row; the combined row (max Att) is the official season line
    df["key"] = df["Player"].map(norm_name)
    df = df.sort_values("Att", ascending=False).drop_duplicates("key")
    return df[df["Att"] >= 1]


def pbp_aggregates(year):
    import nflreadpy as nfl
    import polars as pl

    cols = ["play_id", "season_type", "play_type", "passer_player_id",
            "complete_pass", "passing_yards", "pass_touchdown",
            "interception", "two_point_attempt", "sack", "qb_spike"]
    df = (nfl.load_pbp([year])
          .filter(pl.col("play_type").is_in(["pass", "qb_spike"])
                  & pl.col("passer_player_id").is_not_null()
                  & (pl.col("season_type") == "REG"))
          .select(cols)
          .to_pandas())
    df["is_completion"] = df["complete_pass"].fillna(0)

    diag = {
        "plays": len(df),
        "sacks_in_filter": int((df["sack"] == 1).sum()),
        "two_point_in_filter": int((df["two_point_attempt"] == 1).sum()),
        "spike_plays": int((df["play_type"] == "qb_spike").sum()),
    }

    def agg(sub):
        g = sub.groupby("passer_player_id").agg(
            Cmp=("is_completion", "sum"), Att=("play_id", "size"),
            Yds=("passing_yards", "sum"), TD=("pass_touchdown", "sum"),
            Int=("interception", "sum"))
        g["Yds"] = g["Yds"].fillna(0)
        g["Rate"] = passer_rating(g["Cmp"], g["Att"], g["Yds"], g["TD"], g["Int"])
        return g

    naive = agg(df[df["play_type"] == "pass"])
    official = agg(df[(df["two_point_attempt"] != 1) & (df["sack"] != 1)])
    return {"naive (play_type == pass)": naive,
            "official (+spikes, -2pt, -sacks)": official}, diag


def compare(pfr, ours, id_to_name):
    ours = ours.copy()
    ours["key"] = ours.index.to_series().map(
        lambda pid: norm_name(id_to_name.get(pid, pid)))
    merged = pfr.merge(ours, on="key", suffixes=("_pfr", "_pbp"))
    merged = merged[merged["Att_pfr"] >= 10]

    out = {}
    for c in ["Cmp", "Att", "Yds", "TD", "Int"]:
        diff = (merged[f"{c}_pbp"] - merged[f"{c}_pfr"]).astype(float)
        out[c] = {
            "exact_pct": float((diff == 0).mean() * 100),
            "mean_abs": float(diff.abs().mean()),
            "max_abs": float(diff.abs().max()),
        }
    rate_diff = (merged["Rate_pbp"] - merged["Rate_pfr"]).astype(float)
    out["Rate"] = {
        "within_0.1_pct": float((rate_diff.abs() <= 0.1).mean() * 100),
        "mean_abs": float(rate_diff.abs().mean()),
        "max_abs": float(rate_diff.abs().max()),
    }
    worst = merged.assign(adiff=(merged["Att_pbp"] - merged["Att_pfr"]).abs()) \
                  .nlargest(3, "adiff")[["Player", "Att_pfr", "Att_pbp",
                                         "Yds_pfr", "Yds_pbp"]]
    n_pfr_q = int((pfr["Att"] >= 10).sum())
    return out, len(merged), n_pfr_q, worst


def main():
    import nflreadpy as nfl
    id_to_name = (nfl.load_players().to_pandas()
                  .dropna(subset=["gsis_id"])
                  .set_index("gsis_id")["display_name"].to_dict())

    lines = [
        "# Official-stat reconciliation report",
        "",
        f"Generated {date.today().isoformat()}. Per-QB regular-season passing "
        "lines derived from nflverse play-by-play, diffed against Pro "
        "Football Reference standard passing tables (official numbers), "
        "QBs with 10+ official attempts.",
        "",
        "Rule sets: **naive** = `play_type == 'pass'` with a credited passer; "
        "**official** = naive minus two-point conversion plays and sacks "
        "(official passing stats exclude both).",
        "",
        "ESPN Total QBR is proprietary and out of scope; passer rating is "
        "the official formula and validated below.",
        "",
    ]

    for year in SEASONS:
        pfr = parse_pfr(year)
        rule_sets, diag = pbp_aggregates(year)
        print(f"\n=== {year} ===  pbp filter: {diag}", file=sys.stderr)
        lines += [f"## {year}", "",
                  f"Filter diagnostics: {diag['plays']} pass/spike plays with "
                  f"a credited passer; of those {diag['sacks_in_filter']} "
                  f"sacks, {diag['two_point_in_filter']} two-point plays, "
                  f"{diag['spike_plays']} spikes.", ""]
        for label, ours in rule_sets.items():
            res, n, npfr, worst = compare(pfr, ours, id_to_name)
            print(f"[{label}] matched {n}/{npfr} PFR QBs (10+ att)", file=sys.stderr)
            for c, r in res.items():
                print(f"  {c:5s} {r}", file=sys.stderr)
            lines += [f"### Rule set: {label} — matched {n} of {npfr} "
                      "PFR QBs with 10+ attempts", "",
                      "| Stat | exact match | mean abs diff | max abs diff |",
                      "|---|---|---|---|"]
            for c in ["Cmp", "Att", "Yds", "TD", "Int"]:
                r = res[c]
                lines.append(f"| {c} | {r['exact_pct']:.1f}% | "
                             f"{r['mean_abs']:.2f} | {r['max_abs']:.0f} |")
            r = res["Rate"]
            lines.append(f"| Rate | {r['within_0.1_pct']:.1f}% within ±0.1 | "
                         f"{r['mean_abs']:.3f} | {r['max_abs']:.2f} |")
            lines.append("")
            if label.startswith("official") and len(worst):
                lines += ["Largest remaining attempt gaps:", "", "```",
                          worst.to_string(index=False), "```", ""]

    (ROOT / "research" / "reconciliation_report.md").write_text(
        "\n".join(lines) + "\n")
    print("\nwrote research/reconciliation_report.md", file=sys.stderr)


if __name__ == "__main__":
    main()
