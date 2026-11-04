"""Spatial statistics: weights, global Moran's I, LISA, Getis-Ord Gi*, bivariate Moran / LISA.
Inference by conditional permutation (esda); local p-values are corrected with Benjamini-Hochberg."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import geopandas as gpd
from esda.getisord import G_Local
from esda.moran import Moran, Moran_BV, Moran_Local, Moran_Local_BV
from libpysal import weights
from statsmodels.stats.multitest import multipletests

EA = 6933
QUAD = {1: "high-high", 2: "low-high", 3: "low-low", 4: "high-low"}


def make_weights(gdf: gpd.GeoDataFrame, kind: str = "queen", k: int = 5) -> weights.W:
    """Row-standardised spatial weights. 'queen' contiguity (islands linked to their nearest neighbour) or 'knn'."""
    g = gdf.to_crs(EA)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if kind == "knn":
            pts = np.column_stack([g.geometry.representative_point().x, g.geometry.representative_point().y])
            w = weights.KNN.from_array(pts, k=k)
        else:
            w = weights.Queen.from_dataframe(g, use_index=False)
            if w.islands:
                pts = np.column_stack([g.geometry.representative_point().x, g.geometry.representative_point().y])
                knn1 = weights.KNN.from_array(pts, k=1)
                w = weights.w_union(w, knn1)
                w = weights.W(w.neighbors, silence_warnings=True)
    w.transform = "r"
    return w


def global_moran(y, w, permutations: int = 9999, seed: int = 42) -> dict:
    np.random.seed(seed)
    m = Moran(np.asarray(y, float), w, permutations=permutations)
    return {"moran_I": m.I, "expected_I": m.EI, "z_sim": m.z_sim, "p_sim": m.p_sim, "n": m.n}


def bootstrap_moran_ci(y, gdf, kind, k=5, reps: int = 500, seed: int = 42) -> tuple[float, float]:
    """Percentile CI for Moran's I by resampling units (weights rebuilt each time on the resampled set)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, float)
    vals = []
    n = len(y)
    for _ in range(reps):
        idx = np.unique(rng.integers(0, n, n))
        if len(idx) < 10:
            continue
        sub = gdf.iloc[idx].reset_index(drop=True)
        try:
            w = make_weights(sub, kind, min(k, len(idx) - 1))
            vals.append(Moran(y[idx], w, permutations=0).I)
        except Exception:  # noqa: BLE001
            continue
    return float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def local_clusters(y, w, permutations: int = 9999, alpha: float = 0.05, seed: int = 42) -> pd.DataFrame:
    """LISA and Gi* for one variable. Columns: lisa_I, lisa_p, lisa_q, lisa_cluster, gi_z, gi_p, gi_q, gi_spot."""
    y = np.asarray(y, float)
    np.random.seed(seed)
    lm = Moran_Local(y, w, permutations=permutations, seed=seed)
    gi = G_Local(y, w, star=True, permutations=permutations, seed=seed, transform="R")
    lq = multipletests(lm.p_sim, method="fdr_bh")[1]
    gq = multipletests(gi.p_sim, method="fdr_bh")[1]
    cl = np.where(lq < alpha, pd.Series(lm.q).map(QUAD).to_numpy(), "not significant")
    spot = np.where(gq < alpha, np.where(gi.Zs > 0, "hot spot", "cold spot"), "not significant")
    return pd.DataFrame({"lisa_I": lm.Is, "lisa_p": lm.p_sim, "lisa_q": lq, "lisa_cluster": cl,
                         "gi_z": gi.Zs, "gi_p": gi.p_sim, "gi_q": gq, "gi_spot": spot})


def bivariate(x, y, w, permutations: int = 9999, alpha: float = 0.05, seed: int = 42) -> tuple[dict, pd.DataFrame]:
    """Bivariate Moran (x vs spatial lag of y) and bivariate LISA. high-high = high x surrounded by high y."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    np.random.seed(seed)
    g = Moran_BV(x, y, w, permutations=permutations)
    loc = Moran_Local_BV(x, y, w, permutations=permutations, seed=seed)
    q = multipletests(loc.p_sim, method="fdr_bh")[1]
    cl = np.where(q < alpha, pd.Series(loc.q).map(QUAD).to_numpy(), "not significant")
    return ({"moran_bv_I": g.I, "z_sim": g.z_sim, "p_sim": g.p_sim},
            pd.DataFrame({"bv_I": loc.Is, "bv_p": loc.p_sim, "bv_q": q, "bv_cluster": cl}))


def zscore(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)
