"""Regression and sanity tests for the vulnerability index.

Run with:  pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from hvd import index, inform, paths


@pytest.fixture(scope="module")
def baseline():
    return pd.read_csv(paths.BASELINE_DIR / "processed_vulnerability_tiers.csv")


@pytest.fixture(scope="module")
def legacy():
    return index.build_index_legacy()


@pytest.fixture(scope="module")
def v11():
    df, diag = index.build_index(n_boot=50, tsne=False)
    return df, diag


# --- the refactored code reproduces the October 2026 notebook ---------------------------
def test_legacy_inputs_match_baseline(legacy, baseline):
    feats = [c for c in baseline.columns if c.endswith("_VALUE")]
    assert list(legacy["Region_ID"]) == list(baseline["Region_ID"])
    np.testing.assert_allclose(legacy[feats].to_numpy(float), baseline[feats].to_numpy(float), equal_nan=True)


def test_legacy_scores_match_baseline(legacy, baseline):
    np.testing.assert_allclose(legacy["Vulnerability_Score_PCA"], baseline["Vulnerability_Score_PCA"], atol=1e-9)


def test_legacy_tiers_match_baseline(legacy, baseline):
    assert (legacy["UNHCR_Tier"] == baseline["UNHCR_Tier"]).all()


# --- v1.1 fixes ---------------------------------------------------------------------------
def test_one_row_per_iso3(v11):
    df, _ = v11
    assert df["iso3"].is_unique
    assert len(df) == 191


def test_label_variants_are_merged(v11):
    df, _ = v11
    for iso in inform.label_variants()["iso3"]:
        assert (df["iso3"] == iso).sum() == 1


def test_imputed_flag(v11):
    df, diag = v11
    assert set(df.loc[df["imputed"], "iso3"]) == {"CUB", "LIE", "PRK"}
    assert (df.loc[df["imputed"], "n_imputed"] == 4).all()
    assert diag["n_imputed_countries"] == 3


def test_score_direction_and_range(v11):
    df, _ = v11
    assert df["vulnerability_score"].between(0, 100).all()
    assert df["vulnerability_score"].corr(df["inform_risk"]) > 0.9


def test_tiers_are_ordinal(v11):
    df, _ = v11
    means = df.groupby("tier")["vulnerability_score"].mean()
    assert list(means.index) == [1, 2, 3, 4]
    assert means.is_monotonic_increasing


def test_tier_stability_bounds(v11):
    df, _ = v11
    assert df["tier_stability"].between(0, 1).all()
