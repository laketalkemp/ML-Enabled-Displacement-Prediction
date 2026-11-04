"""IDMC GIDD disaster displacement data: loading and validation of the vulnerability measures.
Inputs (not committed): data/raw/idmc/*.xlsx or *.csv as downloaded from internal-displacement.org.
The loader finds columns by name because the GIDD export headers change between releases."""
from __future__ import annotations

import glob
import re
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from .. import paths


def _find(cols, *patterns):
    for p in patterns:
        for c in cols:
            if re.search(p, str(c), re.I):
                return c
    return None


WEATHER_TYPES = "flood|storm|drought|cyclone|wildfire|extreme temp|wet mass|landslide"


def _disaggregated(files) -> pd.DataFrame | None:
    """GIDD 'Internal Displacement Disaggregated' exports (one figure per row, sheet 1_Disaggregated_Data, often one
    file per year). Keeps disaster internal displacements (flows); IDP stocks and conflict figures are dropped, so the
    sum by country-year reproduces the published GIDD totals. One row per figure, with its event and locations."""
    parts = []
    for f in files:
        try:
            d = pd.read_excel(f, sheet_name="1_Disaggregated_Data")
        except Exception:  # noqa: BLE001
            continue
        if not {"ISO3", "Year", "Figure cause", "Figure category", "Total figures"} <= set(d.columns):
            continue
        parts.append(d)
    if not parts:
        return None
    d = pd.concat(parts, ignore_index=True)
    if "ID" in d.columns:
        d = d.drop_duplicates("ID")
    d = d[(d["Figure cause"].astype(str).str.lower() == "disaster") &
          (d["Figure category"].astype(str).str.lower().str.startswith("internal displacement"))]
    out = pd.DataFrame({"figure_id": d.get("ID"), "iso3": d["ISO3"], "year": pd.to_numeric(d["Year"], errors="coerce"),
                        "displacements": pd.to_numeric(d["Total figures"], errors="coerce"),
                        "hazard_category": d.get("Hazard category"), "hazard_type": d.get("Hazard type"),
                        "hazard_sub_type": d.get("Hazard sub type"), "event_id": d.get("Event ID"), "event": d.get("Event name"),
                        "main_trigger": d.get("Event main trigger"), "start_date": d.get("Start date"),
                        "locations_name": d.get("Locations name"), "locations_coordinates": d.get("Locations coordinates"),
                        "locations_accuracy": d.get("Locations accuracy"), "locations_type": d.get("Locations type")})
    out = out.dropna(subset=["iso3", "year", "displacements"])
    out["year"] = out.year.astype(int)
    out["weather_related"] = out.hazard_category.astype(str).str.lower().eq("weather related")
    return out.reset_index(drop=True)


def load_disaster_events() -> pd.DataFrame | None:
    """GIDD disaster displacement data -> iso3, year, hazard_category, hazard_type, displacements, weather_related.
    Uses the disaggregated (figure-level) export when present, else any event-level table found by column names."""
    files = sorted(glob.glob(str(paths.RAW / "idmc" / "*")))
    dis = _disaggregated([f for f in files if f.lower().endswith((".xlsx", ".xls"))])
    if dis is not None:
        return dis
    best = None
    for f in files:
        if not f.lower().endswith((".xlsx", ".xls", ".csv")):
            continue
        try:
            sheets = pd.read_excel(f, sheet_name=None) if f.lower().endswith(("xlsx", "xls")) else {"csv": pd.read_csv(f)}
        except Exception:  # noqa: BLE001
            continue
        for _, d in sheets.items():
            # some exports carry a second header row with HXL tags (#country+code); drop it
            if len(d) and str(d.iloc[0, 0]).startswith("#"):
                d = d.iloc[1:]
            cols = list(d.columns)
            iso = _find(cols, r"^iso3?$", r"iso")
            yr = _find(cols, r"^year$", r"year")
            disp = _find(cols, r"disaster internal displacements?$", r"internal displacements?", r"new displacements?", r"displacements?")
            hz = _find(cols, r"hazard category", r"hazard_category")
            ht = _find(cols, r"hazard type", r"hazard_type")
            ev = _find(cols, r"event name", r"event")
            if iso and yr and disp and (hz or ht) and ev:
                out = pd.DataFrame({"iso3": d[iso], "year": pd.to_numeric(d[yr], errors="coerce"),
                                    "displacements": pd.to_numeric(d[disp], errors="coerce"),
                                    "hazard_category": d[hz] if hz else np.nan, "hazard_type": d[ht] if ht else np.nan,
                                    "event": d[ev]})
                out = out.dropna(subset=["iso3", "year", "displacements"])
                if best is None or len(out) > len(best):
                    best = out
    if best is not None:
        best["year"] = best.year.astype(int)
        best["weather_related"] = best.hazard_category.astype(str).str.contains("weather", case=False) | \
            best.hazard_type.astype(str).str.contains(WEATHER_TYPES, case=False)
    return best


