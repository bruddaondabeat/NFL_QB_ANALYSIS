"""Shared HTML page scaffolding so all extension dashboards look like one system."""

# Categorical slots (validated palette, fixed order — see dataviz method).
BLUE = "#2a78d6"    # slot 1
ORANGE = "#eb6834"  # slot 2
AQUA = "#1baf7a"    # slot 3

SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

PLOTLY_LAYOUT = dict(
    font=dict(family=FONT, color=INK, size=13),
    paper_bgcolor=SURFACE,
    plot_bgcolor=SURFACE,
    margin=dict(l=56, r=24, t=16, b=48),
    hoverlabel=dict(
        bgcolor="#ffffff",
        bordercolor=GRID,
        font=dict(family=FONT, color=INK, size=12),
    ),
)

AXIS = dict(
    gridcolor=GRID,
    gridwidth=1,
    zeroline=False,
    linecolor=BASELINE,
    tickfont=dict(color=MUTED, size=12),
    title_font=dict(color=INK_2, size=13),
)

CSS = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: {PAGE}; color: {INK};
  font-family: {FONT};
  line-height: 1.55;
}}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 64px; }}
nav.crumbs {{ font-size: 13px; color: {MUTED}; margin-bottom: 20px; }}
nav.crumbs a {{ color: {INK_2}; text-decoration: none; border-bottom: 1px solid {GRID}; }}
nav.crumbs a:hover {{ color: {INK}; }}
h1 {{ font-size: 28px; margin: 0 0 6px; letter-spacing: -0.01em; }}
p.sub {{ color: {INK_2}; margin: 0 0 28px; max-width: 72ch; }}
.card {{
  background: {SURFACE}; border: 1px solid rgba(11,11,11,0.10);
  border-radius: 10px; padding: 20px 20px 8px; margin-bottom: 28px;
}}
.card h2 {{ font-size: 17px; margin: 0 0 2px; }}
.card p.note {{ color: {INK_2}; font-size: 13.5px; margin: 2px 0 10px; max-width: 80ch; }}
.table-scroll {{ overflow-x: auto; margin: 8px 0 16px; }}
table.data {{
  width: 100%; min-width: 540px; border-collapse: collapse; font-size: 13.5px;
}}
table.data th {{
  text-align: left; color: {MUTED}; font-weight: 600; font-size: 12px;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid {BASELINE}; padding: 6px 10px;
}}
table.data td {{
  padding: 6px 10px; border-bottom: 1px solid {GRID};
  font-variant-numeric: tabular-nums;
}}
table.data td.name {{ font-weight: 600; }}
.dot {{
  display: inline-block; width: 9px; height: 9px; border-radius: 50%;
  margin-right: 7px; vertical-align: baseline;
}}
.legend {{ font-size: 13px; color: {INK_2}; margin: 0 0 6px; }}
.legend span {{ margin-right: 18px; white-space: nowrap; }}
footer {{ color: {MUTED}; font-size: 12.5px; margin-top: 8px; max-width: 80ch; }}
footer a {{ color: {INK_2}; }}
"""


def render_page(title: str, subtitle: str, body_html: str, footer_html: str,
                crumb: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="assets/plotly.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<nav class="crumbs"><a href="../index.html">NFL QB Analysis</a> &rsaquo; Extensions &rsaquo; {crumb}</nav>
<h1>{title}</h1>
<p class="sub">{subtitle}</p>
{body_html}
<footer>{footer_html}</footer>
</div>
</body>
</html>"""
