"""Extension 2 — QB Similarity Engine ("QB Comps"), 2019-2023.

Builds a style fingerprint for every qualifying QB season in the project's
time-series export (efficiency, aggressiveness, turnover profile, sack
avoidance, rushing value), then finds each season's nearest statistical
neighbors by cosine similarity — "which QB season does this one play like?" —
and projects the whole space to a 2D PCA map.

Outputs:
  extensions/output/qb_season_comps_2019_2023.csv
  extensions/qb-similarity-map.html
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

import page
import qb_data

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

MIN_ATTEMPTS = 150
TOP_K = 5

ARCH_COLORS = {
    "Elite Quarterbacks": page.BLUE,
    "The League Core": page.ORANGE,
    "Struggling & Backups": page.AQUA,
}
ARCH_SHORT = {
    "Elite Quarterbacks": "Elite",
    "The League Core": "Core",
    "Struggling & Backups": "Struggling",
    "Unclustered": "Unclustered",
}


def build_features() -> pd.DataFrame:
    ts = qb_data.load_time_series()
    ts = ts[ts["attempts"] >= MIN_ATTEMPTS].copy()
    dropbacks = ts["attempts"] + ts["sacks"]
    ts["cmp_pct"] = ts["completions"] / ts["attempts"] * 100
    ts["ypa"] = ts["passing_yards"] / ts["attempts"]
    ts["td_rate"] = ts["passing_tds"] / ts["attempts"] * 100
    ts["int_rate"] = ts["interceptions"] / ts["attempts"] * 100
    ts["sack_rate"] = ts["sacks"] / dropbacks * 100
    ts["epa_per_dropback"] = ts["passing_epa"] / dropbacks
    ts["air_ypa"] = ts["passing_air_yards"] / ts["attempts"]
    ts["rush_ypg"] = ts["rushing_yards"] / ts["games"]
    ts["rush_epa_pg"] = ts["rushing_epa"] / ts["games"]

    arch = qb_data.load_archetypes()[["player_id", "archetype"]]
    ts = ts.merge(arch, on="player_id", how="left")
    ts["archetype"] = ts["archetype"].fillna("Unclustered")
    ts["label"] = ts["display_name"] + " '" + ts["season"].astype(str).str[2:]
    return ts.reset_index(drop=True)


FEATURES = ["cmp_pct", "ypa", "td_rate", "int_rate", "sack_rate",
            "epa_per_dropback", "air_ypa", "rush_ypg", "rush_epa_pg"]


def compute_comps(ts: pd.DataFrame):
    X = StandardScaler().fit_transform(ts[FEATURES])
    sim = cosine_similarity(X)
    np.fill_diagonal(sim, -np.inf)
    rows = []
    for i in range(len(ts)):
        order = np.argsort(sim[i])[::-1][:TOP_K]
        for rank, j in enumerate(order, start=1):
            rows.append(dict(
                player=ts.loc[i, "display_name"], season=ts.loc[i, "season"],
                rank=rank,
                comp_player=ts.loc[j, "display_name"],
                comp_season=ts.loc[j, "season"],
                similarity=round(float(sim[i, j]), 4)))
    comps = pd.DataFrame(rows)
    pca = PCA(n_components=2, random_state=42)
    xy = pca.fit_transform(X)
    return comps, X, xy, pca, sim


def build_map(ts, xy, pca, sim) -> str:
    import plotly.graph_objects as go

    hover = []
    for i in range(len(ts)):
        top3 = np.argsort(sim[i])[::-1][:3]
        comp_txt = "<br>".join(
            f"  {r}. {ts.loc[j, 'label']} "
            f"<span style='color:#898781'>({sim[i, j]:.3f})</span>"
            for r, j in enumerate(top3, start=1))
        hover.append(
            f"<b>{ts.loc[i, 'display_name']} {ts.loc[i, 'season']}</b> "
            f"· {ARCH_SHORT[ts.loc[i, 'archetype']]}<br>"
            f"{ts.loc[i, 'cmp_pct']:.1f}% cmp · "
            f"{ts.loc[i, 'ypa']:.1f} Y/A · "
            f"{ts.loc[i, 'epa_per_dropback']:+.3f} EPA/db · "
            f"{ts.loc[i, 'rush_ypg']:.0f} rush yd/g<br>"
            f"<span style='color:#52514e'>Closest comps:</span><br>{comp_txt}")
    ts = ts.assign(hover=hover, x=xy[:, 0], y=xy[:, 1])

    # Direct labels: each QB's most recent qualifying season, thinned greedily
    # so no two labels sit closer than a minimum map distance (most extreme
    # points win a contested spot — the middle of the map stays readable).
    latest = ts.assign(x=xy[:, 0], y=xy[:, 1]) \
               .sort_values("season").groupby("display_name").tail(1)
    xr = xy[:, 0].max() - xy[:, 0].min()
    yr = xy[:, 1].max() - xy[:, 1].min()
    placed, keep = [], []
    for _, r in latest.assign(ext=lambda d: (d.x - d.x.mean()).abs() / xr
                              + (d.y - d.y.mean()).abs() / yr) \
                      .sort_values("ext", ascending=False).iterrows():
        if all(abs(r.x - px) / xr + abs(r.y - py) / yr > 0.11
               for px, py in placed):
            placed.append((r.x, r.y))
            keep.append(r)
    latest = pd.DataFrame(keep)

    fig = go.Figure()
    for arch in ["Elite Quarterbacks", "The League Core",
                 "Struggling & Backups", "Unclustered"]:
        sub = ts[ts["archetype"] == arch]
        if sub.empty:
            continue
        color = ARCH_COLORS.get(arch, page.MUTED)
        fig.add_trace(go.Scatter(
            x=sub["x"], y=sub["y"], mode="markers", name=ARCH_SHORT[arch],
            marker=dict(size=9, color=color, opacity=0.85,
                        line=dict(width=2, color=page.SURFACE)),
            text=sub["hover"], hovertemplate="%{text}<extra></extra>"))
    for _, r in latest.iterrows():
        fig.add_annotation(
            x=r["x"], y=r["y"], text=r["display_name"], showarrow=False,
            yshift=13, font=dict(size=11, color=page.INK_2))

    var1, var2 = pca.explained_variance_ratio_ * 100
    fig.update_layout(
        height=560,
        xaxis=dict(title=f"PC1 ({var1:.0f}% of variance) — passing efficiency →",
                   **page.AXIS),
        yaxis=dict(title=f"PC2 ({var2:.0f}% of variance) — rushing value "
                         f"& downfield aggression →", **page.AXIS),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(color=page.INK_2)),
        **page.PLOTLY_LAYOUT)
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True})


def comps_table_html(ts, comps) -> str:
    """Top comps for every 2023 qualifying season, most recent first."""
    label = ts.set_index(["display_name", "season"])["label"]
    latest = comps[comps["season"] == 2023]
    tr = []
    for player in sorted(latest["player"].unique()):
        top = latest[(latest["player"] == player)].nsmallest(3, "rank")
        cells = " &middot; ".join(
            f"{label[(r.comp_player, r.comp_season)]} "
            f"<span style='color:#898781'>({r.similarity:.3f})</span>"
            for r in top.itertuples())
        tr.append(f"<tr><td class='name'>{player} &rsquo;23</td><td>{cells}</td></tr>")
    return ("<div class='table-scroll'><table class='data'><thead><tr><th>2023 season</th>"
            "<th>Three closest statistical comps (cosine similarity)</th></tr>"
            "</thead><tbody>" + "".join(tr) + "</tbody></table></div>")


def main():
    ts = build_features()
    comps, X, xy, pca, sim = compute_comps(ts)
    comps.to_csv(OUT / "qb_season_comps_2019_2023.csv", index=False)

    legend_note = "".join(
        f"<span><span class='dot' style='background:{ARCH_COLORS[a]}'></span>"
        f"{ARCH_SHORT[a]}</span>" for a in ARCH_COLORS)

    body = f"""
