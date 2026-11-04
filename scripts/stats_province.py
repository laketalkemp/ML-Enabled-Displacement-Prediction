"""Province / district statistics for the Philippines, Afghanistan and Bangladesh (statistical analysis plan,
Aims 1-3): hazard-signature tables, seasonality, co-occurrence, drought trends, Moran's I / LISA / Gi*,
bivariate LISA with the Relative Wealth Index, pooled hazard archetypes, and comparisons across regions.

    python scripts/stats_province.py [--quick]

Inputs: data/processed/emdat/record_unit_assignment_PHL_AFG_BGD.csv (from scripts/emdat_province_counts.py),
the restricted EM-DAT export, the ERA5-Land drought tables, and if present data/raw/worldpop/*.tif and
data/raw/rwi/*.csv. Outputs: data/processed/emdat/stats/province/ (git-ignored; derived from EM-DAT).
"""
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
from statsmodels.stats.multitest import multipletests  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import archetypes as A  # noqa: E402
from hvd.stats import country as C  # noqa: E402
from hvd.stats import emdat, province as P, rwi as R, spatial as S  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
PERM = 999 if args.quick else 9999
BOOT = 100 if args.quick else 500
OUT = paths.EMDAT_DERIVED_DIR / "stats" / "province"
OUT.mkdir(parents=True, exist_ok=True)
summary = {}

rec = emdat.load_records()
long_all = P.assignment(rec)
long_strict = P.assignment(rec, exclude_text=True)
units, tables, pops, wts = {}, {}, {}, {}

# ---------------- coverage and assignment quality
a = pd.read_csv(paths.EMDAT_DERIVED_DIR / "record_unit_assignment_PHL_AFG_BGD.csv")
cov = a.groupby(["ISO", "unit_source"]).size().unstack(fill_value=0)
cov["records"] = cov.sum(axis=1)
cov["share_assigned"] = 1 - cov.get("unresolved", 0) / cov.records
cov.to_csv(OUT / "assignment_sources.csv")
yr = a.merge(rec[["disno", "hgroup"]], left_on="DisNo.", right_on="disno")
yr[yr.hgroup.isin(emdat.CLIMATE)].groupby(["ISO", "Start Year"]).size().unstack(0, fill_value=0).to_csv(OUT / "coverage_records_by_year.csv")

# ---------------- unit tables
for iso in P.REGIONS:
    u = P.load_units(iso)
    units[iso] = u
    pops[iso] = P.unit_population(iso, u)
    long = P.allocate_impacts(long_all[long_all.iso3 == iso], pops[iso])
    t = P.unit_table(iso, long, u, pops[iso])
    strict = P.unit_table(iso, P.allocate_impacts(long_strict[long_strict.iso3 == iso], pops[iso]), u, pops[iso])
    t["events_climate_strict"] = strict.events_climate
    t["burden"] = P.burden_index(t)
    rw = R.unit_rwi(iso, u)
    if rw is not None:
        t = t.join(rw)
    tables[iso] = t
    t.to_csv(OUT / f"{iso.lower()}_unit_table.csv")
    kind, k = P.WEIGHTS[iso]
    wts[iso] = S.make_weights(u, kind, k or 5)
summary["population_source"] = {iso: ("WorldPop 2020" if pops[iso] is not None else "none (equal split only)") for iso in P.REGIONS}
summary["rwi_available"] = {iso: bool("rwi_mean" in tables[iso]) for iso in P.REGIONS}

# ---------------- Aim 1: seasonality, co-occurrence, drought trends
rows = []
for iso in P.REGIONS:
    r = rec[rec.iso3 == iso]
    for h in ["flood", "storm", "wet_mass_mov", "extreme_temp"]:
        rows.append({"region": iso, "hazard": h, **P.rayleigh(r[r.hgroup == h].month)})
sea = pd.DataFrame(rows)
ok = sea.get("p", pd.Series(dtype=float)).notna()
sea.loc[ok, "q_bh"] = multipletests(sea.loc[ok, "p"], method="fdr_bh")[1]
sea.to_csv(OUT / "seasonality_rayleigh.csv", index=False)
(rec[rec.iso3.isin(P.REGIONS) & rec.hgroup.isin(emdat.CLIMATE)].groupby(["iso3", "hgroup", "month"]).size()
 .unstack(fill_value=0).to_csv(OUT / "seasonality_month_counts.csv"))

