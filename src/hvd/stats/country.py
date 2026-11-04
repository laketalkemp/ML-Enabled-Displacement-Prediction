"""Country-level statistics: hazard signatures, trends, co-occurrence, vulnerability vs impacts.

All inputs derived from EM-DAT are restricted; callers write outputs to data/processed/emdat/ only.
"""
from __future__ import annotations

import itertools
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .emdat import CLIMATE, LABEL

Y0, Y1 = 2000, 2025
NYEARS = Y1 - Y0 + 1


# ------------------------------------------------------------------ signatures ----
def signatures(rec: pd.DataFrame, pop: pd.Series, gdp: pd.Series, groups=None) -> pd.DataFrame:
    """Long table: one row per country x hazard group, 2000-2025."""
    groups = groups or CLIMATE
    r = rec[rec.hgroup.isin(groups)]
    g = r.groupby(["iso3", "hgroup"])
    t = pd.DataFrame({
        "events": g.size(),
        "high_impact_events": g.high_impact.sum(),
        "deaths": g.deaths.sum(min_count=1),
        "affected": g.affected.sum(min_count=1),
        "damage_adj_kusd": g.damage_adj_kusd.sum(min_count=1),
        "deaths_median_per_event": g.deaths.median(),
        "deaths_p90_per_event": g.deaths.quantile(0.9),
        "affected_median_per_event": g.affected.median(),
        "share_deaths_missing": g.deaths.apply(lambda s: s.isna().mean()),
        "share_damage_missing": g.damage_adj_kusd.apply(lambda s: s.isna().mean()),
    }).reset_index()
    t["population"] = t.iso3.map(pop)
    t["gdp_usd"] = t.iso3.map(gdp)
    t["events_per_year"] = t.events / NYEARS
    t["deaths_per_100k_yr"] = t.deaths / t.population * 1e5 / NYEARS
    t["affected_per_100k_yr"] = t.affected / t.population * 1e5 / NYEARS
    t["damage_pct_gdp_yr"] = t.damage_adj_kusd * 1e3 / t.gdp_usd * 100 / NYEARS
    return t


def wide(sig: pd.DataFrame, value: str, groups=None) -> pd.DataFrame:
    groups = groups or CLIMATE
    return sig.pivot(index="iso3", columns="hgroup", values=value).reindex(columns=groups).fillna(0)


# ---------------------------------------------------------------------- trends ----
def trends(rec: pd.DataFrame, groups=None) -> pd.DataFrame:
    """Rate ratio per decade for record counts by hazard group, negative binomial with country fixed effects.
    Fit on all records and on high-impact records only (>=100 deaths or >=100,000 affected)."""
    groups = groups or CLIMATE
    rows = []
    for subset in ("all", "high_impact"):
        r = rec if subset == "all" else rec[rec.high_impact]
        for h in groups:
            c = r[r.hgroup == h].groupby(["iso3", "year"]).size()
            isos = c.index.get_level_values(0).unique()
            panel = (c.reindex(pd.MultiIndex.from_product([isos, range(Y0, Y1 + 1)], names=["iso3", "year"]), fill_value=0)
                     .rename("n").reset_index())
            # drop countries with a single event in 26 years: they carry no within-country trend information
            keep = panel.groupby("iso3").n.transform("sum") >= 2
            panel = panel[keep]
            panel["decade"] = (panel.year - 2012.5) / 10
            row = {"hazard": h, "subset": subset, "records": int(panel.n.sum()), "countries": int(panel.iso3.nunique())}
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m = smf.negativebinomial("n ~ decade + C(iso3)", panel).fit(disp=0, maxiter=300, method="bfgs")
                b, se = m.params["decade"], m.bse["decade"]
                row.update(rate_ratio_per_decade=np.exp(b), ci_low=np.exp(b - 1.96 * se), ci_high=np.exp(b + 1.96 * se),
                           p=m.pvalues["decade"], alpha=m.params.get("alpha", np.nan))
            except Exception as e:  # noqa: BLE001
                row.update(error=str(e)[:120])
            rows.append(row)
    t = pd.DataFrame(rows)
    ok = t.p.notna()
    t.loc[ok, "q_bh"] = multipletests(t.loc[ok, "p"], method="fdr_bh")[1]
    return t