<div class="card">
  <h2>The QB style map</h2>
  <p class="note">Every qualifying season (&ge;{MIN_ATTEMPTS} attempts) from the
  project&rsquo;s 2019&ndash;2023 tracked cohort, projected onto two principal
  components of a nine-feature style fingerprint. Seasons that sit close together
  were statistically similar &mdash; hover any point for its three closest comps.
  Labels mark each QB&rsquo;s most recent qualifying season; color is the
  archetype from the core project&rsquo;s clustering model.</p>
  {{MAP}}
</div>
<div class="card">
  <h2>2023 seasons and their closest historical comps</h2>
  <p class="note">Nearest neighbors across all {{N}} player-seasons. A QB&rsquo;s own
  earlier season showing up as a top comp means his style held steady year over year.</p>
  {{TABLE}}
</div>"""
    body = (body.replace("{MAP}", build_map(ts, xy, pca, sim))
                .replace("{TABLE}", comps_table_html(ts, comps))
                .replace("{N}", str(len(ts))))

    footer = ("Method: nine per-season features &mdash; completion %, yards/attempt, "
              "TD rate, INT rate, sack rate, EPA/dropback, air yards/attempt, rush "
              "yards/game, rushing EPA/game &mdash; standardized, compared with cosine "
              "similarity, and projected with PCA. Data: nflverse seasonal data in "
              "<code>tableau_exports/qb_time_series_2019_2023.csv</code>. "
              "Part of the <a href='../index.html'>NFL QB Analysis</a> extension suite.")

    html = page.render_page(
        "QB Similarity Engine",
        "A nearest-neighbor “comps” model over 2019–2023 QB seasons: every "
        "season becomes a nine-feature style fingerprint, and the model answers a "
        "scouting-room question &mdash; who does this quarterback actually play like?",
        body, footer, "Similarity Engine")
    (HERE / "qb-similarity-map.html").write_text(html)
    print(f"OK: {len(ts)} seasons, {len(comps)} comp rows; "
          f"PC variance {pca.explained_variance_ratio_.round(2)}")


if __name__ == "__main__":
    main()
