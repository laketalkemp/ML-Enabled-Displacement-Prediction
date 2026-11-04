"""CORDEX modeled vs observed hazard, and future change (statistical analysis plan, Aim 3 item 6).

    python scripts/stats_cordex.py --units "<grant folder>/CORDEX/units"

Works with whatever pieces have been downloaded so far (scripts/download_cordex.py); missing runs are skipped
and listed in the summary. Outputs: data/processed/cordex/ (CORDEX-derived, no EM-DAT content).
"""
import argparse
import itertools
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
from scipy import stats  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import cordex as X  # noqa: E402
from hvd.stats import province as P, spatial as S  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--units", default="data/raw/cordex_units")
args = ap.parse_args()
OUT = paths.PROCESSED / "cordex"
OUT.mkdir(parents=True, exist_ok=True)
inv = X.inventory(args.units)
if inv.empty:
    raise SystemExit(f"No CORDEX unit files under {args.units}")
inv.drop(columns="file").to_csv(OUT / "inventory.csv", index=False)
summary = {"pieces": int(len(inv))}


def era5_monthly(iso, col="precip_mm"):
    d = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_monthly_drought_indices_1991_2025.csv", usecols=["unit_id", "date", col])
    m = d.pivot(index="date", columns="unit_id", values=col)
    m.index = pd.PeriodIndex(pd.to_datetime(m.index), freq="M")
    return m


def days_per_month(daily):
    n = daily.groupby(daily.index.str.slice(0, 7)).size()
    n.index = pd.PeriodIndex(n.index, freq="M")
    return n


def in_years(x, a, b):
    return x[(x.index.year >= a) & (x.index.year <= b)]


