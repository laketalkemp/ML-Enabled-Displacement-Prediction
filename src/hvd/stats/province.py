"""Province / district statistics for the three proof-of-concept regions.

Event counts per unit are exact (an EM-DAT record counts once for every unit it is assigned to). Impacts are
reported by EM-DAT per country only, so they are split across an event's units: by population share
(WorldPop 2020) when available, else equally; both are flagged as estimates.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .. import paths
from .emdat import CLIMATE

REGIONS = ("PHL", "AFG", "BGD")
NAMES = {"PHL": "Philippines", "AFG": "Afghanistan", "BGD": "Bangladesh"}
WEIGHTS = {"PHL": ("knn", 5), "AFG": ("queen", None), "BGD": ("queen", None)}
UNIT_HAZARDS = ["flood", "storm", "wet_mass_mov", "extreme_temp", "earthquake"]


def load_units(iso: str) -> gpd.GeoDataFrame:
    reg = paths.REGIONS_DIR / "poc_provinces.gpkg"
    if iso == "PHL":
        u = gpd.read_file(reg, layer="phl_provinces")[["unit_id", "name", "geometry"]]
        u.loc[u.unit_id == "PH-DVO", ["unit_id", "name"]] = ["PH-DAS", "Davao del Sur"]
        u = u.dissolve(by="unit_id", aggfunc="first").reset_index()
    elif iso == "AFG":
        u = gpd.read_file(reg, layer="afg_provinces")[["unit_id", "name", "geometry"]]
    else:
        u = gpd.read_file(paths.GEOBOUNDARIES_DIR / "geoBoundaries-BGD-ADM2_simplified.geojson")
        u = u.rename(columns={"shapeName": "name"}).assign(unit_id=lambda d: d["name"])[["unit_id", "name", "geometry"]]
    return u.to_crs(4326).sort_values("unit_id").reset_index(drop=True)


def assignment(rec: pd.DataFrame, path=None, exclude_text: bool = False) -> pd.DataFrame:
    """Long table: one row per (record, unit) for the three regions, joined to record attributes."""
    path = path or paths.EMDAT_DERIVED_DIR / "record_unit_assignment_PHL_AFG_BGD.csv"
    a = pd.read_csv(path)
    a = a[a.units.notna()].copy()
    if exclude_text:
        a = a[~a.unit_source.str.startswith("Location text")]
    a["unit_id"] = a.units.str.split(";")
    a = a.explode("unit_id")
    cols = ["disno", "event_id", "iso3", "hgroup", "subtype", "year", "month", "deaths", "affected", "damage_adj_kusd", "high_impact"]
    return a[["DisNo.", "unit_source", "n_units", "unit_id"]].rename(columns={"DisNo.": "disno"}).merge(rec[cols], on="disno", how="inner")


def worldpop_file(iso: str) -> str | None:
    """The country's WorldPop 2020 population-count GeoTIFF in data/raw/worldpop/: classic names
    (phl_ppp_2020_UNadj_constrained.tif) or the Global2 release (phl_pop_2020_CN_100m_R2025A_v1.tif)."""
    import glob
    import os
    fs = [f for f in glob.glob(str(paths.RAW / "worldpop" / "*.tif"))
          if os.path.basename(f).lower().startswith(iso.lower()) and "2020" in os.path.basename(f)]
    pref = [f for f in fs if "_ppp_" in f.lower() or "_pop_" in f.lower()]
    return sorted(pref or fs)[-1] if fs else None


def unit_population(iso: str, units: gpd.GeoDataFrame) -> pd.Series | None:
    """Unit population from a WorldPop 2020 raster in data/raw/worldpop/ (sum of cells by unit), if present."""
    f = worldpop_file(iso)
    if not f:
        return None
    f = [f]
    import rasterio
    from rasterio.features import geometry_mask
    out = {}
    with rasterio.open(f[-1]) as src:
        u = units.to_crs(src.crs)
        for _, r in u.iterrows():
            win = rasterio.windows.from_bounds(*r.geometry.bounds, transform=src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win, boundless=True, fill_value=0).astype(float)
            arr[arr < 0] = 0
            tr = src.window_transform(win)
            m = geometry_mask([r.geometry], out_shape=arr.shape, transform=tr, invert=True, all_touched=False)
            out[r.unit_id] = float(arr[m].sum())
    return pd.Series(out, name="population")


def allocate_impacts(long: pd.DataFrame, pop: pd.Series | None) -> pd.DataFrame:
    """Add allocated impact columns. Weight per (record, unit): population share among the record's units
    (falls back to equal split when population is missing)."""
    d = long.copy()
    d["w_equal"] = 1 / d.groupby("disno").unit_id.transform("count")
    if pop is not None:
        d["pop"] = d.unit_id.map(pop)
        d["w_pop"] = d["pop"] / d.groupby("disno")["pop"].transform("sum")
        d["w_pop"] = d.w_pop.fillna(d.w_equal)
    else:
        d["w_pop"] = d.w_equal
    for c in ("deaths", "affected", "damage_adj_kusd"):
        d[f"{c}_alloc_pop"] = d[c] * d.w_pop
        d[f"{c}_alloc_equal"] = d[c] * d.w_equal
    return d


def unit_table(iso: str, long: pd.DataFrame, units: gpd.GeoDataFrame, pop: pd.Series | None) -> pd.DataFrame:
    """One row per unit: event counts by hazard (exact), high-impact counts, allocated impacts, ERA5-Land drought."""
    d = long[long.iso3 == iso]
    cnt = d.groupby(["unit_id", "hgroup"]).disno.nunique().unstack(fill_value=0)
    cnt = cnt.reindex(index=units.unit_id, columns=CLIMATE + ["earthquake"], fill_value=0).add_prefix("events_")
    t = units[["unit_id", "name"]].set_index("unit_id").join(cnt)
    t["events_climate"] = t[[f"events_{h}" for h in CLIMATE]].sum(axis=1)
    t["events_tropical_cyclone"] = d[d.subtype == "Tropical cyclone"].groupby("unit_id").disno.nunique().reindex(t.index, fill_value=0)
    t["events_high_impact"] = d[d.high_impact & d.hgroup.isin(CLIMATE)].groupby("unit_id").disno.nunique().reindex(t.index, fill_value=0)
    for c in ("deaths", "affected"):
        for m in ("pop", "equal"):
            t[f"{c}_alloc_{m}"] = d[d.hgroup.isin(CLIMATE)].groupby("unit_id")[f"{c}_alloc_{m}"].sum().reindex(t.index).fillna(0)
    if pop is not None:
        t["population"] = pop.reindex(t.index)
        for c in ("deaths", "affected"):
            t[f"{c}_per_100k_yr"] = t[f"{c}_alloc_pop"] / t.population * 1e5 / 26
    dr = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_drought_summary_2000_2025.csv").set_index("unit_id")
    t = t.join(dr[["drought_months_spi6", "severe_months_spi6", "drought_months_spei6", "drought_events_spi6",
                   "longest_event_months", "worst_event_severity", "mean_annual_precip_mm"]])
    t["area_km2"] = units.set_index("unit_id").to_crs(6933).area.reindex(t.index) / 1e6
    return t


def burden_index(t: pd.DataFrame, cols=("events_flood", "events_storm", "events_wet_mass_mov", "drought_months_spi6")) -> pd.Series:
    """Mean of z-scores (within region) of log1p event counts and drought months; columns with no variance are skipped."""
    z = []
    for c in cols:
        x = np.log1p(t[c].astype(float)) if c.startswith("events_") else t[c].astype(float)
        if x.std(ddof=0) > 0:
            z.append((x - x.mean()) / x.std(ddof=0))
    return pd.concat(z, axis=1).mean(axis=1)


def rayleigh(months: pd.Series) -> dict:
    """Rayleigh test for seasonal concentration of start months (circular statistics)."""
    m = months.dropna().astype(int)
    n = len(m)
    if n < 5:
        return {"n": n}
    ang = 2 * np.pi * (m - 0.5) / 12
    C, S = np.cos(ang).sum(), np.sin(ang).sum()
    R = np.hypot(C, S) / n
    Z = n * R ** 2
    p = np.exp(np.sqrt(1 + 4 * n + 4 * (n ** 2 - (n * R) ** 2)) - (1 + 2 * n))
    mean_month = (np.degrees(np.arctan2(S, C)) % 360) / 30 + 0.5
    return {"n": n, "mean_resultant_length": R, "rayleigh_Z": Z, "p": min(p, 1.0), "mean_month": mean_month,
            "peak_month": int(m.value_counts().idxmax())}


def drought_trend(iso: str, y0: int = 1991, y1: int = 2025) -> dict:
    """Theil-Sen slope and Mann-Kendall (Kendall tau) for the regional share of unit-months in drought (SPI-6 <= -1)."""
    mth = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_monthly_drought_indices_1991_2025.csv", usecols=["unit_id", "year", "spi6"])
    mth = mth[mth.year.between(y0, y1)]
    share = mth.assign(d=mth.spi6 <= -1).groupby("year").d.mean() * 100
    share = share[share.index >= y0 + 1]   # first months of SPI-6 are undefined
    slope, inter, lo, hi = stats.theilslopes(share.values, share.index.values)
    tau, p = stats.kendalltau(share.index.values, share.values)
    return {"region": iso, "years": f"{share.index.min()}-{share.index.max()}", "theil_sen_pct_points_per_decade": slope * 10,
            "ci_low": lo * 10, "ci_high": hi * 10, "kendall_tau": tau, "p": p, "mean_share_pct": share.mean()}


def mann_whitney(a: pd.Series, b: pd.Series) -> dict:
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    rbc = 1 - 2 * u / (len(a) * len(b))   # rank-biserial; reported as -rbc so positive means a tends to be larger
    return {"U": u, "p": p, "rank_biserial": -rbc, "median_a": float(np.median(a)), "median_b": float(np.median(b))}


def compare_regions(tables: dict, cols) -> pd.DataFrame:
    rows = []
    for c in cols:
        for a, b in itertools.combinations(REGIONS, 2):
            x, y = tables[a][c].dropna(), tables[b][c].dropna()
            rows.append({"variable": c, "region_a": a, "region_b": b, **mann_whitney(x, y)})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p, method="fdr_bh")[1]
    return t
