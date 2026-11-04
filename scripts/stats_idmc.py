"""IDMC disaster displacement as an outcome the index was not built from (statistical analysis plan, Aim 2).

    python scripts/stats_idmc.py

Run after scripts/stats_country.py (it reads that run's covariates.csv). Inputs (not committed): the GIDD
"Internal Displacement Disaggregated" exports in data/raw/idmc/ (one file per year is fine), WDI in data/raw/wdi/,
EM-DAT, and optionally WorldPop 2020 rasters for sharing region-level figures across provinces.
Outputs: data/processed/emdat/stats/idmc/ (internal: the models also use EM-DAT; IDMC data are CC BY-NC).

Country level (weather-related disaster displacements, 2008-2025):
- rank correlations of displacement per 100,000 people with V+C, the full score and hazard exposure;
- by tier (Kruskal-Wallis);
- country-mean OLS: log displacement per capita ~ V+C + log EM-DAT affected per capita + hazard exposure + log pop;
- annual panel with year effects, SEs clustered by country: Poisson pseudo-ML and a two-part model;
- out of sample: fit on 2008-2018 country means, predict 2019-2025.
Provinces: figures shared across their locations and placed in units (idmc.unit_displacements); rank agreement
with EM-DAT per unit; Moran's I and Gi* hot spots.
"""
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
from hvd.stats import emdat, idmc, locmatch, province as P, spatial as S  # noqa: E402

OUT = paths.EMDAT_DERIVED_DIR / "stats" / "idmc"
OUT.mkdir(parents=True, exist_ok=True)
COUNTRY = paths.EMDAT_DERIVED_DIR / "stats" / "country"
PROV = paths.EMDAT_DERIVED_DIR / "stats" / "province"
Y0, Y1 = 2008, 2025
summary = {}

ev = idmc.load_disaster_events()
if ev is None:
    raise SystemExit("No IDMC files in data/raw/idmc/")
summary["figures"] = int(len(ev))
summary["years"] = [int(ev.year.min()), int(ev.year.max())]
summary["weather_share_of_displacements"] = float(ev[ev.weather_related].displacements.sum() / ev.displacements.sum())

# ------------------------------------------------------------------ country level ----
cy = idmc.country_year(ev, weather_only=True, y0=Y0, y1=Y1)
cy.to_csv(OUT / "idmc_weather_displacements_country_year.csv", index=False)
cov = pd.read_csv(COUNTRY / "covariates.csv").set_index("iso3")
v11 = pd.read_csv(paths.INDEX_DIR / "vulnerability_index_v1.1.csv").set_index("iso3")
cov["full_score"] = v11.vulnerability_score
pop = emdat.country_population()
cov["log_pop"] = np.log(pop.reindex(cov.index))
rec = emdat.load_records(Y0, Y1)
aff = rec[rec.climate].groupby(["iso3", "year"]).affected.sum().rename("affected").reset_index()
res = idmc.validate(cy, cov, aff, pop)
for k, v in res.items():
    v.to_csv(OUT / f"country_{k}.csv", index=k.startswith("ols") or k == "country_means")
m = res["country_means"]
rho, p = stats.spearmanr(m.disp_per_100k, m.aff_per_100k)
summary["countries"] = int(len(m))
summary["spearman_idmc_vs_emdat_affected_per_capita"] = {"rho": float(rho), "p": float(p)}
# sensitivity: without the imputed countries; and all disasters (geophysical included)
res_ni = idmc.validate(cy, cov[~cov.imputed.astype(bool)], aff, pop)
res_ni["panel"].to_csv(OUT / "country_panel_without_imputed.csv", index=False)
res_all = idmc.validate(idmc.country_year(ev, weather_only=False, y0=Y0, y1=Y1), cov, aff, pop)
res_all["panel"].to_csv(OUT / "country_panel_all_disasters.csv", index=False)