def global_annual_counts(rec: pd.DataFrame, groups=None) -> pd.DataFrame:
    groups = groups or CLIMATE
    r = rec[rec.hgroup.isin(groups)]
    a = r.groupby(["year", "hgroup"]).size().unstack(fill_value=0).reindex(columns=groups, fill_value=0)
    hi = r[r.high_impact].groupby(["year", "hgroup"]).size().unstack(fill_value=0).reindex(columns=groups, fill_value=0)
    return a.join(hi, rsuffix="_high_impact")


# ---------------------------------------------------------------- co-occurrence ----
def _presence(rec, groups, unit="iso3"):
    p = (rec[rec.hgroup.isin(groups)].assign(v=1).pivot_table(index=[unit, "year"], columns="hgroup", values="v", aggfunc="max")
         .reindex(columns=groups).fillna(0).astype(bool))
    units = p.index.get_level_values(0).unique()
    full = pd.MultiIndex.from_product([units, range(Y0, Y1 + 1)], names=[unit, "year"])
    return p.reindex(full, fill_value=False)


def cooccurrence(rec: pd.DataFrame, groups=None, n_perm: int = 9999, seed: int = 42, unit: str = "iso3") -> pd.DataFrame:
    """Same-year co-occurrence of hazard pairs across place-years. Lift = P(A and B) / (P(A) P(B)); Jaccard.
    Null: years shuffled independently within each place x hazard (keeps each place's hazard frequency)."""
    groups = groups or CLIMATE
    P = _presence(rec, groups, unit)
    places = P.index.get_level_values(0)
    arr = P.to_numpy()  # (place-years, hazards)
    nplace = places.nunique()
    arr3 = arr.reshape(nplace, NYEARS, len(groups))
    rng = np.random.default_rng(seed)
    pairs = list(itertools.combinations(range(len(groups)), 2))

    def stats_of(a3):
        a = a3.reshape(-1, len(groups)).astype(float)
        pa = a.mean(0)
        both = np.array([(a[:, i] * a[:, j]).mean() for i, j in pairs])
        union = np.array([np.maximum(a[:, i], a[:, j]).mean() for i, j in pairs])
        lift = both / np.array([pa[i] * pa[j] for i, j in pairs])
        return lift, both / np.where(union > 0, union, np.nan)

    lift0, jac0 = stats_of(arr3)
    null = np.empty((n_perm, len(pairs)))
    for k in range(n_perm):
        sh = arr3.copy()
        for h in range(len(groups)):
            idx = rng.permuted(np.tile(np.arange(NYEARS), (nplace, 1)), axis=1)
            sh[:, :, h] = np.take_along_axis(arr3[:, :, h], idx, axis=1)
        null[k] = stats_of(sh)[0]
    rows = []
    for n, (i, j) in enumerate(pairs):
        nm = null[:, n]
        p = (1 + np.sum(np.abs(nm - nm.mean()) >= abs(lift0[n] - nm.mean()))) / (n_perm + 1)
        rows.append({"hazard_a": groups[i], "hazard_b": groups[j], "lift": lift0[n], "jaccard": jac0[n],
                     "lift_null_mean": nm.mean(), "lift_vs_null": lift0[n] / nm.mean(),
                     "null_low": np.quantile(nm, 0.025), "null_high": np.quantile(nm, 0.975), "p_perm": p})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p_perm, method="fdr_bh")[1]
    return t


def sequence_12m(rec: pd.DataFrame, groups=None, n_perm: int = 999, seed: int = 42, unit: str = "iso3") -> pd.DataFrame:
    """P(a record of B starts within 12 months after a record of A, same place), vs a null that shuffles
    the year of each record within its place and hazard (month kept)."""
    groups = groups or CLIMATE
    r = rec[rec.hgroup.isin(groups) & rec.month.notna()][[unit, "hgroup", "year", "month"]].copy()
    r["t"] = r.year * 12 + r.month.astype(int) - 1
    rng = np.random.default_rng(seed)

    def prob(df):
        out = {}
        by = {k: g for k, g in df.groupby([unit, "hgroup"])}
        for a, b in itertools.permutations(groups, 2):
            hits = tot = 0
            for (pl, h), ga in by.items():
                if h != a:
                    continue
                gb = by.get((pl, b))
                ta = ga.t.to_numpy()
                tot += len(ta)
                if gb is None:
                    continue
                tb = np.sort(gb.t.to_numpy())
                lo = np.searchsorted(tb, ta, side="left")
                hi = np.searchsorted(tb, ta + 12, side="right")
                hits += int(np.sum(hi > lo))
            out[(a, b)] = hits / tot if tot else np.nan
        return out

    obs = prob(r)
    nulls = {k: [] for k in obs}
    for _ in range(n_perm):
        s = r.copy()
        s["year"] = s.groupby([unit, "hgroup"]).year.transform(lambda y: rng.integers(Y0, Y1 + 1, len(y)))
        s["t"] = s.year * 12 + s.month.astype(int) - 1
        for k, v in prob(s).items():
            nulls[k].append(v)
    rows = []
    for (a, b), v in obs.items():
        nm = np.array(nulls[(a, b)])
        p = (1 + np.sum(nm >= v)) / (n_perm + 1)
        rows.append({"first": a, "then": b, "p_then_within_12m": v, "null_mean": nm.mean(), "ratio_to_null": v / nm.mean() if nm.mean() else np.nan, "p_perm": p})
    t = pd.DataFrame(rows)
    t["q_bh"] = multipletests(t.p_perm, method="fdr_bh")[1]
    return t


