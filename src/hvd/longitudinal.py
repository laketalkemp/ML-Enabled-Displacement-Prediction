"""Country-year scores for the temporal slider and the top-10 race.

Port of execute_longitudinal_analysis() from the notebook with two fixes:
- rows are keyed on ISO3 + year, not on the country label (which differs between the two sources);
- by default only years in which both sources report (2016-2022) are used. Outside that window every
  row is missing four of its eight indicators, which the notebook filled with the pooled median.
The PCA is still fitted once on all country-years, so the scale is constant across years.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from . import inform


def country_year_table(overlap_only: bool = True) -> pd.DataFrame:
    long = inform.load_long()
    wide = long.pivot_table(index=["REF_AREA", "TIME_PERIOD"], columns="indicator", values="OBS_VALUE").reset_index()
    names = inform.merge_latest("iso3").set_index("iso3")["country"]
    wide = wide.rename(columns={"REF_AREA": "iso3", "TIME_PERIOD": "year"})
    wide.insert(1, "country", wide["iso3"].map(names))
    if overlap_only:
        cdi = long[long["INDICATOR"].str.startswith("IMF")]["TIME_PERIOD"]
        jrc = long[long["INDICATOR"].str.startswith("INFORM")]["TIME_PERIOD"]
        y0, y1 = max(cdi.min(), jrc.min()), min(cdi.max(), jrc.max())
        wide = wide[wide["year"].between(y0, y1)]
    return wide.reset_index(drop=True)


def longitudinal_scores(overlap_only: bool = True) -> pd.DataFrame:
    df = country_year_table(overlap_only)
    cols = list(inform.SHORT_NAMES.values())
    df["n_imputed"] = df[cols].isna().sum(axis=1)
    filled = df[cols].fillna(df[cols].median())
    scaled = StandardScaler().fit_transform(filled)
    pc1 = PCA(n_components=1).fit_transform(scaled).ravel()
    if np.corrcoef(pc1, filled["inform_risk"])[0, 1] < 0:
        pc1 = -pc1
    df["vulnerability_score"] = (pc1 - pc1.min()) / (pc1.max() - pc1.min()) * 100
    return df
