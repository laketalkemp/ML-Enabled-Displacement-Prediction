"""Modeled vs observed province hazard archetypes (December analysis, run Nov 3, 2026).

The observed archetypes (stats_province.py) cluster each province's mix of EM-DAT records plus ERA5-Land drought
months. CORDEX cannot simulate typhoons or disaster records, so the modeled side clusters the physical hazard climate
instead, and we ask three questions:

  1. Does the recorded hazard mix follow the physical climate? ERA5-Land climate types vs the EM-DAT archetypes.
  2. Do the regional models reproduce the climate types? CORDEX historical (6 GCM-driven runs per region, ensemble
     median per unit, 1991-2020) vs ERA5-Land on the same monthly features.
  3. How do the modeled types move? Deltas from each run (window minus its own 1991-2020) are added to the ensemble
     baseline and each unit is assigned to the nearest baseline type; a move counts as agreed when at least 5 of the
     6 runs make it (the projection convention).

Feature sets (z-scored within each source, so a uniform model wet or warm bias does not move the clusters):
  monthly (both sources): log annual precipitation, wettest-quarter share, year-to-year CV of annual precipitation,
                          mean temperature, seasonal temperature range
  extended (models only): the monthly set with Rx5day (log) and CDD (log) added and the 95th percentile of daily
                          temperature in place of mean temperature

Outputs: CORDEX/ERA5-Land-only tables in data/processed/cordex/ (shareable); anything compared with the EM-DAT
archetypes in data/processed/emdat/stats/province/ (internal, EM-DAT licence).
    python scripts/stats_cordex_archetypes.py --units /home/claude/cordex_units
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import adjusted_rand_score, balanced_accuracy_score, silhouette_score  # noqa: E402
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_predict  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import archetypes as A  # noqa: E402
from hvd.stats import cordex as X  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--units", default="data/raw/cordex_units")
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--boot", type=int, default=200)
ap.add_argument("--reuse", action="store_true", help="reuse archetype_features_by_unit_and_run.csv from an earlier run")
args = ap.parse_args()
OUT_C = paths.PROCESSED / "cordex"
OUT_E = paths.PROCESSED / "emdat" / "stats" / "province"
REGIONS = ("PHL", "AFG", "BGD")
MONTHLY = ["log_precip", "wet_quarter_share", "precip_cv", "tas_mean", "tas_range"]
EXTENDED = ["log_precip", "wet_quarter_share", "precip_cv", "tas_p95", "tas_range", "log_rx5day", "log_cdd"]
WINDOWS = {"1991-2020": (1991, 2020), **X.FUT}
inv = X.inventory(args.units)


def wet_quarter(clim: pd.DataFrame) -> pd.Series:
    """Largest share of the annual total falling in three consecutive calendar months (wrapping Dec-Jan)."""
    a = clim.to_numpy()
    q = np.stack([a[[i, (i + 1) % 12, (i + 2) % 12]].sum(0) for i in range(12)])
    return pd.Series(q.max(0) / a.sum(0), index=clim.columns)


def monthly_features(pm: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    ann = pm.groupby(pm.index.year).sum(min_count=12)
    clim = pm.groupby(pm.index.month).mean()
    tclim = tm.groupby(tm.index.month).mean()
    return pd.DataFrame({"log_precip": np.log(ann.mean()), "wet_quarter_share": wet_quarter(clim),
                         "precip_cv": ann.std() / ann.mean(), "tas_mean": tclim.mean(),
                         "tas_range": tclim.max() - tclim.min()})


def daily_features(pr: pd.DataFrame, tas: pd.DataFrame, a: int, b: int) -> pd.DataFrame:
    yp = pr.index.str.slice(0, 4).astype(int)
    yt = tas.index.str.slice(0, 4).astype(int)
    p, t = pr[(yp >= a) & (yp <= b)], tas[(yt >= a) & (yt <= b)]
    f = monthly_features(X.monthly(p, "sum"), X.monthly(t, "mean"))
    yrs = p.index.str.slice(0, 4).astype(int)
    rx5, cdd = [], []
    for y in np.unique(yrs):
        d = p[yrs == y]
        if len(d) < 300:
            continue
        rx5.append(d.rolling(5).sum().max())
        cdd.append(pd.Series(X._max_run(d.to_numpy() < 1), index=d.columns))
    f["log_rx5day"] = np.log(pd.concat(rx5, axis=1).mean(axis=1))
    f["log_cdd"] = np.log(pd.concat(cdd, axis=1).mean(axis=1).clip(lower=1))
    f["tas_p95"] = t.quantile(0.95)
    return f


# ------------------------------------------------------------------ observed (ERA5-Land monthly) ----
def era5(iso, col):
    d = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_monthly_drought_indices_1991_2025.csv", usecols=["unit_id", "date", col])
    m = d.pivot(index="date", columns="unit_id", values=col)
    m.index = pd.PeriodIndex(pd.to_datetime(m.index), freq="M")
    return m[(m.index.year >= 1991) & (m.index.year <= 2020)]


obs = pd.concat([monthly_features(era5(i, "precip_mm"), era5(i, "t2m_c")).assign(region=i) for i in REGIONS])
obs.index.name = "unit_id"

# ------------------------------------------------------------------ modeled (CORDEX GCM-driven runs) ----
rows = []
FEAT = OUT_C / "archetype_features_by_unit_and_run.csv"
for iso in ([] if args.reuse and FEAT.exists() else REGIONS):
    s = inv[(inv.iso == iso) & (inv.gcm != "era_interim")]
    for rcm, gcm in s[["rcm", "gcm"]].drop_duplicates().itertuples(index=False):
        for scen in ("rcp_2_6", "rcp_8_5"):
            pr = X.run_series(inv, iso, "pr", rcm, gcm, scen)
            tas = X.run_series(inv, iso, "tas", rcm, gcm, scen)
            if pr.empty or tas.empty:
                continue
            for win, (a, b) in WINDOWS.items():
                if win == "1991-2020" and scen == "rcp_2_6":
                    continue                                   # the baseline is shared by both scenarios
                f = daily_features(pr, tas, a, b)
                rows.append(f.reset_index(names="unit_id").assign(
                    region=iso, rcm=rcm, gcm=gcm, scenario="historical" if win == "1991-2020" else scen, window=win))
        print(iso, rcm, gcm, flush=True)
if rows:
    mod_all = pd.concat(rows, ignore_index=True)
    mod_all.to_csv(FEAT, index=False)
else:
    mod_all = pd.read_csv(FEAT)
base_runs = mod_all[mod_all.window == "1991-2020"].set_index(["unit_id", "rcm", "gcm"])
mod = base_runs.groupby("unit_id")[EXTENDED + ["tas_mean"]].median()
mod["region"] = base_runs.groupby("unit_id").region.first()
units = obs.index.intersection(mod.index)
obs, mod = obs.loc[units], mod.loc[units]


# ------------------------------------------------------------------ clustering ----
def zscore(F):
    return (F - F.mean()) / F.std()


def kfit(F, k, seed=42):
    km = KMeans(k, n_init=50, random_state=seed).fit(zscore(F))
    return pd.Series(km.labels_, index=F.index), km


def stability(F, labels, k, n_boot):
    rng = np.random.default_rng(42)
    Z = zscore(F)
    s = []
    for _ in range(n_boot):
        idx = rng.choice(len(Z), len(Z), replace=True)
        km = KMeans(k, n_init=10, random_state=int(rng.integers(1e9))).fit(Z.iloc[idx])
        s.append(adjusted_rand_score(labels, km.predict(Z)))
    return float(np.mean(s))


def k_table(F, name):
    out = []
    for k in range(2, 7):
        lab, km = kfit(F, k)
        out.append({"features": name, "k": k, "silhouette": silhouette_score(zscore(F), lab),
                    "stability_ari": stability(F, lab, k, max(50, args.boot // 4))})
    return out


def order_by(lab, F, col="log_precip"):
    """Relabel clusters 1..k from wettest to driest so tables read the same across sources."""
    rank = F.groupby(lab)[col].mean().sort_values(ascending=False)
    return lab.map({c: i + 1 for i, c in enumerate(rank.index)})


ksel = pd.DataFrame(k_table(obs[MONTHLY], "era5land_monthly") + k_table(mod[MONTHLY], "cordex_monthly")
                    + k_table(mod[EXTENDED], "cordex_extended"))
ksel.to_csv(OUT_C / "archetypes_modeled_k_selection.csv", index=False)

K = args.k
lab_o, _ = kfit(obs[MONTHLY], K)
lab_m, _ = kfit(mod[MONTHLY], K)
lab_x, km_x = kfit(mod[EXTENDED], K)
lab_o, lab_m = order_by(lab_o, obs), order_by(lab_m, mod)
raw_x = lab_x.copy()
lab_x = order_by(lab_x, mod)
remap_x = dict(zip(raw_x, lab_x))
stab = {"era5land_monthly": stability(obs[MONTHLY], lab_o, K, args.boot),
        "cordex_monthly": stability(mod[MONTHLY], lab_m, K, args.boot),
        "cordex_extended": stability(mod[EXTENDED], lab_x, K, args.boot)}
types = pd.DataFrame({"region": obs.region, "era5land_type": lab_o, "cordex_type": lab_m, "cordex_extended_type": lab_x})
types.to_csv(OUT_C / "archetypes_modeled_units.csv")
prof = pd.concat([
    obs.assign(type=lab_o).groupby("type")[MONTHLY].mean().assign(source="era5land_monthly"),
    mod.assign(type=lab_m).groupby("type")[MONTHLY].mean().assign(source="cordex_monthly"),
    mod.assign(type=lab_x).groupby("type")[EXTENDED].mean().assign(source="cordex_extended")])
cnt = pd.concat([types.groupby(["era5land_type", "region"]).size().unstack(fill_value=0).assign(source="era5land_monthly"),
                 types.groupby(["cordex_type", "region"]).size().unstack(fill_value=0).assign(source="cordex_monthly"),
                 types.groupby(["cordex_extended_type", "region"]).size().unstack(fill_value=0).assign(source="cordex_extended")])
cnt.index.name = prof.index.name = "type"
prof = prof.reset_index().merge(cnt.reset_index(), on=["source", "type"])
for c in ("log_precip", "log_rx5day", "log_cdd"):
    if c in prof:
        prof[c.replace("log_", "") + "_mm" if c != "log_cdd" else "cdd_days"] = np.exp(prof[c])
prof.to_csv(OUT_C / "archetypes_modeled_profiles.csv", index=False)

# ------------------------------------------------------------------ comparisons ----
emd = pd.read_csv(OUT_E / "archetypes_units.csv").set_index("unit_id")
emd = emd.loc[units]
emd_lab = emd.archetype.rename("emdat_archetype")


def cmp(a, b, name):
    r = A.compare_with(a, b)
    ab = types.region.isin(["AFG", "BGD"])
    sub = A.compare_with(a[ab], b[ab])
    return {"comparison": name, "n": r["n"], "cramers_v": r["cramers_v"], "ari": r["ari"], "p": r["p"],
            "afg_bgd_n": sub["n"], "afg_bgd_cramers_v": sub["cramers_v"], "afg_bgd_ari": sub["ari"], "afg_bgd_p": sub["p"]}


comp = pd.DataFrame([
    cmp(types.cordex_type, types.era5land_type, "CORDEX monthly types vs ERA5-Land types (model fidelity)"),
    cmp(types.era5land_type, emd_lab, "ERA5-Land types vs EM-DAT archetypes"),
    cmp(types.cordex_type, emd_lab, "CORDEX monthly types vs EM-DAT archetypes"),
    cmp(types.cordex_extended_type, emd_lab, "CORDEX extended types vs EM-DAT archetypes"),
    cmp(types.region, emd_lab, "Region alone vs EM-DAT archetypes")])
comp.to_csv(OUT_E / "archetypes_modeled_vs_observed.csv", index=False)
xt = {n: pd.crosstab(types[c], emd_lab) for n, c in (("era5land", "era5land_type"), ("cordex", "cordex_type"),
                                                       ("cordex_extended", "cordex_extended_type"))}
pd.concat(xt, names=["source", "type"]).to_csv(OUT_E / "archetypes_modeled_vs_observed_crosstab.csv")

# Can the physical climate tell the two drought + flood archetypes apart, beyond region? (Bangladesh and Afghanistan)
ab = types.region.isin(["AFG", "BGD"]) & emd_lab.isin([2, 3])
y = emd_lab[ab]
reg = pd.get_dummies(types.region[ab], drop_first=True).astype(float)
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=20, random_state=42)


def bacc(Xf):
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
    scores = []
    for tr, te in cv.split(Xf, y):
        clf.fit(Xf.iloc[tr], y.iloc[tr])
        scores.append(balanced_accuracy_score(y.iloc[te], clf.predict(Xf.iloc[te])))
    return float(np.mean(scores)), float(np.std(scores))


sup = []
for name, F in (("region only", reg), ("ERA5-Land monthly", obs.loc[ab, MONTHLY]),
                ("ERA5-Land monthly + region", pd.concat([obs.loc[ab, MONTHLY], reg], axis=1)),
                ("CORDEX monthly", mod.loc[ab, MONTHLY]), ("CORDEX extended", mod.loc[ab, EXTENDED]),
                ("CORDEX extended + region", pd.concat([mod.loc[ab, EXTENDED], reg], axis=1))):
    m_, s_ = bacc(F)
    sup.append({"features": name, "n": int(len(y)), "balanced_accuracy": m_, "sd": s_})
sup = pd.DataFrame(sup)
sup.to_csv(OUT_E / "archetypes_modeled_classifier.csv", index=False)

# Within each region, which physical features differ between the two drought + flood archetypes? (Mann-Whitney, BH)
from scipy.stats import mannwhitneyu  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402
wr = []
for iso in ("AFG", "BGD"):
    m2 = (types.region == iso) & (emd_lab == 2)
    m3 = (types.region == iso) & (emd_lab == 3)
    for src, F, cols in (("era5land", obs, MONTHLY), ("cordex", mod, EXTENDED)):
        for c in cols:
            u, pv = mannwhitneyu(F.loc[m2, c], F.loc[m3, c])
            wr.append({"region": iso, "source": src, "feature": c, "n_arch2": int(m2.sum()), "n_arch3": int(m3.sum()),
                       "median_arch2": F.loc[m2, c].median(), "median_arch3": F.loc[m3, c].median(), "p": pv})
wr = pd.DataFrame(wr)
wr["q"] = multipletests(wr.p, method="fdr_bh")[1]
wr.to_csv(OUT_E / "archetypes_modeled_within_region_tests.csv", index=False)

# ------------------------------------------------------------------ projected moves between modeled types ----
mu, sd = mod[EXTENDED].mean(), mod[EXTENDED].std()
cent = km_x.cluster_centers_
base_z = ((mod[EXTENDED] - mu) / sd).to_numpy()
d_base = np.linalg.norm(base_z[:, None, :] - cent[None], axis=2).min(1)
novel_cut = float(np.quantile(d_base, 0.95))


def assign(F):
    z = ((F[EXTENDED] - mu) / sd).to_numpy()
    d = np.linalg.norm(z[:, None, :] - cent[None], axis=2)
    return pd.Series([remap_x[i] for i in d.argmin(1)], index=F.index), pd.Series(d.min(1), index=F.index)


fut_rows = []
for scen in ("rcp_2_6", "rcp_8_5"):
    for win in X.FUT:
        f = mod_all[(mod_all.scenario == scen) & (mod_all.window == win)].set_index(["unit_id", "rcm", "gcm"])
        delta = (f[EXTENDED] - base_runs.loc[f.index, EXTENDED])
        per_run = []
        for (rcm, gcm), dd in delta.groupby(level=["rcm", "gcm"]):
            dd = dd.droplevel(["rcm", "gcm"])
            dd = dd.loc[dd.index.intersection(units)]           # each run covers one region
            lab, _ = assign(mod.loc[dd.index, EXTENDED] + dd)
            per_run.append(lab.rename(f"{rcm}|{gcm}"))
        per_run = pd.concat(per_run, axis=1).reindex(units)
        med = delta.groupby(level="unit_id").median().loc[units]
        lab, dist = assign(mod.loc[units, EXTENDED] + med)
        have = per_run.notna()
        moved_runs = (per_run.ne(lab_x, axis=0) & have).sum(axis=1)
        to_same = (per_run.eq(lab, axis=0) & have).sum(axis=1)
        fut_rows.append(pd.DataFrame({"unit_id": units, "region": types.region.values, "scenario": scen, "window": win,
                                      "baseline_type": lab_x.values, "projected_type": lab.values,
                                      "runs": have.sum(axis=1).values, "runs_moving": moved_runs.values,
                                      "runs_agreeing_on_projected_type": to_same.values,
                                      "distance_z": dist.values, "no_current_analogue": (dist > novel_cut).values}))
base_novel = pd.DataFrame({"unit_id": units, "region": types.region.values, "scenario": "historical", "window": "1991-2020",
                           "baseline_type": lab_x.values, "projected_type": lab_x.values, "runs": 6, "runs_moving": 0,
                           "runs_agreeing_on_projected_type": 6, "distance_z": d_base, "no_current_analogue": d_base > novel_cut})
fut = pd.concat([base_novel] + fut_rows, ignore_index=True)
fut["moves"] = fut.baseline_type != fut.projected_type
fut["agreed_move"] = fut.moves & (fut.runs_agreeing_on_projected_type >= 5)
fut.to_csv(OUT_C / "archetypes_modeled_future_shift.csv", index=False)
fsum = (fut.groupby(["scenario", "window", "region"])
        .agg(units=("unit_id", "size"), moves=("moves", "sum"), agreed_moves=("agreed_move", "sum"),
             no_current_analogue=("no_current_analogue", "sum")).reset_index())
fsum.to_csv(OUT_C / "archetypes_modeled_future_shift_summary.csv", index=False)
trans = fut[fut.moves].groupby(["scenario", "window", "region", "baseline_type", "projected_type"]).size().rename("units").reset_index()
trans.to_csv(OUT_C / "archetypes_modeled_future_transitions.csv", index=False)

summary = {"units": int(len(units)), "k": K, "stability_ari": stab, "novelty_cut_z": novel_cut,
           "comparisons": comp.to_dict("records"), "classifier": sup.to_dict("records"),
           "future": fsum.to_dict("records")}
(OUT_E / "archetypes_modeled_summary.json").write_text(json.dumps(summary, indent=1, default=float))
pd.set_option("display.width", 220, "display.max_columns", 30)
print(ksel.round(3).to_string())
print(prof.round(3).to_string())
print(comp.round(3).to_string())
for n, t in xt.items():
    print(n, "\n", t)
print(sup.round(3).to_string())
print(json.dumps(stab, indent=1))
print(wr.round(4).to_string())
print(fsum.to_string())
print(trans.to_string())

# ------------------------------------------------------------------ disagreement screen (work plan: "disagreement flags
# likely under-reporting"). Only where the models place rainfall well across units (pattern correlation with ERA5-Land
# about 0.85 in Afghanistan and Bangladesh, 0.23 in the Philippines). Flood records vs heavy-rain proxies, within region.
scr = []
for iso in ("AFG", "BGD"):
    tab = pd.read_csv(OUT_E / f"{iso.lower()}_unit_table.csv", index_col=0)
    j = pd.DataFrame({"flood_events": tab.events_flood,
                      "rx5day_mm_model": np.exp(mod.loc[mod.region == iso, "log_rx5day"]),
                      "wet_quarter_mm_obs": np.exp(obs.loc[obs.region == iso, "log_precip"]) * obs.loc[obs.region == iso, "wet_quarter_share"]}).dropna()
    j["region"] = iso
    j["name"] = emd.name.reindex(j.index)
    j["hazard_rank"] = j[["rx5day_mm_model", "wet_quarter_mm_obs"]].rank(pct=True).mean(axis=1)
    j["record_rank"] = j.flood_events.rank(pct=True)
    j["flag_high_hazard_few_records"] = (j.hazard_rank >= 2 / 3) & (j.record_rank <= 1 / 3)
    scr.append(j)
scr = pd.concat(scr)
from scipy.stats import spearmanr  # noqa: E402
rho = [{"region": iso, "proxy": c, **dict(zip(("rho", "p"), spearmanr(g[c], g.flood_events)))}
       for iso, g in scr.groupby("region") for c in ("rx5day_mm_model", "wet_quarter_mm_obs")]
scr.to_csv(OUT_E / "archetypes_modeled_flood_record_screen.csv")
pd.DataFrame(rho).to_csv(OUT_E / "archetypes_modeled_flood_record_rho.csv", index=False)
print(pd.DataFrame(rho).round(3).to_string())
print(scr[scr.flag_high_hazard_few_records][["region", "name", "flood_events", "rx5day_mm_model", "wet_quarter_mm_obs"]].round(1).to_string())