# --------------------------------------------------------- vulnerability vs impacts ----
def impact_models(rec: pd.DataFrame, cov: pd.DataFrame, outcome: str = "deaths", groups=None,
                  missing_as_zero: bool = False) -> pd.DataFrame:
    """Per hazard group: negative binomial of impact per record on vulnerability (V+C, per 10 points),
    with log population, INFORM hazard exposure and year as controls; SEs clustered by country.
    cov: index iso3 with columns vc (0-100), hazard_exposure, log_pop."""
    groups = groups or CLIMATE
    d = rec[rec.hgroup.isin(groups)].join(cov, on="iso3", how="inner")
    if missing_as_zero:
        d[outcome] = d[outcome].fillna(0)
    d = d[d[outcome].notna() & d.vc.notna() & d.log_pop.notna() & d.hazard_exposure.notna()].copy()
    d["vc10"] = d.vc / 10
    d["yr"] = (d.year - 2012.5) / 10
    d["y"] = d[outcome].round().astype(int)
    rows = []
    for h in groups + ["all_climate"]:
        x = d if h == "all_climate" else d[d.hgroup == h]
        f = "y ~ vc10 + log_pop + hazard_exposure + yr" + (" + C(hgroup)" if h == "all_climate" else "")
        row = {"hazard": h, "outcome": outcome, "records": len(x), "countries": x.iso3.nunique(),
               "share_zero": float((x.y == 0).mean()) if len(x) else np.nan}
        if len(x) < 60 or x.iso3.nunique() < 15:
            rows.append(row | {"note": "too few records"})
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = smf.negativebinomial(f, x).fit(disp=0, maxiter=500, method="bfgs",
                                                    cov_type="cluster", cov_kwds={"groups": pd.factorize(x.iso3)[0]})
            b, se = m.params["vc10"], m.bse["vc10"]
            row.update(irr_per_10pts=np.exp(b), ci_low=np.exp(b - 1.96 * se), ci_high=np.exp(b + 1.96 * se), p=m.pvalues["vc10"],
                       irr_hazard_exposure=np.exp(m.params["hazard_exposure"]), irr_log_pop=np.exp(m.params["log_pop"]),
                       irr_per_decade=np.exp(m.params["yr"]), alpha=m.params.get("alpha", np.nan))
        except Exception as e:  # noqa: BLE001
            row.update(note=str(e)[:120])
        rows.append(row)
    t = pd.DataFrame(rows)
    ok = t.get("p", pd.Series(dtype=float)).notna()
    if ok.any():
        t.loc[ok, "q_bh"] = multipletests(t.loc[ok, "p"], method="fdr_bh")[1]
    return t


