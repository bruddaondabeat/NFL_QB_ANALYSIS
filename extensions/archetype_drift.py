"""Extension 1 — Archetype Drift (2021-2024).

Re-fits the project's KMeans archetype model on four seasons of PFR passing
data (including the previously unused 2024 export), pooled and standardized so
cluster boundaries are comparable across years, then tracks how each QB
migrates between archetypes season over season.

Outputs:
  extensions/output/qb_archetypes_2021_2024.csv
  extensions/qb-archetype-drift.html
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

import page
import qb_data

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

FEATURES = ["Cmp%", "Y/A", "TD%", "Int%"]  # same axes as the original model
SEASONS = [2021, 2022, 2023, 2024]

ARCH_COLORS = {
    "Elite Quarterbacks": page.BLUE,
    "The League Core": page.ORANGE,
    "Struggling & Backups": page.AQUA,
}
ARCH_SHORT = {
    "Elite Quarterbacks": "Elite",
    "The League Core": "Core",
    "Struggling & Backups": "Struggling",
}
ARCH_ORDER = ["Elite Quarterbacks", "The League Core", "Struggling & Backups"]


def fit_archetypes() -> pd.DataFrame:
    qb = qb_data.load_qb_seasons(SEASONS).dropna(subset=FEATURES).copy()
    X = StandardScaler().fit_transform(qb[FEATURES])
    km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)
    qb["cluster"] = km.labels_

    # Rank clusters by a quality composite of their centers: accuracy +
    # efficiency + scoring - turnovers (computed in standardized space).
    centers = pd.DataFrame(km.cluster_centers_, columns=FEATURES)
    quality = (centers["Cmp%"] + centers["Y/A"] + centers["TD%"] - centers["Int%"])
    ranked = quality.sort_values(ascending=False).index.tolist()
    qb["archetype"] = qb["cluster"].map(dict(zip(ranked, ARCH_ORDER)))
    return qb


def build_sankey(qb: pd.DataFrame) -> str:
    import plotly.graph_objects as go

    # Nodes: one per archetype x season, pinned into season columns.
    nodes, node_idx = [], {}
    for si, season in enumerate(SEASONS):
        for ai, arch in enumerate(ARCH_ORDER):
            node_idx[(season, arch)] = len(nodes)
            n = len(qb[(qb.season == season) & (qb.archetype == arch)])
            nodes.append(dict(
                label=f"{ARCH_SHORT[arch]} ({n})",
                color=ARCH_COLORS[arch],
                x=0.02 + 0.96 * si / (len(SEASONS) - 1),
                y=[0.12, 0.5, 0.88][ai],
            ))

    def hex_to_rgba(h, a):
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        return f"rgba({r},{g},{b},{a})"

    links = dict(source=[], target=[], value=[], color=[], customdata=[])
    by_key = qb.set_index(["Player-additional", "season"])["archetype"]
    names = qb.set_index(["Player-additional", "season"])["Player"]
    for s0, s1 in zip(SEASONS[:-1], SEASONS[1:]):
        pairs = {}
        for pid in qb[qb.season == s0]["Player-additional"]:
            if (pid, s1) in by_key.index:
                key = (by_key[(pid, s0)], by_key[(pid, s1)])
                pairs.setdefault(key, []).append(names[(pid, s0)])
        for (a0, a1), players in pairs.items():
            links["source"].append(node_idx[(s0, a0)])
            links["target"].append(node_idx[(s1, a1)])
            links["value"].append(len(players))
            links["color"].append(hex_to_rgba(ARCH_COLORS[a0], 0.32))
            links["customdata"].append(", ".join(sorted(players)))

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            label=[n["label"] for n in nodes],
            color=[n["color"] for n in nodes],
            x=[n["x"] for n in nodes],
            y=[n["y"] for n in nodes],
            pad=28, thickness=14,
            line=dict(width=0),
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=links["source"], target=links["target"], value=links["value"],
            color=links["color"], customdata=links["customdata"],
            hovertemplate="%{source.label} → %{target.label}: "
                          "%{value} QBs<br><span style='color:#52514e'>"
                          "%{customdata}</span><extra></extra>",
        ),
        textfont=dict(family=page.FONT, color=page.INK, size=13),
    ))
    fig.update_layout(height=440, **{k: v for k, v in page.PLOTLY_LAYOUT.items()
                                     if k != "margin"},
                      margin=dict(l=12, r=12, t=44, b=8))
    for si, season in enumerate(SEASONS):
        fig.add_annotation(x=0.02 + 0.96 * si / (len(SEASONS) - 1), y=1.07,
                           xref="paper", yref="paper", showarrow=False,
                           text=f"<b>{season}</b>",
                           font=dict(color=page.INK_2, size=13))
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True})


def movers_html(qb: pd.DataFrame) -> str:
    by_key = qb.set_index(["Player-additional", "season"])
    rows = []
    for s0, s1 in zip(SEASONS[:-1], SEASONS[1:]):
        for pid in qb[qb.season == s0]["Player-additional"]:
            if (pid, s1) in by_key.index:
                a0 = by_key.loc[(pid, s0), "archetype"]
                a1 = by_key.loc[(pid, s1), "archetype"]
                if a0 != a1:
                    rows.append(dict(
                        player=by_key.loc[(pid, s1), "Player"], frm=a0, to=a1,
                        span=f"{s0} &rarr; {s1}",
                        up=ARCH_ORDER.index(a1) < ARCH_ORDER.index(a0)))
    rows.sort(key=lambda r: (r["span"], not r["up"], r["player"]))
    tr = []
    for r in rows:
        arrow = "&#9650;" if r["up"] else "&#9660;"
        arrow_color = "#006300" if r["up"] else "#d03b3b"
        tr.append(
            f"<tr><td class='name'>{r['player']}</td><td>{r['span']}</td>"
            f"<td><span class='dot' style='background:{ARCH_COLORS[r['frm']]}'></span>{ARCH_SHORT[r['frm']]}"
            f" &rarr; <span class='dot' style='background:{ARCH_COLORS[r['to']]}'></span>{ARCH_SHORT[r['to']]}</td>"
            f"<td style='color:{arrow_color}'>{arrow} {'Riser' if r['up'] else 'Faller'}</td></tr>")
    return ("<div class='table-scroll'><table class='data'><thead><tr><th>Quarterback</th><th>Seasons</th>"
            "<th>Archetype change</th><th>Direction</th></tr></thead><tbody>"
            + "".join(tr) + "</tbody></table></div>")


def table_html(qb: pd.DataFrame) -> str:
    pivot = qb.pivot_table(index="Player", columns="season", values="archetype",
                           aggfunc="first")
    order = (qb.groupby("Player")
               .apply(lambda g: (g["archetype"] == "Elite Quarterbacks").sum(),
                      include_groups=False)
               .sort_values(ascending=False))
    pivot = pivot.loc[order.index]
    tr = []
    for player, row in pivot.iterrows():
        cells = []
        for season in SEASONS:
            arch = row.get(season)
            if isinstance(arch, str):
                cells.append(f"<td><span class='dot' style='background:{ARCH_COLORS[arch]}'>"
                             f"</span>{ARCH_SHORT[arch]}</td>")
            else:
                cells.append("<td style='color:#898781'>&mdash;</td>")
        tr.append(f"<tr><td class='name'>{player}</td>{''.join(cells)}</tr>")
    header = "".join(f"<th>{s}</th>" for s in SEASONS)
    return (f"<div class='table-scroll'><table class='data'><thead><tr>"
            f"<th>Quarterback</th>{header}</tr>"
            f"</thead><tbody>{''.join(tr)}</tbody></table></div>")


def main():
    qb = fit_archetypes()

    export = qb[["Player", "Player-additional", "Team", "season", "Age", "Att",
                 *FEATURES, "Rate", "ANY/A", "archetype", "cluster"]].copy()
    export.columns = ["player", "player_id", "team", "season", "age", "attempts",
                      "completion_pct", "yards_per_attempt", "td_rate", "int_rate",
                      "passer_rating", "any_a", "archetype", "cluster"]
    export.sort_values(["season", "archetype", "player"]).to_csv(
        OUT / "qb_archetypes_2021_2024.csv", index=False)

    legend = "".join(
        f"<span><span class='dot' style='background:{ARCH_COLORS[a]}'></span>"
        f"{ARCH_SHORT[a]} &mdash; {a}</span>" for a in ARCH_ORDER)

    body = f"""
