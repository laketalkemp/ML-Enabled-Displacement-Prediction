"""EM-DAT loading and hazard grouping. EM-DAT data are restricted: outputs derived from them are written
to data/processed/emdat/ (git-ignored) and never committed."""
from __future__ import annotations

import glob
import re
import json

import numpy as np
import pandas as pd

from .. import paths

# Hazard groups used throughout. Climate hazards form the core; geophysical ones are sensitivity columns.
HGROUP = {
    "Flood": "flood", "Glacial lake outburst flood": "flood",
    "Storm": "storm",
    "Drought": "drought",
    "Extreme temperature": "extreme_temp",
    "Mass movement (wet)": "wet_mass_mov",
    "Wildfire": "wildfire",
    "Earthquake": "earthquake",
    "Volcanic activity": "volcanic",
    "Mass movement (dry)": "dry_mass_mov",
}
CLIMATE = ["flood", "storm", "drought", "extreme_temp", "wet_mass_mov", "wildfire"]
GEOPHYSICAL = ["earthquake", "volcanic", "dry_mass_mov"]
LABEL = {"flood": "Flood", "storm": "Storm", "drought": "Drought", "extreme_temp": "Extreme temperature",
         "wet_mass_mov": "Landslide (wet)", "wildfire": "Wildfire", "earthquake": "Earthquake",
         "volcanic": "Volcanic", "dry_mass_mov": "Mass movement (dry)"}


def emdat_file() -> str:
    files = sorted(glob.glob(str(paths.EMDAT_DIR / "emdat_public_*.xlsx")))
    if not files:
        raise SystemExit("No EM-DAT export in data/raw/emdat/ (restricted data; see data/README.md).")
    return files[-1]


def load_records(y0: int = 2000, y1: int = 2025) -> pd.DataFrame:
    """One row per EM-DAT record (one country's part of a disaster), natural non-biological hazards."""
    raw = pd.read_excel(emdat_file(), sheet_name="EM-DAT Data")
    d = raw[(raw["Disaster Group"] == "Natural") & raw["Disaster Type"].isin(HGROUP)
            & raw["Start Year"].between(y0, y1)].copy()
    out = pd.DataFrame({
        "disno": d["DisNo."], "event_id": d["DisNo."].str[:9], "iso3": d["ISO"], "country": d["Country"],
        "region": d["Region"], "subregion": d["Subregion"],
        "type": d["Disaster Type"], "subtype": d["Disaster Subtype"], "hgroup": d["Disaster Type"].map(HGROUP),
        "year": d["Start Year"].astype(int), "month": d["Start Month"],
        "end_year": d["End Year"], "end_month": d["End Month"],
        "deaths": d["Total Deaths"], "affected": d["Total Affected"], "homeless": d["No. Homeless"],
        "damage_adj_kusd": d["Total Damage, Adjusted ('000 US$)"],
        "magnitude": d["Magnitude"], "magnitude_scale": d["Magnitude Scale"],
        "lat": d["Latitude"], "lon": d["Longitude"],
        "gadm": d["GADM Admin Units"], "gaul": d["Admin Units"], "location": d["Location"],
        "declaration": d["Declaration"], "appeal": d["Appeal"],
    })
    out["climate"] = out.hgroup.isin(CLIMATE)
    out["tropical_cyclone"] = out.subtype.eq("Tropical cyclone")
    out["coastal_flood"] = out.subtype.isin(["Coastal flood", "Storm surge"])
    out["high_impact"] = (out.deaths.fillna(0) >= 100) | (out.affected.fillna(0) >= 100_000)
    return out.reset_index(drop=True)


def wdi_series(code: str) -> pd.DataFrame | None:
    """A WDI indicator as an ISO3 x year table, from data/raw/wdi/. Reads both the bulk download
    (API_<code>*.csv, four header lines) and a DataBank export (*_Data.csv with 'Series Code' and
    '2000 [YR2000]' columns, '..' for missing). None if neither file is there."""
    d = paths.RAW / "wdi"
    api = sorted(glob.glob(str(d / f"API_{code}*.csv")))
    if api:
        w = pd.read_csv(api[-1], skiprows=4).set_index("Country Code")
        yrs = [c for c in w.columns if str(c).isdigit()]
        w = w[yrs]
        w.columns = w.columns.astype(int)
        return w.apply(pd.to_numeric, errors="coerce")
    for f in sorted(glob.glob(str(d / "*_Data.csv"))) + sorted(glob.glob(str(d / "*Data*.csv"))):
        w = pd.read_csv(f, na_values=[".."])
        if "Series Code" not in w.columns or code not in set(w["Series Code"].dropna()):
            continue
        w = w[w["Series Code"] == code].set_index("Country Code")
        yrs = {c: int(c[:4]) for c in w.columns if re.match(r"^\d{4} \[YR\d{4}\]$", str(c))}
        w = w[list(yrs)].rename(columns=yrs)
        return w.apply(pd.to_numeric, errors="coerce")
    return None


def _natural_earth():
    import geopandas as gpd
    ne = gpd.read_file(f"zip://{paths.NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
    ne["iso3"] = ne.ISO_A3_EH.where(ne.ISO_A3_EH != "-99", ne.ADM0_A3)
    return ne


def country_population(year: int | None = None) -> pd.Series:
    """Population by ISO3: WDI SP.POP.TOTL (mean 2000-2025, or the given year) where present; Natural Earth
    POP_EST (c. 2019) for countries WDI lacks (e.g. Taiwan), or for all if no WDI file is present."""
    ne = _natural_earth().groupby("iso3").POP_EST.sum().rename("population")
    w = wdi_series("SP.POP.TOTL")
    if w is None:
        return ne
    v = (w.loc[:, 2000:2025].mean(axis=1) if year is None else w[year]).dropna()
    return pd.concat([v, ne[~ne.index.isin(v.index)]]).rename("population")


def country_gdp_usd() -> pd.Series:
    """Mean GDP (current US$, 2000-2025) by ISO3: WDI NY.GDP.MKTP.CD where present, else Natural Earth GDP_MD."""
    ne = (_natural_earth().groupby("iso3").GDP_MD.sum() * 1e6).rename("gdp_usd")
    w = wdi_series("NY.GDP.MKTP.CD")
    if w is None:
        return ne
    v = w.loc[:, 2000:2025].mean(axis=1).dropna()
    return pd.concat([v, ne[~ne.index.isin(v.index)]]).rename("gdp_usd")
