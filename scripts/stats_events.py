"""Event-level space-time clustering of EM-DAT climate-hazard events in the three regions (December analysis,
run Nov 3, 2026). Internal: every output here derives from EM-DAT records and stays out of the repository.

Events are EM-DAT records for floods, storms, wet landslides and extreme temperature, 2000-2025, placed on the provinces
or districts they list (record_unit_assignment). Drought and wildfire records are left out: there are too few and
their start dates mean little.

  1. Knox test for space-time interaction. Two events are "near in space" when they share a province or their provinces
     are neighbours (the weights used elsewhere: 5 nearest in the Philippines, shared border elsewhere), and "near in
     time" when they start within T days (15, 30, 60). The observed count of near-near pairs is compared with two nulls,
     999 draws each:
       dates  - start dates shuffled among the region's events (keeps the regional season);
       years  - only the years shuffled, each event keeping its month and day (keeps each place's own season, so an
                excess means events bunch within the same season more than seasons alone explain).
     The same counts are split into same-hazard and cross-hazard pairs (for example a typhoon then a flood).
  2. HDBSCAN episodes: precomputed distance max(km / S, days / 30), with S the region's typical neighbour distance and
     km the shortest distance between the two events' provinces (0 when they share one). Episode share is compared with
     the same clustering on year-shuffled dates.
  3. Which provinces sit in multi-event episodes, and is that related to wealth (Relative Wealth Index, Spearman)?
  4. Event locations (analysis plan, Aim 3 item 3): HDBSCAN with haversine distance on flood records that carry
     coordinates, all countries, with coverage reported.
    python scripts/stats_events.py
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from sklearn.cluster import HDBSCAN  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import emdat, province as P, spatial as S  # noqa: E402

OUT = paths.PROCESSED / "emdat" / "stats" / "events"
OUT.mkdir(parents=True, exist_ok=True)
HAZ = ["flood", "storm", "wet_mass_mov", "extreme_temp"]
TS = (15, 30, 60)
B = 999
rng = np.random.default_rng(42)
R_EARTH = 6371.0


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1)[:, None], np.radians(lat2)[None, :]
    dl = np.radians(lon2)[None, :] - np.radians(lon1)[:, None]
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ------------------------------------------------------------------ events with dates and provinces ----
rec = emdat.load_records()
raw = pd.read_excel(emdat.emdat_file(), sheet_name="EM-DAT Data", usecols=["DisNo.", "Start Day", "Event Name"])
rec = rec.merge(raw.rename(columns={"DisNo.": "disno", "Start Day": "day", "Event Name": "event_name"}), on="disno", how="left")
asg = pd.read_csv(paths.EMDAT_DERIVED_DIR / "record_unit_assignment_PHL_AFG_BGD.csv").rename(columns={"DisNo.": "disno"})
ev = rec[rec.iso3.isin(P.REGIONS) & rec.hgroup.isin(HAZ)].merge(asg[["disno", "units", "unit_source", "n_units"]], on="disno", how="left")
coverage = {"records": int(len(ev)), "no_units": int(ev.units.isna().sum()), "no_month": int(ev.month.isna().sum()),
            "day_imputed_15": int((ev.month.notna() & ev.day.isna()).sum())}
ev = ev[ev.units.notna() & ev.month.notna()].copy()
ev["date"] = pd.to_datetime(dict(year=ev.year, month=ev.month.astype(int), day=ev.day.fillna(15).astype(int)), errors="coerce")
ev = ev[ev.date.notna()].reset_index(drop=True)
ev["unit_list"] = ev.units.str.split(";")
coverage["events_used"] = int(len(ev))
coverage["by_region_hazard"] = ev.groupby(["iso3", "hgroup"]).size().unstack(fill_value=0).to_dict("index")


def region_geometry(iso):
    u = P.load_units(iso).reset_index(drop=True)
    pt = u.geometry.representative_point()
    D = hav(pt.y.values, pt.x.values, pt.y.values, pt.x.values)
    kind, k = P.WEIGHTS[iso]
    w = S.make_weights(u, kind, k or 5)
    N = np.eye(len(u), dtype=bool)
    for i, nb in w.neighbors.items():
        N[i, nb] = True
    N = N | N.T
    s = np.median([D[i, N[i] & (np.arange(len(u)) != i)].max() for i in range(len(u))])
    return u.unit_id.tolist(), D, N, float(s)


def pair_space(e, ids, D, N):
    """Event x event: near (share a unit or neighbouring units) and shortest unit-to-unit distance in km."""
    pos = {x: i for i, x in enumerate(ids)}
    M = np.zeros((len(e), len(ids)), bool)
    for r, ul in enumerate(e.unit_list):
        M[r, [pos[x] for x in ul if x in pos]] = True
    near = (M.astype(int) @ N.astype(int) @ M.T.astype(int)) > 0
    dmin_u = np.stack([D[:, m].min(1) if m.any() else np.full(len(ids), np.inf) for m in M])   # event -> each unit
    km = np.stack([dmin_u[:, m].min(1) if m.any() else np.full(len(e), np.inf) for m in M]).T
    return near, np.minimum(km, km.T)


def day_matrix(dates):
    t = dates.values.astype("datetime64[D]").astype(np.int64)
    return np.abs(t[:, None] - t[None, :])


def shuffled_dates(e, how):
    if how == "dates":
        return pd.Series(rng.permutation(e.date.values), index=e.index)
    yrs = rng.permutation(e.year.values)
    m, d = e.date.dt.month.values, e.date.dt.day.values
    return pd.Series(pd.to_datetime(dict(year=yrs, month=m, day=np.where((m == 2) & (d == 29), 28, d))), index=e.index)


knox_rows, episodes, members, unit_rows, null_rows = [], [], [], [], []
for iso in P.REGIONS:
    e = ev[ev.iso3 == iso].reset_index(drop=True)
    ids, D, N, s_km = region_geometry(iso)
    near, km = pair_space(e, ids, D, N)
    iu = np.triu_indices(len(e), 1)
    hz = e.hgroup.to_numpy(dtype=str)
    same = (hz[:, None] == hz[None, :])[iu]
    sn = near[iu]
    obs_days = day_matrix(e.date)[iu]
    # ---- Knox
    nulls = {how: [day_matrix(shuffled_dates(e, how))[iu].astype(np.int16) for _ in range(B)] for how in ("dates", "years")}
    for T in TS:
        for part, mask in (("all", np.ones_like(sn)), ("same hazard", same), ("cross hazard", ~same)):
            o = int((sn & (obs_days <= T) & mask).sum())
            row = {"region": iso, "days": T, "pairs": part, "events": len(e), "observed": o}
            for how, draws in nulls.items():
                x = np.array([(sn & (d <= T) & mask).sum() for d in draws])
                row.update({f"expected_{how}": float(x.mean()), f"ratio_{how}": o / x.mean() if x.mean() else np.nan,
                            f"p_{how}": float((1 + (x >= o).sum()) / (1 + B))})
            knox_rows.append(row)
    # cross-hazard pairs by hazard combination (30 days)
    for a_, b_ in [("storm", "flood"), ("flood", "wet_mass_mov"), ("storm", "wet_mass_mov"), ("flood", "extreme_temp")]:
        m = (((hz[:, None] == a_) & (hz[None, :] == b_)) | ((hz[:, None] == b_) & (hz[None, :] == a_)))[iu]
        if not m.any():
            continue
        o = int((sn & (obs_days <= 30) & m).sum())
        x = np.array([(sn & (d <= 30) & m).sum() for d in nulls["years"]])
        knox_rows.append({"region": iso, "days": 30, "pairs": f"{a_} + {b_}", "events": len(e), "observed": o,
                          "expected_years": float(x.mean()), "ratio_years": o / x.mean() if x.mean() else np.nan,
                          "p_years": float((1 + (x >= o).sum()) / (1 + B))})
    # ---- HDBSCAN episodes
    from sklearn.cluster import DBSCAN
    CONFIGS = {"hdbscan_eom_3_2": ("h", 3, 2, "eom"), "hdbscan_eom_2_2": ("h", 2, 2, "eom"),
               "hdbscan_leaf_2_2": ("h", 2, 2, "leaf"), "hdbscan_eom_5_3": ("h", 5, 3, "eom"), "dbscan_eps1_2": ("d", 2, 2, None)}
    MAIN = "hdbscan_eom_3_2"

    def episodes_of(days_mat, cfg):
        kind, mcs, ms, sel = CONFIGS[cfg]
        Dst = np.maximum(km / s_km, days_mat / 30.0)
        np.fill_diagonal(Dst, 0)
        if kind == "d":                      # neighbours within S km and 30 days, chained
            return DBSCAN(eps=1.0, min_samples=ms, metric="precomputed").fit(Dst).labels_
        return HDBSCAN(metric="precomputed", min_cluster_size=mcs, min_samples=ms, cluster_selection_method=sel,
                       copy=True).fit(Dst).labels_

    def spans(lab):
        d = pd.Series(e.date.values)[lab >= 0].groupby(lab[lab >= 0]).agg(lambda x: (x.max() - x.min()).days)
        return float(d.median()) if len(d) else np.nan

    null_days = [day_matrix(shuffled_dates(e, "years")) for _ in range(99)]
    for cfg in CONFIGS:
        lab = episodes_of(day_matrix(e.date), cfg)
        sh = np.mean(lab >= 0)
        null_share = np.array([np.mean(episodes_of(dm, cfg) >= 0) for dm in null_days])
        null_rows.append({"region": iso, "config": cfg, "events": len(e), "neighbour_scale_km": s_km,
                          "episodes": int(lab.max() + 1), "share_in_episodes": float(sh),
                          "median_span_days": spans(lab), "null_share_mean": float(null_share.mean()),
                          "null_share_p95": float(np.quantile(null_share, 0.95)),
                          "p": float((1 + np.sum(null_share >= sh)) / (1 + len(null_share)))})
        if cfg == MAIN:
            e["episode"] = lab
    for k, g in e[e.episode >= 0].groupby("episode"):
        allu = sorted(set(sum(g.unit_list.tolist(), [])))
        episodes.append({"region": iso, "episode": int(k), "events": len(g), "start": g.date.min().date(), "end": g.date.max().date(),
                         "span_days": int((g.date.max() - g.date.min()).days), "hazards": " + ".join(sorted(g.hgroup.unique())),
                         "multi_hazard": g.hgroup.nunique() > 1, "units": len(allu),
                         "deaths": float(g.deaths.fillna(0).sum()), "affected": float(g.affected.fillna(0).sum()),
                         "names": "; ".join(sorted({str(x) for x in g.event_name.dropna()}))[:200]})
    members.append(e[["disno", "iso3", "hgroup", "date", "event_name", "n_units", "episode"]])
    # ---- provinces in episodes
    ex = e.explode("unit_list")
    t = ex.groupby("unit_list").agg(events=("disno", "nunique"), in_episode=("episode", lambda x: int((x >= 0).sum())))
    t["share_in_episode"] = t.in_episode / t.events
    t["region"] = iso
    unit_rows.append(t)

knox = pd.DataFrame(knox_rows)
from statsmodels.stats.multitest import multipletests  # noqa: E402
ok = knox.p_years.notna()
knox.loc[ok, "q_years"] = multipletests(knox.loc[ok, "p_years"], method="fdr_bh")[1]
ok = knox.p_dates.notna()
knox.loc[ok, "q_dates"] = multipletests(knox.loc[ok, "p_dates"], method="fdr_bh")[1]
knox.to_csv(OUT / "knox_space_time.csv", index=False)
ep = pd.DataFrame(episodes)
ep.to_csv(OUT / "episodes.csv", index=False)
pd.concat(members).to_csv(OUT / "event_episode_membership.csv", index=False)
hd = pd.DataFrame(null_rows)
hd.to_csv(OUT / "episodes_vs_null.csv", index=False)
ut = pd.concat(unit_rows).rename_axis("unit_id")
ut.to_csv(OUT / "units_in_episodes.csv")

# ---- wealth link (Philippines and Bangladesh have the Relative Wealth Index)
rwi_rows = []
for iso in ("PHL", "BGD"):
    tab = pd.read_csv(paths.PROCESSED / "emdat" / "stats" / "province" / f"{iso.lower()}_unit_table.csv", index_col=0)
    j = ut[ut.region == iso].join(tab[["rwi_mean", "population"]], how="inner").dropna(subset=["rwi_mean"])
    j = j[j.events >= 3]
    for col in ("in_episode", "share_in_episode"):
        r, p = stats.spearmanr(j.rwi_mean, j[col])
        rwi_rows.append({"region": iso, "measure": col, "units": len(j), "spearman_rho": r, "p": p})
rwi = pd.DataFrame(rwi_rows)
rwi.to_csv(OUT / "episodes_vs_rwi.csv", index=False)

# ------------------------------------------------------------------ global flood locations (coordinates) ----
fl = rec[(rec.hgroup == "flood")].copy()
fl["has_xy"] = fl.lat.notna() & fl.lon.notna()
cov_xy = {"flood_records": int(len(fl)), "with_coordinates": int(fl.has_xy.sum()),
          "share": float(fl.has_xy.mean()),
          "share_by_period": fl.groupby(pd.cut(fl.year, [1999, 2005, 2010, 2015, 2020, 2025])).has_xy.mean().round(3).astype(float).rename(str).to_dict(),
          "share_by_region": fl.groupby("region").has_xy.mean().round(3).to_dict()}
xy = fl[fl.has_xy].reset_index(drop=True)
lab = HDBSCAN(metric="haversine", min_cluster_size=10, min_samples=5).fit(np.radians(xy[["lat", "lon"]].to_numpy(float))).labels_
xy["cluster"] = lab
gcl = (xy[xy.cluster >= 0].groupby("cluster")
       .agg(records=("disno", "size"), countries=("iso3", lambda x: ", ".join(x.value_counts().index[:4])),
            lat=("lat", "median"), lon=("lon", "median"), first=("year", "min"), last=("year", "max"),
            deaths=("deaths", "sum"))
       .sort_values("records", ascending=False))
gcl.to_csv(OUT / "global_flood_location_clusters.csv")
cov_xy.update({"clusters": int(lab.max() + 1), "share_clustered": float(np.mean(lab >= 0))})

summary = {"coverage": coverage, "knox": knox.to_dict("records"), "episodes_vs_null": hd.to_dict("records"),
           "episodes": {"total": int(len(ep)), "multi_hazard": int(ep.multi_hazard.sum()) if len(ep) else 0},
           "rwi": rwi.to_dict("records"), "global_flood_coordinates": cov_xy}
(OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_colwidth", 80)
print(json.dumps(coverage, indent=1, default=str))
print(knox.round(3).to_string())
print(hd.round(3).to_string())
print(ep.sort_values("events", ascending=False).head(25).to_string())
print(ep.groupby(["region", "multi_hazard"]).size())
print(rwi.round(3).to_string())
print(json.dumps(cov_xy, indent=1, default=str))
print(gcl.head(15).to_string())
