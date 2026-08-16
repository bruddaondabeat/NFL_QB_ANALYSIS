"""Shared data loaders for the NFL QB Analysis extension projects.

The PFR "standard passing" CSV exports in `Raw Data/` contain raw newlines
inside the Player and Awards fields (unquoted), so each logical row spans
multiple physical lines. A logical row always starts with the rank column
(`<digits>,`), which lets us stitch the file back together before parsing.
"""

from io import StringIO
from pathlib import Path
import re

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = REPO_ROOT / "Raw Data"
TABLEAU = REPO_ROOT / "tableau_exports"

_ROW_START = re.compile(r"^\d*,")  # rank column; empty for the League Average row


def load_pfr_passing(season: int) -> pd.DataFrame:
    """Load one season of PFR standard passing data, repairing split rows."""
    path = RAW_DATA / f"nfl_passing_{season}_standard.csv"
    lines = path.read_text().splitlines()

    header, records, current = lines[0], [], None
    for line in lines[1:]:
        if line == header:  # PFR repeats the header block mid-file
            continue
        if _ROW_START.match(line):
            if current is not None:
                records.append(current)
            current = line
        elif current is not None:
            current += " " + line.strip()
    if current is not None:
        records.append(current)

    df = pd.read_csv(StringIO(header + "\n" + "\n".join(records)))
    # Second 'Yds' column is sack yardage; pandas names it 'Yds.1'.
    df = df.rename(columns={"Yds.1": "SkYds"})
    df["Player"] = (
        df["Player"]
        .str.replace(r"[*+]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    df["season"] = season
    return df


def load_qb_seasons(seasons=(2021, 2022, 2023, 2024), min_attempts=150) -> pd.DataFrame:
    """Qualifying QB player-seasons across PFR exports, one row per player-season."""
    frames = []
    for season in seasons:
        df = load_pfr_passing(season)
        df = df[(df["Pos"].fillna("") == "QB") & (df["Att"] >= min_attempts)]
        # Multi-team players: PFR lists partial team rows plus a combined
        # '2TM'/'3TM' row. The exports here already carry one row per player,
        # but guard anyway by keeping the highest-attempt row per player id.
        df = df.sort_values("Att", ascending=False).drop_duplicates("Player-additional")
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    numeric = ["Age", "G", "GS", "Cmp", "Att", "Cmp%", "Yds", "TD", "TD%", "Int",
               "Int%", "Succ%", "Y/A", "AY/A", "Y/G", "Rate", "QBR", "Sk", "Sk%",
               "NY/A", "ANY/A", "4QC", "GWD"]
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def load_salaries() -> pd.DataFrame:
    """Parse `NFL Player Salary.txt` (Name / Team / money-line triplets)."""
    lines = [l for l in (REPO_ROOT / "NFL Player Salary.txt").read_text().splitlines()]
    # Skip the 5-line wrapped header, then read strict 3-line records.
    body = lines[5:]
    rows = []
    for i in range(0, len(body) - 2, 3):
        name = body[i].strip()
        team = body[i + 1].strip()
        fields = body[i + 2].split("\t")
        if len(fields) < 6 or not name:
            continue
        money = [float(f.replace("$", "").replace(",", "")) for f in fields[1:5]]
        rows.append({
            "player": name,
            "team": team,
            "age": int(fields[0]),
            "total_value": money[0],
            "apy": money[1],
            "total_guaranteed": money[2],
            "fully_guaranteed": money[3],
            "free_agency": fields[5].strip(),
        })
    return pd.DataFrame(rows)


def load_time_series() -> pd.DataFrame:
    return pd.read_csv(TABLEAU / "qb_time_series_2019_2023.csv")


def load_archetypes() -> pd.DataFrame:
    return pd.read_csv(TABLEAU / "qb_archetypes_2019_2023.csv")
