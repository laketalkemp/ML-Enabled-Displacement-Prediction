"""Relative Wealth Index (Meta / Data for Good) averaged to provinces, weighted by WorldPop 2020 population.
Inputs (not committed; see data/README.md): data/raw/rwi/<country>*.csv with columns latitude, longitude, rwi
(and error), and data/raw/worldpop/<iso>_ppp_2020*.tif. Lower RWI = poorer; used as the subnational
vulnerability proxy (wealth, not coping capacity)."""
from __future__ import annotations

import glob

import numpy as np
import pandas as pd
import geopandas as gpd

from .. import paths

FILE_HINTS = {"PHL": ["phl", "philippines"], "AFG": ["afg", "afghanistan"], "BGD": ["bgd", "bangladesh"]}


def rwi_file(iso: str):
    files = glob.glob(str(paths.RAW / "rwi" / "*.csv"))
    for f in sorted(files):
        name = f.lower().rsplit("/", 1)[-1]
        if any(h in name for h in FILE_HINTS[iso]):
            return f
    return None


def unit_rwi(iso: str, units: gpd.GeoDataFrame) -> pd.DataFrame | None:
    f = rwi_file(iso)
    if f is None:
        return None
    d = pd.read_csv(f)
    d.columns = [c.lower() for c in d.columns]
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.longitude, d.latitude), crs=4326)
    j = gpd.sjoin(pts, units[["unit_id", "geometry"]], predicate="within", how="inner")
    from .province import worldpop_file
    wp = [worldpop_file(iso)] if worldpop_file(iso) else []
    if wp:
        # weight each RWI tile (about 2.4 km) by the people living in it: WorldPop summed to about 2 km cells
        import rasterio
        from rasterio.windows import Window
        with rasterio.open(wp[-1]) as src:
            f = 24
            h, w = src.height // f, src.width // f
            arr = np.zeros((h, w))
            for i in range(h):   # block sums, one strip of f rows at a time
                strip = src.read(1, window=Window(0, i * f, w * f, f), masked=True).filled(0).astype(float)
                arr[i] = np.clip(strip, 0, None).reshape(f, w, f).sum(axis=(0, 2))
            tr = src.transform * src.transform.scale(f, f)
            rows, cols = rasterio.transform.rowcol(tr, j.geometry.x.to_numpy(), j.geometry.y.to_numpy())
            rows, cols = np.clip(rows, 0, h - 1), np.clip(cols, 0, w - 1)
            j["w"] = np.clip(arr[rows, cols], 0, None)
        j.loc[~np.isfinite(j.w), "w"] = 0
    else:
        j["w"] = 1.0
    g = j.groupby("unit_id")
    out = pd.DataFrame({
        "rwi_mean": g.apply(lambda x: np.average(x.rwi, weights=x.w) if x.w.sum() > 0 else x.rwi.mean()),
        "rwi_tiles": g.size(),
        "rwi_error_mean": g.error.mean() if "error" in j else np.nan,
    })
    return out.reindex(units.unit_id)
