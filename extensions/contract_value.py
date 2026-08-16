"""Extension 3 — 2025 QB Contract Value Board.

The core project fused 2019-2023 performance with salary data. This extension
brings that idea current: it parses the 2025 contract table in
`NFL Player Salary.txt` and asks what each QB's 2024 season (ANY/A, the
sack- and interception-adjusted efficiency yardstick) says about the deal his
team is paying for now.

Outputs:
  extensions/output/qb_contract_value_2025.csv
  extensions/qb-contract-value.html
"""

from pathlib import Path

import numpy as np
import pandas as pd

import page
import qb_data

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

# Salary-table name -> PFR name.
ALIASES = {"Matt Stafford": "Matthew Stafford",
           "Gardner Minshew": "Gardner Minshew II"}
# Age/APY heuristic exceptions: cheap veteran deals that would otherwise
# look like rookie-scale contracts.
VETERAN_OVERRIDES = {"Mac Jones"}

VET = "Veteran deal"
ROOKIE = "Rookie-scale deal"
TIER_COLORS = {VET: page.BLUE, ROOKIE: page.ORANGE}


def build_board() -> pd.DataFrame:
    sal = qb_data.load_salaries()
    sal["player"] = sal["player"].replace(ALIASES)

    perf = qb_data.load_qb_seasons(seasons=(2024,))
    board = sal.merge(perf, left_on="player", right_on="Player", how="inner")

    unmatched = sorted(set(perf["Player"]) - set(sal["player"]))
    if unmatched:
        print(f"note: 2024 qualifiers with no current contract row: {unmatched}")

    board["contract_type"] = np.where(
        (board["apy"] <= 13e6) & (board["age"] <= 27)
        & ~board["player"].isin(VETERAN_OVERRIDES),
        ROOKIE, VET)
    board["apy_m"] = board["apy"] / 1e6
    board["any_a"] = board["ANY/A"]
    board["perf_pctl"] = board["ANY/A"].rank(pct=True) * 100
    board["cost_pctl"] = board["apy"].rank(pct=True) * 100
    board["value_score"] = board["perf_pctl"] - board["cost_pctl"]
    return board.sort_values("value_score", ascending=False).reset_index(drop=True)


def build_scatter(board: pd.DataFrame) -> str:
    import plotly.graph_objects as go

    med_x = board["apy_m"].median()
    med_y = board["ANY/A"].median()

    fig = go.Figure()
    fig.add_hline(y=med_y, line=dict(color=page.BASELINE, width=1, dash="dot"))
    fig.add_vline(x=med_x, line=dict(color=page.BASELINE, width=1, dash="dot"))

    for tier in [VET, ROOKIE]:
        sub = board[board["contract_type"] == tier]
        hover = [
            f"<b>{r.player}</b> · {r.team} · age {r.age}<br>"
            f"${r.apy_m:.1f}M/yr · {r.any_a:.2f} ANY/A · "
            f"{r.Rate:.1f} rating ({int(r.Att)} att, 2024)<br>"
            f"<span style='color:#52514e'>Value score "
            f"{r.value_score:+.0f} (perf pctl {r.perf_pctl:.0f} − "
            f"cost pctl {r.cost_pctl:.0f})</span>"
            for r in sub.itertuples()]
        fig.add_trace(go.Scatter(
            x=sub["apy_m"], y=sub["ANY/A"], mode="markers", name=tier,
            marker=dict(size=9, color=TIER_COLORS[tier], opacity=0.9,
                        line=dict(width=2, color=page.SURFACE)),
            text=hover, hovertemplate="%{text}<extra></extra>"))

    # Thinned direct labels, extremes first.
    xr = board["apy_m"].max() - board["apy_m"].min()
    yr = board["ANY/A"].max() - board["ANY/A"].min()
    placed = []
    ext = ((board["apy_m"] - med_x).abs() / xr + (board["ANY/A"] - med_y).abs() / yr)
    for _, r in board.assign(ext=ext).sort_values("ext", ascending=False).iterrows():
        if all(abs(r.apy_m - px) / xr + abs(r["ANY/A"] - py) / yr > 0.085
               for px, py in placed):
            placed.append((r.apy_m, r["ANY/A"]))
            fig.add_annotation(x=r.apy_m, y=r["ANY/A"], text=r.player,
                               showarrow=False, yshift=13,
                               font=dict(size=11, color=page.INK_2))

    corners = [(0.01, 0.99, "Bargain production", "left"),
               (0.99, 0.99, "Paid & producing", "right"),
               (0.01, 0.01, "Low cost, low output", "left"),
               (0.99, 0.01, "Contracts under pressure", "right")]
    for x, y, txt, anchor in corners:
        fig.add_annotation(x=x, y=y, xref="paper", yref="paper", text=txt,
                           showarrow=False, xanchor=anchor,
                           font=dict(size=12, color=page.MUTED))

    fig.update_layout(
        height=560,
        xaxis=dict(title="Contract average per year ($M)", ticksuffix="M",
                   tickprefix="$", **page.AXIS),
        yaxis=dict(title="2024 adjusted net yards per attempt (ANY/A)",
                   **page.AXIS),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(color=page.INK_2)),
        **page.PLOTLY_LAYOUT)
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True})


