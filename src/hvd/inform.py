"""Load and merge the eight INFORM / climate-driven INFORM indicator files.

Two merge modes:
- ``legacy``: reproduces the Oct 2026 notebook exactly. Rows are keyed on ISO3 *and* country label,
  so a country spelled differently in the two sources (e.g. "Turkiye" / "Türkiye") becomes two
  half-empty rows that are then filled with column means.
- ``iso3``: keys on the ISO3 code (REF_AREA) only, so every country is one row. The country name is
  taken from the INFORM (JRC) files, falling back to the IMF files.
"""
from __future__ import annotations

import pandas as pd

from .paths import INFORM_DIR, INFORM_FILES

REQUIRED = ["REF_AREA", "REF_AREA_LABEL", "INDICATOR", "INDICATOR_LABEL", "TIME_PERIOD", "OBS_VALUE"]

# Short, stable column names for the eight indicators (the long labels stay in the data dictionary).
SHORT_NAMES = {
    "IMF_CDIR_ECFRMC": "cdi_lack_coping_capacity",
    "IMF_CDIR_ECFRMH": "cdi_hazard_exposure",
    "IMF_CDIR_ECFRMR": "cdi_risk",
    "IMF_CDIR_ECFRMV": "cdi_vulnerability",
    "INFORM_CC": "inform_lack_coping_capacity",
    "INFORM_HA": "inform_hazard_exposure",
    "INFORM_OVRL": "inform_risk",
    "INFORM_VU": "inform_vulnerability",
}


# Display-name overrides where a source label is unwieldy (the ISO3 code remains the key).
NAME_OVERRIDES = {"SOM": "Somalia"}


def read_indicator(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    return df[REQUIRED].copy()


def latest_per_area(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Most recent observation per area (the notebook's sort-then-drop_duplicates)."""
    return df.sort_values("TIME_PERIOD", ascending=False).drop_duplicates(subset=keys, keep="first")


def load_long(data_dir=INFORM_DIR, files=INFORM_FILES) -> pd.DataFrame:
    """All eight files stacked in long format, with a short indicator name."""
    frames = []
    for f in files:
        d = read_indicator(data_dir / f)
        d["indicator"] = d["INDICATOR"].map(SHORT_NAMES)
        d["source_file"] = f
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def merge_latest(mode: str = "iso3", data_dir=INFORM_DIR, files=INFORM_FILES) -> pd.DataFrame:
    """Wide table: one row per area, one column per indicator (latest year available).

    Returns columns: iso3, country, <8 indicator columns>, and <indicator>_year for each indicator.
    In ``legacy`` mode the column names and row order match the notebook's ``merged_raw_inform_data.csv``
    (Region_ID + '<INDICATOR_LABEL>_VALUE').
    """
    if mode == "legacy":
        merged = None
        for f in files:
            d = read_indicator(data_dir / f)
            d = latest_per_area(d, ["REF_AREA", "REF_AREA_LABEL"])
            label = str(d["INDICATOR_LABEL"].iloc[0]).strip()
            d = d.rename(columns={"OBS_VALUE": f"{label}_VALUE"}).drop(columns=["INDICATOR", "INDICATOR_LABEL", "TIME_PERIOD"])
            merged = d if merged is None else pd.merge(merged, d, on=["REF_AREA", "REF_AREA_LABEL"], how="outer")
        merged = merged.rename(columns={"REF_AREA_LABEL": "Region_ID", "REF_AREA": "iso3"})
        return merged

    if mode != "iso3":
        raise ValueError("mode must be 'iso3' or 'legacy'")
    long = load_long(data_dir, files)
    latest = latest_per_area(long, ["REF_AREA", "indicator"])
    values = latest.pivot(index="REF_AREA", columns="indicator", values="OBS_VALUE")
    years = latest.pivot(index="REF_AREA", columns="indicator", values="TIME_PERIOD").add_suffix("_year")
    order = [SHORT_NAMES[f.replace(".csv", "")] for f in files]
    wide = pd.concat([values[order], years[[f"{c}_year" for c in order]]], axis=1)
    # country name: prefer the INFORM (JRC) spelling, fall back to the IMF one
    names = (long.assign(pref=long["INDICATOR"].str.startswith("INFORM").map({True: 0, False: 1}))
                 .sort_values(["pref", "TIME_PERIOD"], ascending=[True, False])
                 .drop_duplicates("REF_AREA").set_index("REF_AREA")["REF_AREA_LABEL"])
    names = names.copy()
    for iso, name in NAME_OVERRIDES.items():
        if iso in names.index:
            names[iso] = name
    wide.insert(0, "country", names.reindex(wide.index))
    wide.index.name = "iso3"
    return wide.reset_index()


def label_variants(data_dir=INFORM_DIR, files=INFORM_FILES) -> pd.DataFrame:
    """ISO3 codes whose country label differs between files (the cause of the legacy split rows)."""
    long = load_long(data_dir, files)
    v = long.groupby("REF_AREA")["REF_AREA_LABEL"].agg(lambda s: sorted(set(s)))
    v = v[v.str.len() > 1]
    return v.rename("labels").reset_index().rename(columns={"REF_AREA": "iso3"})