share = lambda x: (x <= -1).where(x.notna()).mean()  # noqa: E731  (share of months in drought; missing months excluded)
eval_rows, eval_t_rows, clim_rows, change_rows, unit_change, moran_rows = [], [], [], [], [], []
for iso in P.REGIONS:
    obs = era5_monthly(iso)
    obs_t = era5_monthly(iso, "t2m_c")
    lat = P.load_units(iso).set_index("unit_id").geometry.representative_point().y
    pr = inv[(inv.iso == iso) & (inv["var"] == "pr")]
    has_tas = not inv[(inv.iso == iso) & (inv["var"] == "tas")].empty
    if pr.empty:
        continue
    # ---- evaluation runs (ERA-Interim driven): month-by-month agreement with ERA5-Land, 1991-2016
    for rcm in sorted(pr[pr.exp == "evaluation"].rcm.unique()):
        d = X.run_series(inv, iso, "pr", rcm, "era_interim", "evaluation")
        if d.empty:
            continue
        m = X.monthly(d, "sum")
        ev = X.evaluate_monthly(m, obs, 1991, 2016).assign(region=iso, rcm=rcm)
        eval_rows.append(ev)
        if has_tas:
            t = X.monthly(X.run_series(inv, iso, "tas", rcm, "era_interim", "evaluation"), "mean")
            idx = in_years(t, 1991, 2016).index.intersection(obs_t.index)
            mt, ot = t.loc[idx], obs_t.loc[idx, t.columns.intersection(obs_t.columns)]
            mt = mt[ot.columns]
            am = mt - mt.groupby(mt.index.month).transform("mean")
            ao = ot - ot.groupby(ot.index.month).transform("mean")
            eval_t_rows.append(pd.DataFrame({"unit_id": ot.columns, "bias_c": (mt.mean() - ot.mean()).values,
                                             "anomaly_corr": [np.corrcoef(am[u], ao[u])[0, 1] for u in ot.columns]}).assign(region=iso, rcm=rcm))
    # ---- GCM-driven runs
    runs = pr[pr.gcm != "era_interim"][["rcm", "gcm"]].drop_duplicates().itertuples(index=False)
    for rcm, gcm in runs:
        base = X.run_series(inv, iso, "pr", rcm, gcm, "observed")
        if base.empty:
            continue
        mb = X.monthly(base, "sum")
        ob = obs[(obs.index.year >= 1991) & (obs.index.year <= 2020)]
        mb_b = mb[(mb.index.year >= 1991) & (mb.index.year <= 2020)]
        units = ob.columns.intersection(mb.columns)
        clim_m, clim_o = mb_b[units].mean() * 12, ob[units].mean() * 12
        seas_m = mb_b[units].groupby(mb_b.index.month).mean().mean(axis=1)
        seas_o = ob[units].groupby(ob.index.month).mean().mean(axis=1)
        ann_m = mb_b[units].groupby(mb_b.index.year).sum().mean(axis=1)
        ann_o = ob[units].groupby(ob.index.year).sum().mean(axis=1)
        row = {"region": iso, "rcm": rcm, "gcm": gcm, "years_baseline": int(mb_b.index.year.nunique()),
               "annual_bias_pct": float((clim_m.mean() / clim_o.mean() - 1) * 100),
               "pattern_corr_units": float(np.corrcoef(clim_m, clim_o)[0, 1]),
               "seasonal_cycle_corr": float(np.corrcoef(seas_m, seas_o)[0, 1]),
               "interannual_sd_ratio": float(ann_m.std() / ann_o.std())}
        tb = X.run_series(inv, iso, "tas", rcm, gcm, "observed") if has_tas else pd.DataFrame()
        if not tb.empty:
            tbm = in_years(X.monthly(tb, "mean"), 1991, 2020)[units]
            ot = in_years(obs_t, 1991, 2020)[units]
            row.update({"tas_bias_c": float(tbm.mean().mean() - ot.mean().mean()),
                        "tas_pattern_corr_units": float(np.corrcoef(tbm.mean(), ot.mean())[0, 1]),
                        "tas_seasonal_cycle_corr": float(np.corrcoef(tbm.groupby(tbm.index.month).mean().mean(axis=1),
                                                                     ot.groupby(ot.index.month).mean().mean(axis=1))[0, 1])})
            _, t95 = X.hot_days(tb)
        clim_rows.append(row)
        _, p95 = X.annual_extremes(base)
        for scen in ("rcp_2_6", "rcp_8_5"):
            d = X.run_series(inv, iso, "pr", rcm, gcm, scen)
            if d.empty or d.index.str.slice(0, 4).astype(int).max() < 2041:
                continue
            m = X.monthly(d, "sum")
            s = X.spi6(m)
            ex, _ = X.annual_extremes(d, p95)
            base_share = share(in_years(s, 1991, 2020))
            ann = m.groupby(m.index.year).sum(min_count=12)
            td = X.run_series(inv, iso, "tas", rcm, gcm, scen) if has_tas else pd.DataFrame()
            if not td.empty:
                tm = X.monthly(td, "mean")
                tann = tm.groupby(tm.index.year).mean()
                hd, _ = X.hot_days(td, t95)
                idx = m.index.intersection(tm.index)
                pet = X.thornthwaite(tm.loc[idx], days_per_month(td), lat)
                se = X.spei6(m.loc[idx], pet)
                se_base = share(in_years(se, 1991, 2020))
            for win, (a, b) in X.FUT.items():
                fs = s[(s.index.year >= a) & (s.index.year <= b)]
                if fs.index.year.nunique() < 20:
                    continue
                ch = {"drought_share_change_pp": (share(fs) - base_share) * 100,
                      "annual_precip_change_pct": (ann.loc[a:b].mean() / ann.loc[1991:2020].mean() - 1) * 100}
                for k in ("cdd", "rx5day", "r95p"):
                    e = ex[k]
                    ch[f"{k}_change_pct"] = (e.loc[a:b].mean() / e.loc[1991:2020].mean() - 1) * 100
                if not td.empty:
                    ch["tas_change_c"] = tann.loc[a:b].mean() - tann.loc[1991:2020].mean()
                    ch["hot_days_change"] = hd.loc[a:b].mean() - hd.loc[1991:2020].mean()
                    ch["spei_drought_share_change_pp"] = (share(in_years(se, a, b)) - se_base) * 100
                    ch["pet_change_pct"] = (in_years(pet, a, b).mean() / in_years(pet, 1991, 2020).mean() - 1) * 100
                for k, v in ch.items():
                    unit_change.append(pd.DataFrame({"unit_id": v.index, "value": v.values}).assign(
                        region=iso, rcm=rcm, gcm=gcm, scenario=scen, window=win, metric=k))
                    change_rows.append({"region": iso, "rcm": rcm, "gcm": gcm, "scenario": scen, "window": win,
                                        "metric": k, "regional_mean": float(v.mean())})

if eval_rows:
    ev = pd.concat(eval_rows)
    ev.to_csv(OUT / "evaluation_vs_era5land_by_unit.csv", index=False)
    ev.groupby(["region", "rcm"])[["bias_pct", "anomaly_corr", "spi6_corr", "drought_kappa"]].median().to_csv(OUT / "evaluation_vs_era5land_summary.csv")
if eval_t_rows:
    et = pd.concat(eval_t_rows)
    et.to_csv(OUT / "evaluation_tas_vs_era5land_by_unit.csv", index=False)
    et.groupby(["region", "rcm"])[["bias_c", "anomaly_corr"]].median().to_csv(OUT / "evaluation_tas_vs_era5land_summary.csv")
SCREEN_BIAS = 50   # sensitivity: drop GCM-driven runs whose 1991-2020 precipitation bias exceeds +-50%
screened_out = set()
if clim_rows:
    cl = pd.DataFrame(clim_rows)
    cl.to_csv(OUT / "historical_vs_era5land_climatology.csv", index=False)
    screened_out = {(r.region, r.rcm, r.gcm) for r in cl.itertuples() if abs(r.annual_bias_pct) > SCREEN_BIAS}
    summary["screened_out_runs"] = sorted("/".join(x) for x in screened_out)