co = []
for iso in P.REGIONS:
    d = long_all[(long_all.iso3 == iso) & (long_all.hgroup != "drought")].rename(columns={"unit_id": "unit"})
    # drought presence per unit-year from the observed index (>= 3 months with SPI-6 <= -1), not from the
    # few EM-DAT drought records
    ann = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_drought_annual_2000_2025.csv")
    dro = ann[ann.drought_months_spi6 >= 3][["unit_id", "year"]].rename(columns={"unit_id": "unit"}).assign(hgroup="drought")
    d = pd.concat([d[["unit", "year", "hgroup"]], dro], ignore_index=True)
    hz = [h for h in ["flood", "storm", "wet_mass_mov", "extreme_temp", "drought"] if (d.hgroup == h).sum() >= 5]
    if len(hz) >= 2:
        co.append(C.cooccurrence(d, groups=hz, n_perm=999 if args.quick else 4999, unit="unit").assign(region=iso))
pd.concat(co).to_csv(OUT / "cooccurrence_unit_year.csv", index=False)

pd.DataFrame([P.drought_trend(iso) for iso in P.REGIONS]).to_csv(OUT / "drought_trend_era5land.csv", index=False)

# ---------------- Aim 3: spatial statistics by region
VARS = ["burden", "events_flood", "events_storm", "events_wet_mass_mov", "events_climate", "drought_months_spi6", "drought_months_spei6"]
glob_rows, local = [], {}
for iso in P.REGIONS:
    t, u, w = tables[iso], units[iso], wts[iso]
    vars_iso = [v for v in VARS if v in t and t[v].std() > 0] + [v for v in ("affected_per_100k_yr", "deaths_per_100k_yr", "rwi_mean") if v in t]
    kind, k = P.WEIGHTS[iso]
    for v in vars_iso:
        y = np.log1p(t[v]) if v.startswith(("events_", "affected_", "deaths_")) else t[v]
        g = S.global_moran(y.values, w, PERM)
        lo, hi = S.bootstrap_moran_ci(y.values, u, kind, k or 5, reps=BOOT)
        glob_rows.append({"region": iso, "variable": v, **g, "boot_ci_low": lo, "boot_ci_high": hi})
    loc = []
    for v in ("burden", "events_flood", "events_storm", "drought_months_spi6"):
        if v in t and t[v].std() > 0:
            y = np.log1p(t[v]) if v.startswith("events_") else t[v]
            loc.append(S.local_clusters(y.values, w, PERM).add_prefix(f"{v}__").set_index(t.index))
    if "rwi_mean" in t:
        for hv in ("burden", "drought_months_spi6"):
            gstat, bl = S.bivariate(t[hv].values, (-t.rwi_mean).values, w, PERM)
            glob_rows.append({"region": iso, "variable": f"bivariate {hv} x low RWI", "moran_I": gstat["moran_bv_I"],
                              "z_sim": gstat["z_sim"], "p_sim": gstat["p_sim"], "n": len(t)})
            loc.append(bl.add_prefix(f"{hv}_x_lowRWI__").set_index(t.index))
    local[iso] = pd.concat([t[["name"]]] + loc, axis=1)
    local[iso].to_csv(OUT / f"{iso.lower()}_local_clusters.csv")
    gg = u.set_index("unit_id").join(t.drop(columns="name")).join(local[iso].drop(columns="name")).reset_index()
    gg.to_file(OUT / f"{iso.lower()}_units_stats.gpkg", driver="GPKG")
