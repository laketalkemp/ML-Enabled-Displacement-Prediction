"""Hazard archetypes: cluster places by their hazard profile (mix of hazards plus overall frequency).
K-means, Gaussian mixture (BIC) and Ward hierarchical are compared; k is chosen by silhouette and
bootstrap stability (adjusted Rand index)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


def profile_features(counts: pd.DataFrame, smooth: float = 0.5, include_total: bool = False) -> pd.DataFrame:
    """counts: places x hazards (event counts). Features: centred log-ratio of the smoothed hazard mix,
    plus log total frequency. Smoothing keeps places with few events from getting extreme shares."""
    c = counts.astype(float) + smooth
    clr = np.log(c).sub(np.log(c).mean(axis=1), axis=0)
    clr.columns = [f"mix_{h}" for h in counts.columns]
    if include_total:
        clr["log_total"] = np.log1p(counts.sum(axis=1))
    return clr


def select_k(X: np.ndarray, ks=range(2, 9), n_boot: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for k in ks:
        km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(X)
        sil = silhouette_score(X, km.labels_)
        aris = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(X), len(X))
            kb = KMeans(n_clusters=k, n_init=5, random_state=int(rng.integers(1e9))).fit(X[idx])
            aris.append(adjusted_rand_score(km.labels_, kb.predict(X)))
        gmm = GaussianMixture(n_components=k, covariance_type="diag", n_init=5, random_state=seed).fit(X)
        ward = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
        rows.append({"k": k, "silhouette_kmeans": sil, "stability_ari": float(np.mean(aris)),
                     "gmm_bic": gmm.bic(X), "ari_kmeans_vs_gmm": adjusted_rand_score(km.labels_, gmm.predict(X)),
                     "ari_kmeans_vs_ward": adjusted_rand_score(km.labels_, ward)})
    return pd.DataFrame(rows)


def choose_k(sel: pd.DataFrame, min_k: int = 3, min_stability: float = 0.7) -> int:
    """Largest-silhouette k among k >= min_k whose bootstrap stability (mean ARI) is at least min_stability;
    falls back to min_k. k = 2 is excluded because it only splits flood- from storm-led places."""
    ok = sel[(sel.k >= min_k) & (sel.stability_ari >= min_stability)]
    if not len(ok):
        return min_k
    return int(ok.sort_values("silhouette_kmeans", ascending=False).k.iloc[0])


def fit(counts: pd.DataFrame, k: int | None = None, seed: int = 42, n_boot: int = 200, include_total: bool = False):
    """Returns (labels Series, selection table, profile table with mean hazard shares per archetype,
    per-place membership probability from a Gaussian mixture with the same k)."""
    F = profile_features(counts, include_total=include_total)
    X = StandardScaler().fit_transform(F)
    sel = select_k(X, n_boot=n_boot, seed=seed)
    k = k or choose_k(sel)
    km = KMeans(n_clusters=k, n_init=50, random_state=seed).fit(X)
    lab = pd.Series(km.labels_, index=counts.index, name="archetype")
    gmm = GaussianMixture(n_components=k, covariance_type="diag", n_init=10, random_state=seed,
                          means_init=km.cluster_centers_).fit(X)
    member_p = pd.Series(gmm.predict_proba(X).max(axis=1), index=counts.index, name="membership_p")
    shares = counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0)
    prof = shares.groupby(lab).mean()
    prof["places"] = lab.value_counts().sort_index()
    prof["median_events"] = counts.sum(axis=1).groupby(lab).median()
    # order archetypes by total frequency and name them by their two dominant hazards
    order = prof.median_events.sort_values(ascending=False).index
    remap = {old: new for new, old in enumerate(order, start=1)}
    lab = lab.map(remap)
    prof.index = prof.index.map(remap)
    prof = prof.sort_index()
    hz = list(counts.columns)
    prof["name"] = [" + ".join(prof.loc[i, hz].astype(float).nlargest(2).index) for i in prof.index]
    prof["mean_membership_p"] = member_p.groupby(lab).mean()
    return lab, sel, prof, member_p


def compare_with(labels: pd.Series, other: pd.Series) -> dict:
    """Contingency comparison of archetypes with another grouping (e.g. vulnerability tiers)."""
    j = pd.concat([labels, other], axis=1, join="inner").dropna()
    ct = pd.crosstab(j.iloc[:, 0], j.iloc[:, 1])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    n = ct.to_numpy().sum()
    v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
    return {"n": int(n), "chi2": chi2, "dof": int(dof), "p": p, "cramers_v": v,
            "ari": adjusted_rand_score(j.iloc[:, 0], j.iloc[:, 1]), "table": ct}