def tier_differences(rec: pd.DataFrame, tiers: pd.Series, outcome: str = "deaths", groups=None) -> pd.DataFrame:
    """Kruskal-Wallis of impact per record across the four tiers, with epsilon-squared, per hazard group."""
    groups = groups or CLIMATE
    d = rec[rec.hgroup.isin(groups)].assign(tier=lambda x: x.iso3.map(tiers)).dropna(subset=["tier", outcome])
    rows = []
    for h in groups + ["all_climate"]:
        x = d if h == "all_climate" else d[d.hgroup == h]
        samples = [x.loc[x.tier == k, outcome].to_numpy() for k in (1, 2, 3, 4)]
        meds = [float(np.median(s)) if len(s) else np.nan for s in samples]
        ns = [len(s) for s in samples]
        if sum(n > 4 for n in ns) < 3:
            rows.append({"hazard": h, "outcome": outcome, "n": sum(ns), "note": "too few"})
            continue
        H, p = stats.kruskal(*[s for s in samples if len(s) > 0])
        n = sum(ns)
        rows.append({"hazard": h, "outcome": outcome, "n": n, "H": H, "p": p, "epsilon2": (H - len([s for s in samples if len(s)]) + 1) / (n - len([s for s in samples if len(s)])),
                     **{f"median_tier{k}": meds[k - 1] for k in (1, 2, 3, 4)}, **{f"n_tier{k}": ns[k - 1] for k in (1, 2, 3, 4)}})
    t = pd.DataFrame(rows)
    ok = t.get("p", pd.Series(dtype=float)).notna()
    if ok.any():
        t.loc[ok, "q_bh"] = multipletests(t.loc[ok, "p"], method="fdr_bh")[1]
    return t


def impact_hurdle(rec: pd.DataFrame, cov: pd.DataFrame, outcome: str = "deaths", groups=None) -> pd.DataFrame:
    """Two-part (hurdle) model per hazard group. EM-DAT leaves impacts blank instead of recording zero, so:
    part 1, logistic: P(impact recorded > 0) on V+C (per 10 points), log population, hazard exposure, year;
    part 2, given impact > 0: negative binomial for deaths, OLS on log(affected) for people affected.
    SEs clustered by country. Reported: odds ratio (part 1) and rate ratio / ratio of geometric means (part 2)."""
    groups = groups or CLIMATE
    d = rec[rec.hgroup.isin(groups)].join(cov, on="iso3", how="inner")
    d = d[d.vc.notna() & d.log_pop.notna() & d.hazard_exposure.notna()].copy()
    d["vc10"] = d.vc / 10
    d["yr"] = (d.year - 2012.5) / 10
    d["any"] = (d[outcome].fillna(0) > 0).astype(int)
    rows = []
    for h in groups + ["all_climate"]:
        x = d if h == "all_climate" else d[d.hgroup == h]
        fe = " + C(hgroup)" if h == "all_climate" else ""
        row = {"hazard": h, "outcome": outcome, "records": len(x), "countries": int(x.iso3.nunique()),
               "share_recorded": float(x["any"].mean()) if len(x) else np.nan}
        cl = lambda z: {"groups": pd.factorize(z.iso3)[0]}  # noqa: E731
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m1 = smf.logit("any ~ vc10 + log_pop + hazard_exposure + yr" + fe, x).fit(disp=0, cov_type="cluster", cov_kwds=cl(x))
            b, se = m1.params["vc10"], m1.bse["vc10"]
            row.update(or_recorded=np.exp(b), or_ci_low=np.exp(b - 1.96 * se), or_ci_high=np.exp(b + 1.96 * se), p_recorded=m1.pvalues["vc10"])
        except Exception as e:  # noqa: BLE001
            row.update(note1=str(e)[:100])
        pos = x[x["any"] == 1].copy()
        row["records_positive"] = len(pos)
        if len(pos) >= 60 and pos.iso3.nunique() >= 15:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if outcome == "deaths":
                        pos["y"] = pos[outcome].round().astype(int)
                        m2 = smf.negativebinomial("y ~ vc10 + log_pop + hazard_exposure + yr" + fe, pos).fit(
                            disp=0, maxiter=500, method="bfgs", cov_type="cluster", cov_kwds=cl(pos))
                    else:
                        pos["y"] = np.log(pos[outcome])
                        m2 = smf.ols("y ~ vc10 + log_pop + hazard_exposure + yr" + fe, pos).fit(cov_type="cluster", cov_kwds=cl(pos))
                b, se = m2.params["vc10"], m2.bse["vc10"]
                row.update(ratio_if_recorded=np.exp(b), ratio_ci_low=np.exp(b - 1.96 * se), ratio_ci_high=np.exp(b + 1.96 * se),
                           p_if_recorded=m2.pvalues["vc10"])
            except Exception as e:  # noqa: BLE001
                row.update(note2=str(e)[:100])
        else:
            row["note2"] = "too few records with impact > 0"
        rows.append(row)
    t = pd.DataFrame(rows)
    for pc, qc in (("p_recorded", "q_recorded"), ("p_if_recorded", "q_if_recorded")):
        if pc in t:
            ok = t[pc].notna()
            t.loc[ok, qc] = multipletests(t.loc[ok, pc], method="fdr_bh")[1]
    return t