# --------------------------------------------------------------------- provinces ----
lm = locmatch.build_units(paths.ROOT)
diag, prov_rows, moran_rows, loc_all, rwi_rows = {}, [], [], [], []
for iso in P.REGIONS:
    u = P.load_units(iso)
    upop = P.unit_population(iso, u)
    a, d = idmc.unit_displacements(ev, iso, u, lm, upop)
    diag[iso] = d
    a = a[a.weather_related & a.year.between(Y0, Y1)]
    a.to_csv(OUT / f"{iso.lower()}_figure_unit_shares.csv", index=False)
    grp = a.assign(h=a.hazard_type.str.lower().map(lambda s: s if s in ("storm", "flood") else "other"))
    t = grp.pivot_table(index="unit_id", columns="h", values="value", aggfunc="sum").reindex(u.unit_id).fillna(0)
    t.columns = [f"idmc_{c}" for c in t.columns]
    t["idmc_weather"] = t.sum(axis=1)
    t["idmc_per_year"] = t.idmc_weather / (Y1 - Y0 + 1)
    if upop is not None:
        t["population"] = upop.reindex(t.index)
        t["idmc_per_100k_yr"] = t.idmc_per_year / t.population * 1e5
    em = pd.read_csv(PROV / f"{iso.lower()}_unit_table.csv").set_index("unit_id")
    t = t.join(em[[c for c in ("name", "events_climate", "events_storm", "events_flood", "affected_alloc_pop", "burden",
                               "drought_months_spi6", "rwi_mean") if c in em]])
    t.to_csv(OUT / f"{iso.lower()}_unit_displacements.csv")
    for x in ("events_climate", "affected_alloc_pop", "burden"):
        rho, p = stats.spearmanr(t.idmc_weather, t[x])
        prov_rows.append({"region": iso, "emdat_measure": x, "spearman_rho": rho, "p": p, "units": len(t),
                          "idmc_assigned_share": d["assigned_share"]})
    y = np.log1p(t["idmc_per_100k_yr"] if "idmc_per_100k_yr" in t else t.idmc_per_year).to_numpy()
    kind, k = P.WEIGHTS[iso]
    w = S.make_weights(u, kind, k or 5)
    gm = S.global_moran(y, w, 9999)
    moran_rows.append({"region": iso, "variable": "log IDMC displacements" + (" per 100k" if upop is not None else ""), **gm})
    lc = S.local_clusters(y, w, 9999).assign(unit_id=u.unit_id.values, region=iso, name=t.name.values, value=t.idmc_per_year.values)
    loc_all.append(lc)
    # within the country: are poorer units displaced more, given how often they are hit? (needs RWI and WorldPop)
    if "rwi_mean" in t and "idmc_per_100k_yr" in t:
        z = t.dropna(subset=["rwi_mean", "idmc_per_100k_yr"])
        rho, p = stats.spearmanr(z.rwi_mean, z.idmc_per_100k_yr)
        import statsmodels.formula.api as smf
        z = z.assign(ld=np.log1p(z.idmc_per_100k_yr), le=np.log1p(z.events_climate), lp=np.log(z.population))
        f = smf.ols("ld ~ rwi_mean + le + lp", z).fit(cov_type="HC3")
        ci = f.conf_int().loc["rwi_mean"]
        gs, bl = S.bivariate(np.log1p(t.idmc_per_100k_yr.fillna(0)).values, (-t.rwi_mean.fillna(t.rwi_mean.mean())).values, w, 9999)
        rwi_rows.append({"region": iso, "units": len(z), "spearman_rwi_vs_disp_per_100k": rho, "p": p,
                         "ols_rwi_coef": f.params["rwi_mean"], "ols_ci_low": ci[0], "ols_ci_high": ci[1], "ols_p": f.pvalues["rwi_mean"],
                         "ols_ratio_per_rwi_unit": float(np.exp(f.params["rwi_mean"])), "bivariate_moran_disp_x_lowRWI": gs["moran_bv_I"],
                         "bivariate_p": gs["p_sim"]})
        bl.assign(unit_id=u.unit_id.values, name=t.name.values, region=iso).to_csv(OUT / f"{iso.lower()}_idmc_x_lowRWI_clusters.csv", index=False)
pd.DataFrame(prov_rows).to_csv(OUT / "province_idmc_vs_emdat_spearman.csv", index=False)
if rwi_rows:
    pd.DataFrame(rwi_rows).to_csv(OUT / "province_idmc_vs_rwi.csv", index=False)
pd.DataFrame(moran_rows).to_csv(OUT / "province_idmc_moran.csv", index=False)
pd.concat(loc_all).to_csv(OUT / "province_idmc_local_clusters.csv", index=False)
summary["province_assignment"] = diag
json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))