def country_year(ev: pd.DataFrame, weather_only: bool = True, y0: int = 2008, y1: int = 2025) -> pd.DataFrame:
    e = ev[ev.weather_related] if weather_only else ev
    e = e[e.year.between(y0, y1)]
    t = e.groupby(["iso3", "year"]).displacements.sum().rename("displacements")
    isos = t.index.get_level_values(0).unique()
    return t.reindex(pd.MultiIndex.from_product([isos, range(y0, y1 + 1)], names=["iso3", "year"]), fill_value=0).reset_index()


def validate(cy: pd.DataFrame, cov: pd.DataFrame, emdat_aff_cy: pd.DataFrame, pop: pd.Series) -> dict:
    """cov: iso3-indexed vc, full_score, tier, hazard_exposure, log_pop. emdat_aff_cy: iso3, year, affected (EM-DAT, climate).
    Returns a dict of tables."""
    out = {}
    d = cy.merge(emdat_aff_cy, on=["iso3", "year"], how="left").fillna({"affected": 0})
    d = d[d.iso3.isin(cov.index)].copy()
    d["pop"] = d.iso3.map(pop)
    d = d[d["pop"] > 0]
    m = d.groupby("iso3").agg(displacements=("displacements", "mean"), affected=("affected", "mean"), pop=("pop", "first"))
    m["disp_per_100k"] = m.displacements / m["pop"] * 1e5
    m["aff_per_100k"] = m.affected / m["pop"] * 1e5
    m = m.join(cov)
    rows = []
    for x in ("vc", "full_score", "hazard_exposure"):
        z = m[[x, "disp_per_100k"]].dropna()
        rho, p = stats.spearmanr(z[x], z.disp_per_100k)
        rows.append({"measure": x, "n": len(z), "spearman_rho": rho, "p": p})
    out["rank_correlations"] = pd.DataFrame(rows)
    # tiers
    groups = [m.loc[m.tier == k, "disp_per_100k"].dropna() for k in (1, 2, 3, 4)]
    H, p = stats.kruskal(*groups)
    out["by_tier"] = pd.DataFrame({"tier": [1, 2, 3, 4], "n": [len(g) for g in groups],
                                   "median_disp_per_100k": [g.median() for g in groups], "mean_disp_per_100k": [g.mean() for g in groups]}
                                  ).assign(kruskal_H=H, kruskal_p=p)
    # conditional: does vulnerability predict displacement beyond exposure? (cross-section of country means)
    m["log_disp"] = np.log1p(m.disp_per_100k)
    m["log_aff"] = np.log1p(m.aff_per_100k)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = smf.ols("log_disp ~ I(vc/10) + log_aff + hazard_exposure + log_pop", m.dropna(subset=["vc", "log_aff", "hazard_exposure", "log_pop"])).fit(cov_type="HC3")
    out["ols_country_means"] = pd.DataFrame({"coef": f.params, "ci_low": f.conf_int()[0], "ci_high": f.conf_int()[1], "p": f.pvalues}
                                            ).assign(n=int(f.nobs), r2=f.rsquared)
    # cross-section without the people-affected control: the total association given exposure and size
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f0 = smf.ols("log_disp ~ I(vc/10) + hazard_exposure + log_pop", m.dropna(subset=["vc", "hazard_exposure", "log_pop"])).fit(cov_type="HC3")
    out["ols_country_means_exposure_only"] = pd.DataFrame({"coef": f0.params, "ci_low": f0.conf_int()[0], "ci_high": f0.conf_int()[1],
                                                           "p": f0.pvalues}).assign(n=int(f0.nobs), r2=f0.rsquared)
    # annual panel, year effects, SEs clustered by country. Displacement counts are extremely overdispersed
    # (a negative binomial does not converge reliably), so: Poisson pseudo-ML on the counts, and a two-part model
    # (any displacement recorded; log displacements given some), each with and without EM-DAT people affected.
    d = d.join(cov[["vc", "hazard_exposure", "log_pop"]], on="iso3").dropna(subset=["vc", "hazard_exposure", "log_pop"])
    d["log_aff1"] = np.log1p(d.affected)
    d["any"] = (d.displacements > 0).astype(int)
    g = pd.factorize(d.iso3)[0]
    pos = d[d.displacements > 0]
    gp = pd.factorize(pos.iso3)[0]
    rows = []
    key = "I(vc / 10)"
    import statsmodels.api as sm
    for ctrl, rhs in (("exposure", "I(vc/10) + hazard_exposure + log_pop + C(year)"),
                      ("exposure + EM-DAT affected", "I(vc/10) + log_aff1 + hazard_exposure + log_pop + C(year)")):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fits = {"PPML, displacements": smf.glm(f"displacements ~ {rhs}", d, family=sm.families.Poisson()).fit(cov_type="cluster", cov_kwds={"groups": g}),
                    "any displacement (odds)": smf.logit(f"any ~ {rhs}", d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": g}),
                    "displacements given any": smf.ols(f"np.log(displacements) ~ {rhs}", pos).fit(cov_type="cluster", cov_kwds={"groups": gp})}
        for name, r in fits.items():
            ci = r.conf_int().loc[key]
            rows.append({"model": name, "controls": ctrl, "ratio_per_10_vc": float(np.exp(r.params[key])), "ci_low": float(np.exp(ci[0])),
                         "ci_high": float(np.exp(ci[1])), "p": float(r.pvalues[key]), "n": int(r.nobs), "countries": int(d.iso3.nunique())})
    out["panel"] = pd.DataFrame(rows)
    # out-of-sample: train 2008-2018 country means, test on 2019-2025
    tr = d[d.year <= 2018].groupby("iso3").agg(disp=("displacements", "mean"), aff=("affected", "mean"))
    te = d[d.year >= 2019].groupby("iso3").agg(disp=("displacements", "mean"), aff=("affected", "mean"))
    j = tr.join(te, lsuffix="_tr", rsuffix="_te").join(cov)
    j["pop"] = j.index.map(pop)
    j = j[j["pop"] > 0].dropna(subset=["vc", "hazard_exposure", "log_pop"])
    for s in ("tr", "te"):
        j[f"ld_{s}"] = np.log1p(j[f"disp_{s}"] / j["pop"] * 1e5)
        j[f"la_{s}"] = np.log1p(j[f"aff_{s}"] / j["pop"] * 1e5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fo = smf.ols("ld_tr ~ I(vc/10) + la_tr + hazard_exposure + log_pop", j).fit()
        fb = smf.ols("ld_tr ~ la_tr + hazard_exposure + log_pop", j).fit()
    pred = fo.predict(j.assign(la_tr=j.la_te))
    predb = fb.predict(j.assign(la_tr=j.la_te))
    rho, p = stats.spearmanr(pred, j.ld_te)
    rhob, pb = stats.spearmanr(predb, j.ld_te)
    out["out_of_sample"] = pd.DataFrame([{"model": "with V+C", "spearman_pred_vs_observed_2019_2025": rho, "p": p, "n": len(j)},
                                         {"model": "without V+C", "spearman_pred_vs_observed_2019_2025": rhob, "p": pb, "n": len(j)}])
    out["country_means"] = m
    return out


# ------------------------------------------------------------------ provinces ----
# Location precision that is at least as fine as the analysis unit: PHL provinces and BGD districts are ADM2,
# Afghan provinces ADM1. Coarser points (PHL regions, BGD divisions) are matched by name and shared out.
FINE = {"PHL": ("(ADM2)", "(ADM3)", "Point"), "BGD": ("(ADM2)", "(ADM3)", "Point"), "AFG": ("(ADM1)", "(ADM2)", "(ADM3)", "Point")}
COUNTRY_NAMES = {"PHL": "philippines", "BGD": "bangladesh", "AFG": "afghanistan"}


def _split(x, n):
    parts = [p.strip() for p in str(x).split(";")] if pd.notna(x) else []
    return parts if len(parts) == n else (parts[:1] * n if len(parts) == 1 else [""] * n)


def unit_displacements(ev: pd.DataFrame, iso: str, units, lm_units, pop: pd.Series | None = None,
                       snap_km: float = 10.0) -> tuple[pd.DataFrame, dict]:
    """Share each disaster figure across its reported locations (equally, as IDMC advises against summing
    multi-point figures), then put each location's share in a unit:
    - fine locations (FINE) by point-in-polygon, snapping to the nearest unit within snap_km (coastal points);
    - coarse locations by name (location matcher: regions expand to their provinces), shared by population
      when WorldPop is available, else equally;
    - country-level or unmatched locations stay unassigned (reported in the diagnostics).
    Destination-only locations are dropped (the analysis is about where people were displaced from).
    Returns one row per (figure, unit) and diagnostics."""
    import geopandas as gpd
    from shapely.geometry import Point
    from . import locmatch
    e = ev[(ev.iso3 == iso)].copy()
    rows, coarse = [], []
    for r in e.itertuples(index=False):
        pts = [p.strip() for p in str(r.locations_coordinates).split(";")] if pd.notna(r.locations_coordinates) else []
        n = max(len(pts), 1)
        acc, names, typ = _split(r.locations_accuracy, n), _split(r.locations_name, n), _split(r.locations_type, n)
        share = r.displacements / n
        for k in range(n):
            base = {"figure_id": r.figure_id, "year": r.year, "event_id": r.event_id, "hazard_type": r.hazard_type,
                    "weather_related": r.weather_related, "value": share}
            t = typ[k].lower()
            if t.startswith("destination"):
                rows.append({**base, "how": "destination (dropped)"})
                continue
            nm = names[k]
            if not pts or "(AM0)" in acc[k] or nm.strip().lower() in (COUNTRY_NAMES[iso], ""):
                rows.append({**base, "how": "country level"})
                continue
            if any(tok in acc[k] for tok in FINE[iso]):
                try:
                    lat, lon = (float(v) for v in pts[k].split(","))
                    rows.append({**base, "how": "point", "lat": lat, "lon": lon})
                    continue
                except ValueError:
                    pass
            coarse.append((len(rows), nm))
            rows.append({**base, "how": "name"})
    t = pd.DataFrame(rows)
    out = []
    # points -> units
    p = t[t.how == "point"]
    if len(p):
        g = gpd.GeoDataFrame(p, geometry=[Point(xy) for xy in zip(p.lon, p.lat)], crs=4326)
        j = gpd.sjoin(g, units[["unit_id", "geometry"]], predicate="within", how="left")
        j = j[~j.index.duplicated()]
        miss = j[j.unit_id.isna()].drop(columns=["unit_id", "index_right"])
        if len(miss):
            m = gpd.sjoin_nearest(miss.to_crs(6933), units[["unit_id", "geometry"]].to_crs(6933), how="left",
                                  max_distance=snap_km * 1000)
            m = m[~m.index.duplicated()]
            j.loc[m.index, "unit_id"] = m.unit_id
            j.loc[m[m.unit_id.notna()].index, "how"] = "point (snapped)"
        out.append(pd.DataFrame(j.drop(columns=["geometry", "index_right"], errors="ignore")).assign(weight=1.0))
    # names -> units, shared by population (or equally)
    named = []
    for i, nm in coarse:
        us, _ = locmatch.location_units(iso, nm, lm_units)
        us = sorted(u for u in us if u in set(units.unit_id))
        if not us:
            continue
        w = pd.Series(1.0, index=us) if pop is None else pop.reindex(us).fillna(0)
        w = w / w.sum() if w.sum() > 0 else pd.Series(1.0 / len(us), index=us)
        for u, wt in w.items():
            named.append({**t.loc[i].to_dict(), "unit_id": u, "weight": wt, "how": "name"})
    if named:
        out.append(pd.DataFrame(named))
    a = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=list(t.columns) + ["unit_id", "weight"])
    a = a[a.unit_id.notna()].copy()
    a["value"] = a.value * a.weight
    tot = t.value.sum()
    diag = {"figures": int(e.figure_id.nunique()), "displacements": float(tot),
            "assigned_share": float(a.value.sum() / tot) if tot else np.nan,
            "by_method_share": {k: float(v / tot) for k, v in a.groupby("how").value.sum().items()},
            "unassigned_share": {k: float(v / tot) for k, v in t[t.how.isin(["country level", "destination (dropped)"])].groupby("how").value.sum().items()},
            "name_unmatched_share": float(t.loc[[i for i, _ in coarse]].value.sum() / tot - a[a.how == "name"].value.sum() / tot) if coarse else 0.0,
            "population_weights": pop is not None}
    return a.drop(columns=[c for c in ("lat", "lon", "weight") if c in a.columns]), diag
