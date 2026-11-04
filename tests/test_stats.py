"""Tests for the statistics sprint code (no restricted data needed: synthetic inputs and public files only)."""
import numpy as np
import pandas as pd
import pytest

from hvd import paths
from hvd.stats import archetypes, cordex, country, locmatch, province


# ---------------------------------------------------------------- name matching ----
@pytest.fixture(scope="module")
def units():
    return locmatch.build_units(paths.ROOT)


@pytest.mark.parametrize("iso,text,expected,absent", [
    ("PHL", "Quezon City (National Capital Region)", {"PH-00"}, {"PH-QUE"}),
    ("PHL", "General Santos City and South Cotabato", {"PH-SCO"}, {"PH-NCO"}),
    ("PHL", "Eastern Samar, Leyte", {"PH-EAS", "PH-LEY"}, {"PH-WSA", "PH-SLE"}),
    ("PHL", "Cagayan de Oro (Misamis Oriental)", {"PH-MSR"}, {"PH-CAG"}),
    ("PHL", "Cagayan Valley, Bicol", {"PH-ISA", "PH-CAG", "PH-ALB", "PH-SOR"}, set()),
    ("PHL", "Region 3, 1 (Ilocos) and 12", {"PH-PAM", "PH-ILN", "PH-SCO"}, set()),
    ("PHL", "Maguindanao del Sur province (Bangsamoro Autonomous Region)", {"PH-MAG"}, {"PH-SLU", "PH-TAW"}),
    ("BGD", "Kishoreganj upazila, Nilphamari", {"Nilphamari"}, {"Kishoreganj"}),
    ("BGD", "Sherpur district (Mymensingh and Sindh divisions)", {"Sherpur"}, {"Mymensingh"}),
    ("BGD", "Cox’s Bazar, Chattogram, Cumilla", {"Cox's Bazar", "Chittagong", "Comilla"}, set()),
    ("AFG", "Herat region; Sar-e-Pul", {"AF-HER", "AF-SAR"}, set()),
])
def test_location_units(units, iso, text, expected, absent):
    got, _ = locmatch.location_units(iso, text, units)
    assert expected <= got
    assert not (absent & got)


# ---------------------------------------------------------------- co-occurrence ----
def test_cooccurrence_independent_hazards_near_chance():
    rng = np.random.default_rng(0)
    rows = []
    for c in range(60):
        for y in range(2000, 2026):
            for h, p in (("flood", 0.5), ("storm", 0.3)):
                if rng.random() < p:
                    rows.append({"iso3": f"C{c}", "year": y, "hgroup": h})
    t = country.cooccurrence(pd.DataFrame(rows), groups=["flood", "storm"], n_perm=199)
    assert 0.85 < t.lift_vs_null.iloc[0] < 1.15
    assert t.p_perm.iloc[0] > 0.01


def test_cooccurrence_detects_dependence():
    rng = np.random.default_rng(1)
    rows = []
    for c in range(60):
        for y in range(2000, 2026):
            a = rng.random() < 0.3
            if a:
                rows.append({"iso3": f"C{c}", "year": y, "hgroup": "drought"})
            if rng.random() < (0.8 if a else 0.1):
                rows.append({"iso3": f"C{c}", "year": y, "hgroup": "wildfire"})
    t = country.cooccurrence(pd.DataFrame(rows), groups=["drought", "wildfire"], n_perm=199)
    assert t.lift_vs_null.iloc[0] > 1.5
    assert t.p_perm.iloc[0] < 0.01


# ---------------------------------------------------------------- seasonality ----
def test_rayleigh():
    peaked = pd.Series([8, 9, 9, 9, 10, 9, 8, 9, 10, 9] * 3)
    flat = pd.Series(list(range(1, 13)) * 3)
    assert province.rayleigh(peaked)["p"] < 0.001
    assert abs(province.rayleigh(peaked)["mean_month"] - 9) < 1
    assert province.rayleigh(flat)["p"] > 0.5


# ---------------------------------------------------------------- SPI and indices ----
def test_spi_baseline_share_and_gaps():
    rng = np.random.default_rng(2)
    idx = pd.period_range("1986-01", "2025-12", freq="M").append(pd.period_range("2041-01", "2060-12", freq="M"))
    m = pd.DataFrame({"u": rng.gamma(2.0, 50, len(idx))}, index=idx)
    s = cordex.spi6(m)
    base = s[(s.index.year >= 1991) & (s.index.year <= 2020)]
    assert 0.12 < float((base.u <= -1).mean()) < 0.20
    # no 6-month total may bridge the 2026-2040 gap: the first five months of 2041 are undefined
    assert s.loc["2041-01":"2041-05", "u"].isna().all()
    assert np.isfinite(s.loc["2041-06", "u"])


