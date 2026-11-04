"""Country-level statistics (Aims 1-3 of workplan/statistical-analysis-plan): hazard signatures, trends,
co-occurrence, vulnerability vs impacts, hazard archetypes, global spatial clustering.

    python scripts/stats_country.py [--quick]

Needs the restricted EM-DAT export in data/raw/emdat/. All outputs are written to
data/processed/emdat/stats/country/ (git-ignored) because they are derived from EM-DAT.
--quick uses fewer permutations and bootstrap draws (for testing).
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

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hvd import index, paths  # noqa: E402
from hvd.stats import archetypes as A  # noqa: E402
from hvd.stats import country as C  # noqa: E402
from hvd.stats import emdat, spatial as S  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
PERM = 999 if args.quick else 9999
BOOT = 50 if args.quick else 200
OUT = paths.EMDAT_DERIVED_DIR / "stats" / "country"
OUT.mkdir(parents=True, exist_ok=True)
summary = {}

rec = emdat.load_records()
pop, gdp = emdat.country_population(), emdat.country_gdp_usd()
summary["records_2000_2025"] = int(len(rec))
summary["events_2000_2025"] = int(rec.event_id.nunique())
summary["countries"] = int(rec.iso3.nunique())
summary["population_source"] = "WDI SP.POP.TOTL, mean 2000-2025 (Natural Earth for countries WDI lacks)" if emdat.wdi_series("SP.POP.TOTL") is not None else "Natural Earth POP_EST (c. 2019)"

# ---- covariates: V+C sub-index (no hazard, no risk), hazard exposure, population, tiers
vc, vc_diag = index.build_index("vc4", n_boot=0, tsne=False)
v11 = pd.read_csv(paths.INDEX_DIR / "vulnerability_index_v1.1.csv").set_index("iso3")
cov = vc.set_index("iso3")[["vulnerability_score"]].rename(columns={"vulnerability_score": "vc"})
cov["hazard_exposure"] = v11.inform_hazard_exposure
cov["log_pop"] = np.log(pop.reindex(cov.index))
cov["tier"] = v11.tier
cov["imputed"] = v11.imputed
cov.to_csv(OUT / "covariates.csv")
summary["vc_subindex"] = {"features": vc_diag["features"], "pc1_variance": vc_diag["explained_variance_pc1_to_pc3"][0],
                          "corr_with_full_score": float(np.corrcoef(cov.vc, v11.reindex(cov.index).vulnerability_score)[0, 1]),
                          "corr_with_hazard_exposure": float(np.corrcoef(cov.vc, cov.hazard_exposure)[0, 1])}

# ---- Aim 1: signatures, trends, co-occurrence
sig = C.signatures(rec, pop, gdp)
sig.to_csv(OUT / "signatures_country_hazard.csv", index=False)
C.signatures(rec, pop, gdp, groups=emdat.CLIMATE + emdat.GEOPHYSICAL).to_csv(OUT / "signatures_country_hazard_allhazards.csv", index=False)
C.global_annual_counts(rec).to_csv(OUT / "global_annual_counts.csv")
tr = C.trends(rec)
tr.to_csv(OUT / "trends_rate_ratio_per_decade.csv", index=False)
co = C.cooccurrence(rec, n_perm=PERM)
co.to_csv(OUT / "cooccurrence_same_year.csv", index=False)
sq = C.sequence_12m(rec, n_perm=199 if args.quick else 999)
sq.to_csv(OUT / "sequence_within_12_months.csv", index=False)

# ---- Aim 2: vulnerability vs impacts (two-part models), tiers, sensitivity
res = []
for oc in ("deaths", "affected"):
    res.append(C.impact_hurdle(rec, cov, oc).assign(sample="all countries"))
    res.append(C.impact_hurdle(rec, cov[~cov.imputed.astype(bool)], oc).assign(sample="without imputed countries"))
pd.concat(res).to_csv(OUT / "vulnerability_vs_impacts_hurdle.csv", index=False)
# indicator-set sensitivity: V+C from the JRC indicators only
vc2, _ = index.build_index("vc2", n_boot=0, tsne=False)
cov2 = cov.copy()
cov2["vc"] = vc2.set_index("iso3").vulnerability_score.reindex(cov.index)
pd.concat([C.impact_hurdle(rec, cov2, oc).assign(sample="V+C from JRC indicators only") for oc in ("deaths", "affected")]
          ).to_csv(OUT / "vulnerability_vs_impacts_hurdle_jrc_only.csv", index=False)
td = pd.concat([C.tier_differences(rec, cov.tier, oc) for oc in ("deaths", "affected")])
td.to_csv(OUT / "impacts_by_tier_kruskal.csv", index=False)

# ---- Aim 3a: hazard archetypes (countries with >= 5 climate records)
cnt = C.wide(sig, "events")
cnt = cnt[cnt.sum(axis=1) >= 5]
lab, sel, prof, member_p = A.fit(cnt, n_boot=BOOT)
names = {}
for i, r in prof.iterrows():
    top = r[emdat.CLIMATE].astype(float)
    if top["storm"] >= 0.45:
        names[i] = "Storm-led"
    elif top["flood"] >= 0.6:
        names[i] = "Flood-led"
    else:
        names[i] = "Mixed: flood, heat and wildfire"
prof["label"] = prof.index.map(names)
arch = pd.DataFrame({"archetype": lab, "archetype_label": lab.map(names), "membership_p": member_p})
arch = arch.join(cnt).join(cov[["vc", "tier"]])
arch.to_csv(OUT / "archetypes_country.csv")
sel.to_csv(OUT / "archetypes_country_k_selection.csv", index=False)
prof.to_csv(OUT / "archetypes_country_profiles.csv")
cmp = A.compare_with(lab, cov.tier)
cmp["table"].to_csv(OUT / "archetypes_vs_tiers_table.csv")
summary["archetypes"] = {"k": int(lab.nunique()), "countries": int(len(lab)),
                         "stability_ari_at_k": float(sel.set_index("k").loc[lab.nunique(), "stability_ari"]),
                         "silhouette_at_k": float(sel.set_index("k").loc[lab.nunique(), "silhouette_kmeans"]),
                         "vs_tiers": {k: float(v) for k, v in cmp.items() if k != "table"}}

# ---- Aim 3b: global spatial clustering of climate hazard burden (191 index countries)
ne = gpd.read_file(f"zip://{paths.NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
ne["iso3"] = ne.ISO_A3_EH.where(ne.ISO_A3_EH != "-99", ne.ADM0_A3)
g = ne.dissolve("iso3").reset_index()
g = g[g.iso3.isin(cov.index)][["iso3", "NAME", "geometry"]].reset_index(drop=True)
aff = C.wide(sig, "affected_per_100k_yr").reindex(g.iso3).fillna(0)
dth = C.wide(sig, "deaths_per_100k_yr").reindex(g.iso3).fillna(0)
ev = C.wide(sig, "events_per_year").reindex(g.iso3).fillna(0)
g["burden_affected"] = np.log1p(aff.sum(axis=1).to_numpy())
g["burden_deaths"] = np.log1p(dth.sum(axis=1).to_numpy())
for h in ("flood", "storm", "drought"):
    g[f"affected_{h}"] = np.log1p(aff[h].to_numpy())
    g[f"frequency_{h}"] = np.log1p(ev[h].to_numpy())
g["vc"] = cov.reindex(g.iso3).vc.to_numpy()
w = S.make_weights(g, "knn", 6)
glob_rows = []
for v in ["burden_affected", "burden_deaths"] + [f"{m}_{h}" for h in ("flood", "storm", "drought") for m in ("affected", "frequency")] + ["vc"]:
    glob_rows.append({"variable": v, **S.global_moran(g[v], w, PERM)})
pd.DataFrame(glob_rows).to_csv(OUT / "global_moran_country.csv", index=False)
locs = []
for v in ("burden_affected", "burden_deaths", "affected_flood", "affected_storm", "affected_drought"):
    locs.append(S.local_clusters(g[v], w, PERM).add_prefix(f"{v}__"))
bv_rows = []
for x, y, tag in (("vc", "burden_affected", "vulnerable_amid_burden"), ("burden_affected", "vc", "burden_amid_vulnerable")):
    gstat, bl = S.bivariate(g[x], g[y], w, PERM)
    bv_rows.append({"x": x, "lag_of": y, **gstat})
    locs.append(bl.add_prefix(f"{tag}__"))
pd.DataFrame(bv_rows).to_csv(OUT / "bivariate_moran_country.csv", index=False)
gl = pd.concat([g.drop(columns="geometry")] + locs, axis=1)
gl.to_csv(OUT / "local_clusters_country.csv", index=False)
g[["iso3", "geometry"]].merge(gl, on="iso3").to_file(OUT / "local_clusters_country.gpkg", driver="GPKG")

json.dump(summary, open(OUT / "summary.json", "w"), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))
print("Wrote", OUT)
