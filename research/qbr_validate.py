import pandas as pd, numpy as np, warnings, re
warnings.filterwarnings('ignore')

pbp = pd.read_parquet('pbp_full.parquet')
pbp = pbp[pbp['season_type'] == 'REG'].copy()

# QB "action plays": pass attempts, sacks, scrambles, designed runs by the passer/rusher
pbp['qb_id'] = pbp['passer_player_id'].fillna(pbp['rusher_player_id'])
pbp['qb_name'] = pbp['passer_player_name'].fillna(pbp['rusher_player_name'])
plays = pbp[(pbp['pass'] == 1) | (pbp['rush'] == 1)].copy()
plays = plays[plays['qb_id'].notna() & plays['qb_epa'].notna() & plays['down'].notna()]

# --- QBR-style transforms (cfb_qbr recipe: floor EPA, fumble penalty, WP clutch weights)
plays['epa_floor45'] = plays['qb_epa'].clip(lower=-4.5)      # dakota convention
plays['epa_qbr'] = plays['qb_epa'].clip(lower=-5.0)          # cfb_qbr convention
plays.loc[plays['fumble'] == 1, 'epa_qbr'] = -3.5

wp = plays['wp']
w = np.ones(len(plays))
w[(wp < 0.1) | (wp > 0.9)] = 0.6
w[((wp >= 0.1) & (wp < 0.2)) | ((wp > 0.8) & (wp <= 0.9))] = 0.9
plays['clutch_w'] = np.where(np.isnan(wp), 1.0, w)

# ANY/A pieces
plays['is_att'] = (plays['pass_attempt'] == 1) & (plays['sack'] == 0) & (plays['two_point_attempt'] != 1)
plays['is_sack'] = plays['sack'] == 1
plays['pass_yds'] = np.where(plays['is_att'] & (plays['complete_pass'] == 1), plays['yards_gained'], 0)
plays['sack_yds'] = np.where(plays['is_sack'], plays['yards_gained'], 0)
plays['ptd'] = (plays['pass_touchdown'] == 1) & plays['is_att']
plays['int'] = (plays['interception'] == 1)

def agg(g):
    n = len(g)
    cw = g['clutch_w']
    att = g['is_att'].sum(); sk = g['is_sack'].sum()
    d = {
        'n_plays': n,
        'attempts': att,
        'sacks': sk,
        'epa_per_play': g['epa_floor45'].sum() / n,
        'epa_per_play_raw': g['qb_epa'].mean(),
        'cpoe': g['cpoe'].mean(skipna=True),
        'success_rate': g['success'].mean(),
        # clutch-weighted, QBR-style EPA per action play
        'qbr_epa_cw': np.average(g['epa_qbr'], weights=cw),
        'epa_cw_floor': np.average(g['epa_floor45'], weights=cw),
        'anya_num': g['pass_yds'].sum() + 20 * g['ptd'].sum() - 45 * g['int'].sum() + g['sack_yds'].sum(),
        'anya_den': att + sk,
    }
    return pd.Series(d)

season_qb = plays.groupby(['season', 'qb_id', 'qb_name']).apply(agg).reset_index()
season_qb['cpoe'] = season_qb['cpoe'].fillna(0)
season_qb['anya'] = season_qb['anya_num'] / season_qb['anya_den']

# --- official QBR
qbr = pd.read_csv('qbr_nflverse.csv')
qbr = qbr[(qbr['season_type'] == 'Regular') & (qbr['season'].between(2021, 2024))].copy()

def norm_short(s):
    # "P. Mahomes" -> "P.Mahomes"
    return re.sub(r'\s+', '', str(s))

qbr['join_name'] = qbr['name_short'].map(norm_short)
season_qb['join_name'] = season_qb['qb_name'].map(norm_short)

# ESPN's file includes non-QBs who threw a pass (e.g. WR Roman Wilson, 34 plays),
# which collide on abbreviated names. Keep the highest-volume passer per name-season.
qbr = qbr[qbr['qb_plays'] >= 100]
qbr = qbr.sort_values('qb_plays').drop_duplicates(['season', 'join_name'], keep='last')

m = season_qb.merge(
    qbr[['season', 'join_name', 'qbr_total', 'qbr_raw', 'qb_plays', 'epa_total', 'pts_added', 'name_display']],
    on=['season', 'join_name'], how='inner'
)
# qualified-ish sample
m = m[m['attempts'] >= 150].copy()
print(f"Matched QB-seasons (>=150 att, 2021-2024): {len(m)}")
print(f"Unmatched official QBR rows w/ >=150 qb_plays: "
      f"{len(qbr[qbr['qb_plays']>=200]) - m['join_name'].nunique()}")

cands = ['epa_per_play', 'epa_per_play_raw', 'qbr_epa_cw', 'epa_cw_floor', 'cpoe',
         'success_rate', 'anya']
print("\n=== Pearson r with official Total QBR (season, 2021-2024) ===")
rows = []
for c in cands:
    r = m[c].corr(m['qbr_total'])
    rr = m[c].corr(m['qbr_raw'])
    rows.append((c, r, r**2, rr))
for c, r, r2, rr in sorted(rows, key=lambda x: -abs(x[1])):
    print(f"{c:20s} r={r:6.3f}  R2={r2:6.3f}   (vs raw QBR r={rr:6.3f})")

m.to_parquet('season_qb_merged.parquet')
print("\nsaved season_qb_merged.parquet")
