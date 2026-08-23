import pandas as pd, numpy as np, warnings
from sklearn.linear_model import LinearRegression
from scipy.stats import rankdata, norm
warnings.filterwarnings('ignore')

m = pd.read_parquet('season_qb_merged.parquet')
pbp = pd.read_parquet('pbp_full.parquet')
pbp = pbp[pbp['season_type'] == 'REG']

# ---------- opponent (defense) strength: EPA/play allowed on dropbacks+rushes ----------
d = pbp[((pbp['pass'] == 1) | (pbp['rush'] == 1)) & pbp['defteam'].notna() & pbp['epa'].notna()]
def_str = d.groupby(['season', 'defteam'])['epa'].mean().rename('def_epa_allowed').reset_index()
lg = d.groupby('season')['epa'].mean().rename('lg_epa').reset_index()
def_str = def_str.merge(lg, on='season')
def_str['def_adj'] = def_str['def_epa_allowed'] - def_str['lg_epa']   # <0 = good defense

# per-QB-season: mean opponent def_adj over their action plays
plays = pbp[((pbp['pass'] == 1) | (pbp['rush'] == 1))].copy()
plays['qb_id'] = plays['passer_player_id'].fillna(plays['rusher_player_id'])
plays = plays[plays['qb_id'].notna() & plays['qb_epa'].notna() & plays['down'].notna()]
plays = plays.merge(def_str[['season', 'defteam', 'def_adj']], on=['season', 'defteam'], how='left')
opp = plays.groupby(['season', 'qb_id'])['def_adj'].mean().rename('opp_def_adj').reset_index()
m = m.merge(opp, on=['season', 'qb_id'], how='left')
m['opp_def_adj'] = m['opp_def_adj'].fillna(0)

y = m['qbr_total'].values
seasons = m['season'].values

def loso_eval(name, Xcols, transform=None):
    """Leave-one-season-out CV."""
    X = m[Xcols].values
    preds = np.zeros(len(m))
    for s in np.unique(seasons):
        tr, te = seasons != s, seasons == s
        mod = LinearRegression().fit(X[tr], y[tr])
        preds[te] = mod.predict(X[te])
    preds = np.clip(preds, 0, 100)
    r = np.corrcoef(preds, y)[0, 1]
    mae = np.abs(preds - y).mean()
    # full-sample coefficients for reporting
    full = LinearRegression().fit(X, y)
    coefs = ", ".join(f"{c}={b:+.3f}" for c, b in zip(Xcols, full.coef_))
    print(f"{name:38s} r={r:.3f} R2={r**2:.3f} MAE={mae:4.1f}  | int={full.intercept_:+.2f} {coefs}")
    return preds, r, mae

print("=== Leave-one-season-out CV predicting official Total QBR (n=%d) ===" % len(m))
loso_eval("EPA/play only", ['epa_per_play'])
loso_eval("clutch-wtd EPA/play", ['epa_cw_floor'])
loso_eval("clutch-wtd EPA + CPOE", ['epa_cw_floor', 'cpoe'])
loso_eval("clutch-wtd EPA + CPOE + success", ['epa_cw_floor', 'cpoe', 'success_rate'])
loso_eval("clutch EPA + CPOE + succ + ANY/A", ['epa_cw_floor', 'cpoe', 'success_rate', 'anya'])
p_full, r_full, mae_full = loso_eval(
    "  + opponent adj", ['epa_cw_floor', 'cpoe', 'success_rate', 'anya', 'opp_def_adj'])
loso_eval("EPA + CPOE (dakota-style inputs)", ['epa_per_play', 'cpoe'])

# ---------- Non-regression, fully transparent option: percentile of clutch EPA ----------
print("\n=== Transparent scaling options (no fitted coefficients) ===")
for col in ['epa_cw_floor', 'epa_per_play']:
    pct = rankdata(m[col]) / len(m) * 100
    print(f"percentile rank of {col:16s}  r={np.corrcoef(pct, y)[0,1]:.3f}  MAE={np.abs(pct-y).mean():4.1f}")

# z-score -> normal CDF -> 0-100 (pooled across all seasons)
z = (m['epa_cw_floor'] - m['epa_cw_floor'].mean()) / m['epa_cw_floor'].std()
cdf = norm.cdf(z) * 100
print(f"normal-CDF of z(clutch EPA)          r={np.corrcoef(cdf, y)[0,1]:.3f}  MAE={np.abs(cdf-y).mean():4.1f}")

# logistic map fit on a single input (ESPN-style "logistic" scaling)
from scipy.optimize import curve_fit
def logi(x, a, b): return 100 / (1 + np.exp(-(a + b * x)))
popt, _ = curve_fit(logi, m['epa_cw_floor'].values, y, p0=[0, 5])
lp = logi(m['epa_cw_floor'].values, *popt)
print(f"logistic 100/(1+exp(-({popt[0]:.3f}+{popt[1]:.3f}*x))) r={np.corrcoef(lp,y)[0,1]:.3f} MAE={np.abs(lp-y).mean():4.1f}")

m['pred_qbr'] = p_full
print("\n=== Largest residuals (own composite - official QBR) ===")
m['resid'] = m['pred_qbr'] - m['qbr_total']
cols = ['season', 'name_display', 'qbr_total', 'pred_qbr', 'resid', 'epa_cw_floor', 'cpoe']
print(m.reindex(m['resid'].abs().sort_values(ascending=False).index)[cols].head(8).to_string(index=False))
m.to_parquet('season_qb_scored.parquet')
