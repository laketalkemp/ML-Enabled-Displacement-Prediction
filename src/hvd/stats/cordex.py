"""CORDEX province series (from scripts/download_cordex.py): monthly aggregation, SPI-6 with a fixed
1991-2020 baseline (gaps allowed), daily extreme-precipitation indices, evaluation against ERA5-Land,
and future change with ensemble agreement.

SPI here is computed with one implementation for both the models and ERA5-Land so they are comparable:
6-month precipitation totals per calendar month, a two-parameter gamma fitted to the 1991-2020 totals
(with the share of zero totals handled separately), then mapped to standard normal quantiles. The fit is
applied unchanged to any later period, so future SPI measures change relative to the baseline climate.
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np
import pandas as pd
from scipy import stats

BASE0, BASE1 = 1991, 2020
FUT = {"2026-2045": (2026, 2045), "2041-2070": (2041, 2070), "2071-2099": (2071, 2099)}
CHUNK_RE = re.compile(r"(?P<rcm>[^_]+(?:_[^_]+)*)__(?P<gcm>[^_]+(?:_[^_]+)*)__(?P<exp>[a-z0-9_]+)__(?P<y0>\d{4})-(?P<y1>\d{4})\.csv\.gz$")


def inventory(root: str) -> pd.DataFrame:
    rows = []
    for f in glob.glob(os.path.join(root, "*", "*", "*.csv.gz")):
        iso, var = f.split(os.sep)[-3:-1]
        m = CHUNK_RE.search(os.path.basename(f))
        if m:
            rows.append({"iso": iso, "var": var, **m.groupdict(), "file": f})
    t = pd.DataFrame(rows)
    if len(t):
        t[["y0", "y1"]] = t[["y0", "y1"]].astype(int)
    return t


def read_daily(files) -> pd.DataFrame:
    d = pd.concat([pd.read_csv(f, index_col=0) for f in sorted(files)])
    d = d[~d.index.duplicated()].sort_index()
    return d


def monthly(daily: pd.DataFrame, how: str) -> pd.DataFrame:
    """Daily (date strings, any model calendar) -> monthly. how: 'sum' (precipitation) or 'mean' (temperature)."""
    ym = daily.index.str.slice(0, 7)
    g = daily.groupby(ym)
    m = g.sum(min_count=20) if how == "sum" else g.mean()
    m.index = pd.PeriodIndex(m.index, freq="M")
    return m


def run_series(inv: pd.DataFrame, iso: str, var: str, rcm: str, gcm: str, scenario: str) -> pd.DataFrame:
    """Daily series for one model run: historical + RCP8.5 to 2025 (observed period), plus the scenario's
    chunks from 2026 on (2026-2040 when downloaded, then 2041-2099) if scenario is rcp_2_6 or rcp_8_5.
    Evaluation runs: scenario='evaluation'."""
    s = inv[(inv.iso == iso) & (inv["var"] == var) & (inv.rcm == rcm) & (inv.gcm == gcm)]
    if scenario == "evaluation":
        files = s[s.exp == "evaluation"].file
    else:
        files = pd.concat([s[s.exp == "historical"].file, s[(s.exp == "rcp_8_5") & (s.y1 <= 2025)].file,
                           s[(s.exp == scenario) & (s.y0 >= 2026)].file])
    return read_daily(files) if len(files) else pd.DataFrame()


# ------------------------------------------------------------------------- SPI ----
def accum(m: pd.DataFrame, n: int = 6) -> pd.DataFrame:
    """n-month totals that never bridge a gap in the monthly index."""
    full = pd.period_range(m.index.min(), m.index.max(), freq="M")
    r = m.reindex(full).rolling(n, min_periods=n).sum()
    return r.loc[m.index]


def spi_fit(acc: pd.DataFrame, y0: int = BASE0, y1: int = BASE1) -> dict:
    """Per unit and calendar month: (q0 = share of zeros, gamma shape, gamma scale) from the baseline."""
    base = acc[(acc.index.year >= y0) & (acc.index.year <= y1)]
    fits = {}
    for u in acc.columns:
        for mth in range(1, 13):
            x = base.loc[base.index.month == mth, u].dropna().to_numpy()
            if len(x) < 10:
                fits[(u, mth)] = None
                continue
            q0 = np.mean(x <= 0)
            pos = x[x > 0]
            a, _, sc = stats.gamma.fit(pos, floc=0) if len(pos) >= 5 else (np.nan, 0, np.nan)
            fits[(u, mth)] = (q0, a, sc)
    return fits


def spi_apply(acc: pd.DataFrame, fits: dict) -> pd.DataFrame:
    out = pd.DataFrame(index=acc.index, columns=acc.columns, dtype=float)
    months = acc.index.month
    for u in acc.columns:
        for mth in range(1, 13):
            f = fits.get((u, mth))
            sel = months == mth
            if f is None or not np.isfinite(f[1]):
                continue
            q0, a, sc = f
            x = acc.loc[sel, u].to_numpy()
            p = q0 + (1 - q0) * stats.gamma.cdf(np.where(x > 0, x, 0), a, scale=sc)
            p = np.where(x <= 0, q0 / 2 if q0 > 0 else 1e-6, p)
            z = stats.norm.ppf(np.clip(p, 1e-6, 1 - 1e-6))
            out.loc[sel, u] = np.where(np.isnan(x), np.nan, z)   # missing totals stay missing
    return out


def spi6(monthly_pr: pd.DataFrame) -> pd.DataFrame:
    acc = accum(monthly_pr, 6)
    return spi_apply(acc, spi_fit(acc))


# ------------------------------------------------------------- PET and SPEI ----
MID_DOY = np.array([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349])


def daylength(lat: float, months) -> np.ndarray:
    """Mean daylight hours for calendar months at a latitude (FAO-56 solar declination, mid-month day)."""
    j = MID_DOY[np.asarray(months) - 1]
    dec = 0.409 * np.sin(2 * np.pi * j / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(np.radians(lat)) * np.tan(dec), -1, 1))
    return 24 * ws / np.pi


def thornthwaite(tmon: pd.DataFrame, ndays: pd.Series, lat: pd.Series) -> pd.DataFrame:
    """Monthly PET (mm) by Thornthwaite (1948). The heat index comes from the unit's own 1991-2020 climatology and
    is held fixed, so warming raises PET. Above 26.5 C the Willmott, Rowe & Mintz (1985) form is used, which stops
    the original power law from running away at tropical temperatures. ndays: days in each month (model calendar)."""
    base = tmon[(tmon.index.year >= BASE0) & (tmon.index.year <= BASE1)]
    clim = base.groupby(base.index.month).mean().clip(lower=0)
    heat = ((clim / 5) ** 1.514).sum()
    a = 6.75e-7 * heat ** 3 - 7.71e-5 * heat ** 2 + 1.792e-2 * heat + 0.49239
    pet = 16 * (10 * tmon.clip(lower=0) / heat) ** a
    pet = pet.where(tmon < 26.5, -415.85 + 32.24 * tmon - 0.43 * tmon ** 2)
    L = pd.DataFrame({u: daylength(float(lat[u]), tmon.index.month) for u in tmon.columns}, index=tmon.index)
    return pet * L / 12 * (ndays.reindex(tmon.index).to_numpy()[:, None] / 30)


def spei6(pr_m: pd.DataFrame, pet_m: pd.DataFrame, y0: int = BASE0, y1: int = BASE1) -> pd.DataFrame:
    """SPEI-6 (Pearson III, climate-indices, as in the ERA5-Land layer) calibrated on y0-y1; gaps stay missing."""
    os.environ.setdefault("CLIMATE_INDICES_LOG_LEVEL", "WARNING")
    from climate_indices import compute, indices
    full = pd.period_range(f"{pr_m.index.min().year}-01", f"{pr_m.index.max().year}-12", freq="M")
    P, E = pr_m.reindex(full), pet_m.reindex(full)
    out = {u: indices.spei(P[u].to_numpy(float), E[u].to_numpy(float), 6, indices.Distribution.pearson,
                           compute.Periodicity.monthly, full[0].year, y0, y1) for u in pr_m.columns}
    return pd.DataFrame(out, index=full).loc[pr_m.index]


def hot_days(daily_tas: pd.DataFrame, p95: pd.Series | None = None):
    """Days per year with daily mean temperature above the unit's own 1991-2020 95th percentile (about 18 by
    construction in the baseline). Shares are scaled to 365.25 days so 360-day model calendars compare."""
    yrs = daily_tas.index.str.slice(0, 4).astype(int)
    if p95 is None:
        p95 = daily_tas[(yrs >= BASE0) & (yrs <= BASE1)].quantile(0.95)
    n = daily_tas.groupby(yrs).size()
    out = (daily_tas > p95).groupby(yrs).mean() * 365.25
    return out[n >= 300], p95


# ---------------------------------------------------------- daily extreme indices ----
def _max_run(mask: np.ndarray) -> np.ndarray:
    """Longest run of True along axis 0, per column."""
    best = np.zeros(mask.shape[1], int)
    cur = np.zeros(mask.shape[1], int)
    for row in mask:
        cur = np.where(row, cur + 1, 0)
        best = np.maximum(best, cur)
    return best


def annual_extremes(daily_pr: pd.DataFrame, wet_p95: pd.Series | None = None) -> dict:
    """Per year and unit: CDD (longest run of days < 1 mm), Rx5day (max 5-day total), R95p (total on days above
    the baseline 95th percentile of wet days), PRCPTOT (total on wet days)."""
    yrs = daily_pr.index.str.slice(0, 4).astype(int)
    if wet_p95 is None:
        b = daily_pr[(yrs >= BASE0) & (yrs <= BASE1)]
        wet_p95 = b.where(b >= 1).quantile(0.95)
    out = {k: {} for k in ("cdd", "rx5day", "r95p", "prcptot")}
    for y in np.unique(yrs):
        d = daily_pr[yrs == y]
        if len(d) < 300:
            continue
        a = d.to_numpy()
        out["cdd"][y] = _max_run(a < 1)
        out["rx5day"][y] = pd.DataFrame(a).rolling(5).sum().max().to_numpy()
        out["r95p"][y] = np.where(a > wet_p95.to_numpy(), a, 0).sum(0)
        out["prcptot"][y] = np.where(a >= 1, a, 0).sum(0)
    return {k: pd.DataFrame(v, index=daily_pr.columns).T for k, v in out.items()}, wet_p95


# ----------------------------------------------------------------- comparisons ----
def kappa(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    po = np.mean(a == b)
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return (po - pe) / (1 - pe) if pe < 1 else np.nan


def evaluate_monthly(model_pr: pd.DataFrame, obs_pr: pd.DataFrame, y0: int = 1991, y1: int = 2016) -> pd.DataFrame:
    """Per unit: bias (%), correlation of monthly anomalies, RMSE (mm/month), and drought-month agreement (kappa,
    SPI-6 <= -1 with each series calibrated on its own 1991-2016 values)."""
    idx = model_pr.index.intersection(obs_pr.index)
    idx = idx[(idx.year >= y0) & (idx.year <= y1)]
    m, o = model_pr.loc[idx], obs_pr.loc[idx, model_pr.columns.intersection(obs_pr.columns)]
    m = m[o.columns]
    am = m - m.groupby(m.index.month).transform("mean")
    ao = o - o.groupby(o.index.month).transform("mean")
    accm, acco = accum(m, 6), accum(o, 6)
    sm = spi_apply(accm, spi_fit(accm, y0, y1))
    so = spi_apply(acco, spi_fit(acco, y0, y1))
    rows = []
    for u in o.columns:
        ok = sm[u].notna() & so[u].notna()
        rows.append({"unit_id": u, "bias_pct": (m[u].mean() / o[u].mean() - 1) * 100,
                     "anomaly_corr": np.corrcoef(am[u], ao[u])[0, 1], "rmse_mm": float(np.sqrt(((m[u] - o[u]) ** 2).mean())),
                     "spi6_corr": np.corrcoef(sm.loc[ok, u], so.loc[ok, u])[0, 1],
                     "drought_kappa": kappa(sm.loc[ok, u] <= -1, so.loc[ok, u] <= -1)})
    return pd.DataFrame(rows)


def agreement(changes: pd.DataFrame) -> pd.DataFrame:
    """changes: rows = runs, columns = units. Ensemble median and the number of runs agreeing on its sign."""
    med = changes.median()
    agree = (np.sign(changes) == np.sign(med)).sum()
    return pd.DataFrame({"median": med, "runs": changes.notna().sum(), "agree_sign": agree,
                         "robust": agree >= np.ceil(0.8 * changes.notna().sum())})