<div class="card">
  <h2>How QBs flowed between archetypes, season to season</h2>
  <p class="note">Each band is a group of quarterbacks moving (or staying put)
  between archetypes in consecutive qualifying seasons (&ge;150 attempts).
  Hover a band to see exactly which QBs made that move.</p>
  <p class="legend">{legend}</p>
  {{SANKEY}}
</div>
<div class="card">
  <h2>The movers</h2>
  <p class="note">Every archetype change between consecutive qualifying seasons.
  A <em>riser</em> moved toward the Elite cluster; a <em>faller</em> moved away from it.</p>
  {{MOVERS}}
</div>
<div class="card">
  <h2>Full archetype history, 2021&ndash;2024</h2>
  <p class="note">One row per QB, sorted by seasons spent in the Elite cluster.
  A dash means the QB didn&rsquo;t reach 150 attempts that season.</p>
  {{TABLE}}
</div>"""
    body = (body.replace("{SANKEY}", build_sankey(qb))
                .replace("{MOVERS}", movers_html(qb))
                .replace("{TABLE}", table_html(qb)))

    n = len(qb)
    footer = (f"Method: KMeans (k=3) refit on {n} pooled player-seasons "
              f"(2021&ndash;2024, &ge;150 attempts) over the original model&rsquo;s four axes "
              f"&mdash; completion %, yards/attempt, TD rate, INT rate &mdash; standardized "
              f"before clustering so seasons share one boundary. Data: Pro-Football-Reference "
              f"standard passing exports in <code>Raw Data/</code>. "
              f"Part of the <a href='../index.html'>NFL QB Analysis</a> extension suite.")

    html = page.render_page(
        "QB Archetype Drift, 2021&ndash;2024",
        "The core project found three QB archetypes in 2019&ndash;2023 data. This extension "
        "refits that clustering model across 2021&ndash;2024 &mdash; adding the unused 2024 "
        "season &mdash; and follows every quarterback&rsquo;s movement between archetypes.",
        body, footer, "Archetype Drift")
    (HERE / "qb-archetype-drift.html").write_text(html)
    print(f"OK: {n} player-seasons clustered; "
          f"{(export.groupby('season')['archetype'].value_counts()).to_dict()}")


if __name__ == "__main__":
    main()
