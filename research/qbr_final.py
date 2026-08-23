import pandas as pd, numpy as np, warnings
from scipy.optimize import curve_fit
from scipy.stats import spearmanr
warnings.filterwarnings('ignore')

m = pd.read_parquet('season_qb_scored.parquet')
y = m['qbr_total'].values
x = m['epa_cw_floor'].values
seasons = m['season'].values

def logi(x, a, b): return 100 / (1 + np.exp(-(a + b * x)))

# Leave-one-season-out CV of the logistic map
preds = np.zeros(len(m))
for s in np.unique(seasons):
    tr, te = seasons != s, seasons == s
    p, _ = curve_fit(logi, x[tr], y[tr], p0=[0, 4])
    preds[te] = logi(x[te], *p)

r = np.corrcoef(preds, y)[0, 1]
rho = spearmanr(preds, y).statistic
mae = np.abs(preds - y).mean()
rmse = np.sqrt(((preds - y) ** 2).mean())
print("=== RECOMMENDED FORMULA: leave-one-season-out CV (n=%d, 2021-24) ===" % len(m))
print(f"Pearson r  = {r:.3f}   (R2 = {r**2:.3f})")
print(f"Spearman r = {rho:.3f}")
print(f"MAE        = {mae:.2f} QBR points")
print(f"RMSE       = {rmse:.2f} QBR points")
print(f"within  5 QBR pts: {(np.abs(preds-y)<=5).mean()*100:.0f}%")
print(f"within 10 QBR pts: {(np.abs(preds-y)<=10).mean()*100:.0f}%")

pfull, _ = curve_fit(logi, x, y, p0=[0, 4])
print(f"\nFull-sample coefficients: a={pfull[0]:.4f}, b={pfull[1]:.4f}")
print(f"  cQBR = 100 / (1 + exp(-({pfull[0]:.4f} + {pfull[1]:.4f} * clutch_epa_per_play)))")

# sanity: what EPA/play maps to what score
print("\nMapping check:")
for v in [-0.25, -0.15, -0.05, 0.0, 0.05, 0.10, 0.20, 0.30, 0.40]:
    print(f"  clutch EPA/play {v:+.2f} -> cQBR {logi(v,*pfull):5.1f}")

# top/bottom of our metric vs official
m['cQBR'] = logi(x, *pfull)
m['off_rank'] = m.groupby('season')['qbr_total'].rank(ascending=False)
m['our_rank'] = m.groupby('season')['cQBR'].rank(ascending=False)
print("\n=== 2024 leaderboard: ours vs official ===")
s24 = m[m.season == 2024].sort_values('cQBR', ascending=False).head(12)
print(s24[['name_display', 'cQBR', 'qbr_total', 'our_rank', 'off_rank', 'epa_cw_floor']]
      .to_string(index=False, float_format=lambda v: f"{v:.1f}"))

print("\nMean |rank difference| within season: %.1f places" %
      (m['our_rank'] - m['off_rank']).abs().mean())
