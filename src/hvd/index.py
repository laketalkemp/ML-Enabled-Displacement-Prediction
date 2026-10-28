"""Composite vulnerability index: imputation, PCA score, K-means tiers, t-SNE coordinates.

``build_index_legacy`` reproduces the October 2026 Colab notebook step for step (see tests/).
``build_index`` is v1.1: one row per ISO3 code, a per-country imputation flag, a PCA sign fixed so
that higher always means more vulnerable, and tier stability from a bootstrap.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from . import inform

TIER_LABELS = {1: "1 - Low Vulnerability", 2: "2 - Mild Vulnerability",
               3: "3 - Moderate Vulnerability", 4: "4 - Severe Vulnerability"}

# Indicator sets. "all8" is what the notebook used; the others are sensitivity options for Workshop 1
# (the IMF and JRC files carry overlapping versions of the same INFORM components; see the data dictionary).
FEATURE_SETS = {
    "all8": list(inform.SHORT_NAMES.values()),
    "inform4": ["inform_lack_coping_capacity", "inform_hazard_exposure", "inform_risk", "inform_vulnerability"],
    "inform3": ["inform_lack_coping_capacity", "inform_hazard_exposure", "inform_vulnerability"],
}


def _minmax_100(x: np.ndarray) -> np.ndarray:
    return (x - x.min()) / (x.max() - x.min()) * 100


def _ordered_tiers(score: np.ndarray, random_state: int = 42):
    """K-means (k=4) on the 1-D score; clusters renumbered 1-4 by centroid so tiers are ordinal."""
    km = KMeans(n_clusters=4, random_state=random_state, n_init=10)
    raw = km.fit_predict(score.reshape(-1, 1))
    order = np.argsort(km.cluster_centers_.ravel())
    remap = {int(c): i + 1 for i, c in enumerate(order)}
    return raw, np.vectorize(remap.get)(raw), km


# ---------------------------------------------------------------- legacy (notebook) ----
def build_index_legacy(random_state: int = 42) -> pd.DataFrame:
    """Exact re-implementation of build_vulnerability_index() from the Colab notebook."""
    df = inform.merge_latest(mode="legacy")
    iso3 = df.pop("iso3")
    features = df.drop(columns=["Region_ID"])
    imputed = SimpleImputer(strategy="mean").fit_transform(features)
    scaled = StandardScaler().fit_transform(imputed)
    raw = PCA(n_components=1).fit_transform(scaled).ravel()
    df["Vulnerability_Score_PCA"] = _minmax_100(raw)
    km = KMeans(n_clusters=4, random_state=random_state, n_init=10)
    df["Cluster_ID"] = km.fit_predict(df[["Vulnerability_Score_PCA"]])
    order = np.argsort(km.cluster_centers_.flatten())
    df["UNHCR_Tier"] = df["Cluster_ID"].map({order[i]: TIER_LABELS[i + 1] for i in range(4)})
    tsne = TSNE(n_components=2, perplexity=30, random_state=random_state).fit_transform(scaled)
    df["tSNE_1"], df["tSNE_2"] = tsne[:, 0], tsne[:, 1]
    df.insert(1, "iso3", iso3.values)
    return df


# --------------------------------------------------------------------------- v1.1 ----
def build_index(feature_set: str = "all8", impute: str = "mean", n_boot: int = 500,
                random_state: int = 42, tsne: bool = True) -> tuple[pd.DataFrame, dict]:
    """v1.1 index. Returns (table, diagnostics)."""
    cols = FEATURE_SETS[feature_set]
    df = inform.merge_latest(mode="iso3")
    X = df[cols]
    missing = X.isna()
    df["n_imputed"] = missing.sum(axis=1)
    df["imputed"] = df["n_imputed"] > 0
    df["imputed_indicators"] = missing.apply(lambda r: ";".join(c for c, m in r.items() if m), axis=1)

    filled = SimpleImputer(strategy=impute).fit_transform(X)
    scaled = StandardScaler().fit_transform(filled)
    pca = PCA(n_components=min(3, len(cols)))
    comps = pca.fit_transform(scaled)
    pc1 = comps[:, 0]
    # PCA's sign is arbitrary; fix it so a higher score means higher INFORM risk.
    anchor = "inform_risk" if "inform_risk" in cols else cols[0]
    if np.corrcoef(pc1, filled[:, cols.index(anchor)])[0, 1] < 0:
        pc1, pca.components_[0] = -pc1, -pca.components_[0]
    df["vulnerability_score"] = _minmax_100(pc1)

    _, tiers, km = _ordered_tiers(df["vulnerability_score"].to_numpy(), random_state)
    df["tier"] = tiers
    df["tier_label"] = df["tier"].map(TIER_LABELS)

    # bootstrap stability: refit K-means on resampled countries, assign every country, compare tiers
    rng = np.random.default_rng(random_state)
    score = df["vulnerability_score"].to_numpy()
    agree = np.zeros(len(df))
    for _ in range(n_boot):
        idx = rng.integers(0, len(score), len(score))
        kb = KMeans(n_clusters=4, random_state=random_state, n_init=10).fit(score[idx].reshape(-1, 1))
        order = np.argsort(kb.cluster_centers_.ravel())
        remap = {int(c): i + 1 for i, c in enumerate(order)}
        agree += np.vectorize(remap.get)(kb.predict(score.reshape(-1, 1))) == tiers
    df["tier_stability"] = (agree / n_boot).round(3)

    if tsne:
        t = TSNE(n_components=2, perplexity=30, random_state=random_state).fit_transform(scaled)
        df["tsne_1"], df["tsne_2"] = t[:, 0], t[:, 1]

    diagnostics = {
        "feature_set": feature_set,
        "features": cols,
        "imputation": impute,
        "n_countries": int(len(df)),
        "n_imputed_countries": int(df["imputed"].sum()),
        "explained_variance_pc1_to_pc3": [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "pc1_loadings": {c: round(float(v), 4) for c, v in zip(cols, pca.components_[0])},
        "tier_centroids": sorted(round(float(c), 2) for c in km.cluster_centers_.ravel()),
        "tier_counts": {int(k): int(v) for k, v in df["tier"].value_counts().sort_index().items()},
        "silhouette_tiers_on_score": round(float(silhouette_score(score.reshape(-1, 1), tiers)), 4),
        "bootstrap_reps": n_boot,
        "mean_tier_stability": round(float(df["tier_stability"].mean()), 4),
        "countries_below_80pct_stability": int((df["tier_stability"] < 0.8).sum()),
    }
    return df, diagnostics