if change_rows:
    cr = pd.DataFrame(change_rows)
    cr.to_csv(OUT / "future_change_regional_by_run.csv", index=False)
    uc = pd.concat(unit_change)
    uc.to_csv(OUT / "future_change_by_unit_and_run.csv", index=False)
    ens = []
    for (iso, scen, win, met), g in uc.groupby(["region", "scenario", "window", "metric"]):
        wide = g.pivot_table(index=["rcm", "gcm"], columns="unit_id", values="value")
        ag = X.agreement(wide)
        ag = ag.assign(region=iso, scenario=scen, window=win, metric=met)
        ens.append(ag.reset_index().rename(columns={"index": "unit_id"}))
    ens = pd.concat(ens)
    ens.to_csv(OUT / "future_change_ensemble_by_unit.csv", index=False)
    grp = ["region", "scenario", "window", "metric"]
    cr["agree_sign"] = np.sign(cr.regional_mean) == np.sign(cr.groupby(grp).regional_mean.transform("median"))
    reg = cr.groupby(grp).agg(median=("regional_mean", "median"), min=("regional_mean", "min"), max=("regional_mean", "max"),
                              count=("regional_mean", "size"), agree_sign=("agree_sign", "sum"))
    reg["units_robust_share"] = ens.groupby(grp).robust.mean()
    reg.to_csv(OUT / "future_change_ensemble_regional.csv")
    keep = ~cr.apply(lambda r: (r.region, r.rcm, r.gcm) in screened_out, axis=1)
    cr[keep].groupby(grp).regional_mean.agg(["median", "min", "max", "count"]).to_csv(OUT / "future_change_ensemble_regional_screened.csv")
    # hot spots of projected drought increase (ensemble median), per region
    hs = []
    for iso in P.REGIONS:
        u = P.load_units(iso)
        kind, k = P.WEIGHTS[iso]
        w = S.make_weights(u, kind, k or 5)
        for scen, win, met in itertools.product(("rcp_2_6", "rcp_8_5"), X.FUT, ("drought_share_change_pp", "spei_drought_share_change_pp",
                                                                              "rx5day_change_pct", "hot_days_change")):
            e = ens[(ens.region == iso) & (ens.scenario == scen) & (ens.window == win) & (ens.metric == met)]
            if len(e) < len(u) * 0.9:
                continue
            y = e.set_index("unit_id")["median"].reindex(u.unit_id)
            if y.isna().any() or y.std() == 0:
                continue
            gm = S.global_moran(y.values, w, 9999)
            lc = S.local_clusters(y.values, w, 9999).assign(unit_id=u.unit_id.values, region=iso, scenario=scen, window=win, metric=met,
                                                             value=y.values, robust=e.set_index("unit_id").robust.reindex(u.unit_id).values)
            hs.append(lc)
            moran_rows.append({"region": iso, "scenario": scen, "window": win, "metric": met, **gm})
    if hs:
        pd.concat(hs).to_csv(OUT / "future_change_hotspots.csv", index=False)
        pd.DataFrame(moran_rows).to_csv(OUT / "future_change_moran.csv", index=False)

# modeled vs observed drought pattern, 2000-2016: evaluation runs vs ERA5-Land
pat = []
for iso in P.REGIONS:
    obs = era5_monthly(iso)
    so = X.spi_apply(X.accum(obs, 6), X.spi_fit(X.accum(obs, 6), 1991, 2016))
    od = (so[(so.index.year >= 2000) & (so.index.year <= 2016)] <= -1).sum()   # months in drought, 2000-2016
    for rcm in sorted(inv[(inv.iso == iso) & (inv.exp == "evaluation") & (inv["var"] == "pr")].rcm.unique()):
        d = X.run_series(inv, iso, "pr", rcm, "era_interim", "evaluation")
        m = X.monthly(d, "sum")
        sm = X.spi_apply(X.accum(m, 6), X.spi_fit(X.accum(m, 6), 1991, 2016))
        md = (sm[(sm.index.year >= 2000) & (sm.index.year <= 2016)] <= -1).sum()
        units = od.index.intersection(md.index)
        rho, p = stats.spearmanr(od[units], md[units])
        pat.append({"region": iso, "rcm": rcm, "units": len(units), "spearman_drought_months_2000_2016": rho, "p": p,
                    "obs_mean_months": float(od[units].mean()), "model_mean_months": float(md[units].mean())})
if pat:
    pd.DataFrame(pat).to_csv(OUT / "drought_pattern_model_vs_obs_2000_2016.csv", index=False)

summary["runs_with_future"] = int(len({(r["region"], r["rcm"], r["gcm"]) for r in change_rows if "rcm" in r}))
json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))