# sensitivity: other spatial weights, and counts without Location-text assignments
sens = []
for iso in P.REGIONS:
    t, u = tables[iso], units[iso]
    strict_t = P.unit_table(iso, P.allocate_impacts(long_strict[long_strict.iso3 == iso], pops[iso]), u, pops[iso])
    variants = [("knn", 4), ("knn", 6), ("queen", None)] if iso == "PHL" else [("knn", 4), ("knn", 6), ("queen", None)]
    for v in ("events_flood", "events_storm", "events_climate", "drought_months_spi6"):
        if t[v].std() == 0:
            continue
        for kind, k in variants:
            w2 = S.make_weights(u, kind, k or 5)
            y = np.log1p(t[v]) if v.startswith("events_") else t[v]
            sens.append({"region": iso, "variable": v, "weights": f"{kind}{k or ''}", "counts": "all assignments",
                         **S.global_moran(y.values, w2, 999)})
        if v.startswith("events_") and strict_t[v].std() > 0:
            kind, k = P.WEIGHTS[iso]
            sens.append({"region": iso, "variable": v, "weights": f"{kind}{k or ''}", "counts": "without Location-text",
                         **S.global_moran(np.log1p(strict_t[v]).values, wts[iso], 999)})
pd.DataFrame(sens).to_csv(OUT / "global_moran_sensitivity.csv", index=False)

gm = pd.DataFrame(glob_rows)
gm["q_bh"] = multipletests(gm.p_sim, method="fdr_bh")[1]
gm.to_csv(OUT / "global_moran_by_region.csv", index=False)

# hot-spot shares (comparison across regions)
hs = []
for iso in P.REGIONS:
    L = local[iso]
    for v in ("burden", "events_flood", "events_storm", "drought_months_spi6"):
        c = f"{v}__gi_spot"
        if c in L:
            hs.append({"region": iso, "variable": v, "units": len(L), "hot_spots": int((L[c] == "hot spot").sum()),
                       "cold_spots": int((L[c] == "cold spot").sum()), "share_hot": float((L[c] == "hot spot").mean())})
pd.DataFrame(hs).to_csv(OUT / "hotspot_shares_by_region.csv", index=False)

# ---------------- Aim 2 (province): relative wealth vs hazard
rw_rows = []
for iso in P.REGIONS:
    t = tables[iso]
    if "rwi_mean" not in t:
        continue
    for v in ("burden", "events_climate", "drought_months_spi6", "affected_per_100k_yr", "deaths_per_100k_yr"):
        if v in t:
            x = t[[v, "rwi_mean"]].dropna()
            rho, p = __import__("scipy").stats.spearmanr(x[v], x.rwi_mean)
            rw_rows.append({"region": iso, "variable": v, "n": len(x), "spearman_rho_with_rwi": rho, "p": p})
if rw_rows:
    rr = pd.DataFrame(rw_rows)
    rr["q_bh"] = multipletests(rr.p, method="fdr_bh")[1]
    rr.to_csv(OUT / "rwi_vs_hazard_spearman.csv", index=False)

# ---------------- pooled archetypes and comparisons across regions
pool = pd.concat([tables[iso].assign(region=iso) for iso in P.REGIONS])
cnt = pool[["events_flood", "events_storm", "events_wet_mass_mov", "events_extreme_temp"]].copy()
cnt.columns = ["flood", "storm", "wet_mass_mov", "extreme_temp"]
cnt["drought"] = (pool.drought_months_spi6 / 6).round()   # drought months as 6-month drought "episodes"
lab, sel, prof, mp = A.fit(cnt, n_boot=BOOT // 2)
pool["archetype"], pool["membership_p"] = lab, mp
prof.to_csv(OUT / "archetypes_units_profiles.csv")
sel.to_csv(OUT / "archetypes_units_k_selection.csv", index=False)
pool[["region", "name", "archetype", "membership_p"]].to_csv(OUT / "archetypes_units.csv")
pd.crosstab(pool.archetype, pool.region).to_csv(OUT / "archetypes_by_region.csv")
cmp = A.compare_with(lab, pool.region)
summary["unit_archetypes"] = {"k": int(lab.nunique()), "units": int(len(lab)), "stability_ari": float(sel.set_index("k").loc[lab.nunique(), "stability_ari"]),
                              "cramers_v_with_region": float(cmp["cramers_v"])}

cr = P.compare_regions(tables, ["drought_months_spi6", "drought_months_spei6", "events_flood", "events_storm", "events_climate"])
cr.to_csv(OUT / "regions_mann_whitney.csv", index=False)

json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))
print("Wrote", OUT)