def value_table_html(rows: pd.DataFrame) -> str:
    tr = []
    for r in rows.itertuples():
        color = TIER_COLORS[r.contract_type]
        score_color = "#006300" if r.value_score >= 0 else "#d03b3b"
        tr.append(
            f"<tr><td class='name'><span class='dot' style='background:{color}'>"
            f"</span>{r.player}</td><td>{r.team}</td>"
            f"<td>${r.apy_m:,.1f}M</td><td>{r.any_a:.2f}</td>"
            f"<td style='color:{score_color}'>{r.value_score:+.0f}</td></tr>")
    return ("<div class='table-scroll'><table class='data'><thead><tr><th>Quarterback</th><th>2025 team</th>"
            "<th>APY</th><th>2024 ANY/A</th><th>Value score</th></tr></thead>"
            "<tbody>" + "".join(tr) + "</tbody></table></div>")


def main():
    board = build_board()

    export = board[["player", "team", "age", "contract_type", "apy",
                    "total_value", "fully_guaranteed", "free_agency", "Att",
                    "Cmp%", "Yds", "TD", "Int", "Rate", "QBR", "ANY/A",
                    "perf_pctl", "cost_pctl", "value_score"]].copy()
    export.columns = [c.lower().replace("%", "_pct").replace("/", "_")
                      for c in export.columns]
    export.to_csv(OUT / "qb_contract_value_2025.csv", index=False)

    any_col = board.columns.get_loc("ANY/A")
    best = board.head(8)
    pressure = board[board["apy"] >= 30e6].sort_values("value_score").head(8)

    body = f"""
<div class="card">
  <h2>Every 2024 qualifying QB against his current contract</h2>
  <p class="note">Each point is a QB with &ge;150 attempts in 2024, placed by what
  his current deal costs per year against how efficiently he actually played
  (ANY/A &mdash; net yards with sack losses, a 20-yard TD bonus and a 45-yard INT
  penalty baked in). Dotted lines mark the medians; hover any point for the full
  contract-vs-production readout.</p>
  {{SCATTER}}
</div>
<div class="card">
  <h2>Best value: production the market isn&rsquo;t charging for</h2>
  <p class="note">Value score = 2024 performance percentile minus contract cost
  percentile. Rookie-scale deals dominate by construction &mdash; that&rsquo;s the
  competitive advantage of hitting on a draft pick.</p>
  {{BEST}}
</div>
<div class="card">
  <h2>Contracts under pressure: $30M+ per year, lagging returns</h2>
  <p class="note">Big-money deals whose 2024 production fell short of the price
  tag. One down season doesn&rsquo;t make a bad contract &mdash; but these are the
  deals carrying the most risk into 2025.</p>
  {{PRESSURE}}
</div>"""
    body = (body.replace("{SCATTER}", build_scatter(board))
                .replace("{BEST}", value_table_html(best))
                .replace("{PRESSURE}", value_table_html(pressure)))

    footer = ("Method: 2025 contract terms parsed from <code>NFL Player Salary.txt</code> "
              "(APY = average per year), joined to 2024 Pro-Football-Reference passing "
              "data (&ge;150 attempts). Value score is performance percentile minus cost "
              "percentile within this qualifier pool. Teams shown are 2025 contract "
              "teams, which can differ from the team a QB played for in 2024. "
              "2025 draftees have no NFL season yet and are excluded. "
              "Part of the <a href='../index.html'>NFL QB Analysis</a> extension suite.")

    html = page.render_page(
        "2025 QB Contract Value Board",
        "The core project priced 2019–2023 production against the market. This "
        "extension runs the same playbook on today&rsquo;s money: current contracts "
        "against 2024 on-field efficiency, to find the bargains and the deals under "
        "pressure.",
        body, footer, "Contract Value Board")
    (HERE / "qb-contract-value.html").write_text(html)
    print(f"OK: {len(board)} QBs on board; best value: "
          f"{best.iloc[0]['player']} ({best.iloc[0]['value_score']:+.0f}), "
          f"most pressure: {pressure.iloc[0]['player']} "
          f"({pressure.iloc[0]['value_score']:+.0f})")


if __name__ == "__main__":
    main()