def test_annual_extremes_known_values():
    days = [f"2000-01-{d:02d}" for d in range(1, 31)] * 12
    dates = [f"2000-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 31)]
    pr = np.zeros(360)
    pr[100:105] = 10.0          # one 5-day wet spell of 50 mm
    out, _ = cordex.annual_extremes(pd.DataFrame({"u": pr}, index=dates))
    assert out["rx5day"].loc[2000, "u"] == pytest.approx(50.0)
    assert out["cdd"].loc[2000, "u"] == 360 - 105
    assert out["prcptot"].loc[2000, "u"] == pytest.approx(50.0)


def test_kappa():
    a = np.array([1, 1, 0, 0, 1, 0, 0, 0])
    assert cordex.kappa(a, a) == pytest.approx(1.0)
    assert cordex.kappa(a, 1 - a) < 0


# ---------------------------------------------------------------- archetypes ----
def test_archetypes_recover_planted_groups():
    rng = np.random.default_rng(3)
    a = pd.DataFrame(rng.poisson([40, 4, 2, 1], (40, 4)), columns=["flood", "storm", "drought", "heat"])
    b = pd.DataFrame(rng.poisson([5, 40, 2, 1], (40, 4)), columns=a.columns)
    c = pd.DataFrame(rng.poisson([5, 3, 30, 10], (40, 4)), columns=a.columns)
    counts = pd.concat([a, b, c], ignore_index=True)
    lab, sel, prof, _ = archetypes.fit(counts, k=3, n_boot=20)
    truth = np.repeat([0, 1, 2], 40)
    from sklearn.metrics import adjusted_rand_score
    assert adjusted_rand_score(truth, lab) > 0.9


def test_thornthwaite_and_hot_days():
    idx = pd.period_range("1991-01", "2020-12", freq="M")
    seas = 25 + 3 * np.sin(2 * np.pi * (idx.month - 4) / 12)
    t = pd.DataFrame({"u": seas}, index=idx)
    nd = pd.Series(idx.days_in_month, index=idx)
    lat = pd.Series({"u": 14.0})
    pet = cordex.thornthwaite(t, nd, lat)
    assert (pet.u > 50).all() and (pet.u < 250).all()
    # warming raises PET; the heat index stays at the baseline value
    warm = cordex.thornthwaite(pd.concat([t, (t + 2).set_axis(idx + 360)]), pd.concat([nd, nd.set_axis(idx + 360)]), lat)
    assert warm.loc[idx + 360, "u"].mean() > pet.u.mean() * 1.05
    # daily: baseline share above own 95th percentile is about 18 days a year
    rng = np.random.default_rng(4)
    days = pd.date_range("1991-01-01", "2020-12-31").strftime("%Y-%m-%d")
    d = pd.DataFrame({"u": 25 + rng.normal(0, 2, len(days))}, index=days)
    hd, p95 = cordex.hot_days(d)
    assert 17 < hd.u.mean() < 19.5
    hd2, _ = cordex.hot_days(d + 2, p95)
    assert hd2.u.mean() > 80


def test_idmc_disaggregated_keeps_disaster_flows(tmp_path):
    from hvd.stats import idmc
    rows = pd.DataFrame({"ID": [1, 2, 3, 4, 4], "ISO3": ["PHL"] * 5, "Year": [2020] * 5,
                         "Figure cause": ["Disaster", "Disaster", "Conflict", "Disaster", "Disaster"],
                         "Figure category": ["Internal Displacements", "IDPs", "Internal Displacements", "Internal Displacements", "Internal Displacements"],
                         "Total figures": [100, 50, 70, 30, 30], "Hazard category": ["Weather related", "Weather related", None, "Geophysical", "Geophysical"],
                         "Hazard type": ["Storm", "Storm", None, "Earthquake", "Earthquake"], "Event ID": [9, 9, 8, 7, 7]})
    f = tmp_path / "IDMC_GIDD_Internal_Displacement_Disaggregated_2020.xlsx"
    with pd.ExcelWriter(f) as xw:
        rows.to_excel(xw, sheet_name="1_Disaggregated_Data", index=False)
    ev = idmc._disaggregated([str(f)])
    assert len(ev) == 2 and ev.displacements.sum() == 130          # stock, conflict and the duplicate figure dropped
    cy = idmc.country_year(ev, weather_only=True, y0=2020, y1=2020)
    assert int(cy.displacements.iloc[0]) == 100
