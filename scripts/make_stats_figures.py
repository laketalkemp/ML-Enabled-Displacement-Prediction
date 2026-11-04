"""Figures for the Nov 10 statistical results (deck and pre-read), from the outputs of stats_country.py,
stats_province.py, stats_cordex.py and the IDMC validation. Figures are saved at the size they occupy on a
10 x 5.625 in slide, so font sizes are the sizes the audience sees.

    python scripts/make_stats_figures.py

Outputs: data/processed/emdat/stats/figures/ (internal; aggregated EM-DAT statistics).
"""
import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
warnings.filterwarnings("ignore")

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap, Normalize, TwoSlopeNorm  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import province as P  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#9aa5b1", "axes.labelcolor": "#3a4a5c",
                     "xtick.color": "#5b6b7c", "ytick.color": "#3a4a5c", "axes.spines.top": False, "axes.spines.right": False})
INK, MUTED, GRID = "#1d2b3a", "#6b7b8c", "#e3e8ee"
BLUE, GOLD, NAVY, GREY = "#00629B", "#C69214", "#182B49", "#d9d9d9"
HZ_COLOR = {"flood": "#2a78d6", "drought": "#eb6834", "storm": "#1baf7a", "extreme_temp": "#eda100",
            "wet_mass_mov": "#e87ba4", "wildfire": "#e34948"}
HZ_LABEL = {"flood": "Flood", "storm": "Storm", "drought": "Drought", "extreme_temp": "Extreme temperature",
            "wet_mass_mov": "Landslide (wet)", "wildfire": "Wildfire", "all_climate": "All climate hazards"}
STATS = paths.EMDAT_DERIVED_DIR / "stats"
CTRY, PROV = STATS / "country", STATS / "province"
OUT = STATS / "figures"
OUT.mkdir(parents=True, exist_ok=True)
DPI = 250


def save(fig, name):
    fig.savefig(OUT / name, dpi=DPI, facecolor="white")
    plt.close(fig)
    print("saved", name)


def countries():
    ne = gpd.read_file(f"zip://{paths.NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
    ne["iso3"] = ne.ISO_A3_EH.where(ne.ISO_A3_EH != "-99", ne.ADM0_A3)
    return ne[ne.iso3 != "ATA"].dissolve("iso3").reset_index().to_crs("ESRI:54030")


def world_axes(fig, rect):
    ax = fig.add_axes(rect)
    ax.set_axis_off()
    return ax


def fit_world(ax, g):
    xmin, ymin, xmax, ymax = g.total_bounds
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(max(ymin, -6.3e6), ymax)


# ------------------------------------------------------------- 1. trends ----
def fig_trends():
    t = pd.read_csv(CTRY / "trends_rate_ratio_per_decade.csv")
    t = t[t.records >= 30]
    order = ["extreme_temp", "storm", "wildfire", "wet_mass_mov", "flood", "drought"]
    fig = plt.figure(figsize=(6.0, 3.5))
    ax = fig.add_axes([0.32, 0.17, 0.66, 0.78])
    for i, h in enumerate(order):
        for sub, off, face in (("all", 0.14, BLUE), ("high_impact", -0.14, "white")):
            r = t[(t.hazard == h) & (t.subset == sub)]
            if r.empty:
                continue
            r = r.iloc[0]
            y = len(order) - 1 - i + off
            sig = r.q_bh < 0.05
            ax.plot([r.ci_low, r.ci_high], [y, y], color=BLUE if sub == "all" else GOLD, lw=2, solid_capstyle="round")
            ax.scatter([r.rate_ratio_per_decade], [y], s=46, facecolor=face if sub == "all" else "white",
                       edgecolor=BLUE if sub == "all" else GOLD, linewidth=2, zorder=3)
            if sig:
                pct = (r.rate_ratio_per_decade - 1) * 100
                ax.text(r.ci_high * 1.04, y, f"{pct:+.0f}%/decade", va="center", fontsize=10, color=INK)
    ax.axvline(1, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.set_xscale("log")
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks([0.7, 1, 1.5, 2, 2.5])
    ax.set_xticklabels(["0.7", "1", "1.5", "2", "2.5"])
    ax.set_xlim(0.6, 4.6)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([HZ_LABEL[h] for h in order[::-1]], fontsize=11, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Change in events per decade, 2000–2025 (rate ratio)", fontsize=10.5)
    ax.scatter([], [], s=46, facecolor=BLUE, edgecolor=BLUE, label="all records")
    ax.scatter([], [], s=46, facecolor="white", edgecolor=GOLD, linewidth=2, label="high-impact only")
    ax.legend(loc="lower right", frameon=False, fontsize=10, handletextpad=0.2)
    save(fig, "s_trends_forest.png")


# -------------------------------------------------------- 2. co-occurrence ----
def fig_cooccurrence():
    c = pd.read_csv(CTRY / "cooccurrence_same_year.csv")
    hz = ["flood", "storm", "drought", "extreme_temp", "wet_mass_mov", "wildfire"]
    M = np.full((len(hz), len(hz)), np.nan)
    Q = np.full_like(M, np.nan)
    for _, r in c.iterrows():
        i, j = hz.index(r.hazard_a), hz.index(r.hazard_b)
        a, b = max(i, j), min(i, j)
        M[a, b], Q[a, b] = r.lift_vs_null, r.q_bh
    # lower triangle without the empty first row and last column, so every label sits on a row or column of cells
    M, Q = M[1:, :-1], Q[1:, :-1]
    labels = ["Flood", "Storm", "Drought", "Heat/cold", "Landslide", "Wildfire"]
    rows, cols = labels[1:], labels[:-1]
    fig = plt.figure(figsize=(5.2, 3.6))
    ax = fig.add_axes([0.2, 0.22, 0.55, 0.75])
    cmap = matplotlib.colormaps["RdBu_r"]
    im = ax.imshow(M, cmap=cmap, norm=TwoSlopeNorm(1.0, 0.8, 1.35))
    for a in range(M.shape[0]):
        for b in range(M.shape[1]):
            if np.isfinite(M[a, b]):
                star = "*" if Q[a, b] < 0.05 else ""
                ax.text(b, a, f"{M[a, b]:.2f}{star}", ha="center", va="center", fontsize=9.5,
                        color="white" if abs(M[a, b] - 1) > 0.2 else INK, fontweight="bold" if star else "normal")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=90, ha="center", va="top", fontsize=10)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows, fontsize=10)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cax = fig.add_axes([0.8, 0.3, 0.03, 0.5])
    cb = fig.colorbar(im, cax=cax)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=9, length=0)
    cb.set_label("same-year co-occurrence\nvs chance (1 = chance)", fontsize=9.5)
    save(fig, "s_cooccurrence_matrix.png")


# --------------------------------------------------------- 3. vulnerability ----
def fig_vulnerability():
    h = pd.read_csv(CTRY / "vulnerability_vs_impacts_hurdle.csv")
    h = h[(h["sample"] == "all countries") & (h.outcome == "deaths") & h.ratio_if_recorded.notna()]
    order = ["storm", "flood", "wet_mass_mov", "wildfire", "extreme_temp", "all_climate"]
    td = pd.read_csv(CTRY / "impacts_by_tier_kruskal.csv")
    fig = plt.figure(figsize=(9.0, 3.4))
    ax = fig.add_axes([0.2, 0.22, 0.37, 0.72])
    for i, hz in enumerate(order):
        r = h[h.hazard == hz]
        if r.empty:
            continue
        r = r.iloc[0]
        y = len(order) - 1 - i
        col = BLUE if r.q_if_recorded < 0.05 else "#9aa5b1"
        ax.plot([r.ratio_ci_low, r.ratio_ci_high], [y, y], color=col, lw=2.2, solid_capstyle="round")
        ax.scatter([r.ratio_if_recorded], [y], s=55, color=col, zorder=3, marker="D" if hz == "all_climate" else "o")
        if r.q_if_recorded < 0.05:
            ax.text(r.ratio_ci_high * 1.03, y, f"+{(r.ratio_if_recorded - 1) * 100:.0f}%", va="center", fontsize=10.5, color=INK)
    ax.axvline(1, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.set_xscale("log")
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks([0.6, 0.8, 1, 1.25, 1.5, 2])
    ax.set_xticklabels(["0.6", "0.8", "1", "1.25", "1.5", "2"])
    ax.set_xlim(0.5, 2.3)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([HZ_LABEL[o] for o in order[::-1]], fontsize=10.5, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Deaths per fatal event, per 10-point\nrise in vulnerability (rate ratio)", fontsize=10)
    # tier medians
    ax2 = fig.add_axes([0.67, 0.22, 0.31, 0.68])
    x = np.arange(4)
    for k, (hz, col) in enumerate((("flood", HZ_COLOR["flood"]), ("storm", HZ_COLOR["storm"]))):
        r = td[(td.hazard == hz) & (td.outcome == "deaths")].iloc[0]
        vals = [r[f"median_tier{t}"] for t in (1, 2, 3, 4)]
        ax2.bar(x + (k - 0.5) * 0.36, vals, width=0.34, color=col, label=HZ_LABEL[hz])
        for xi, v in zip(x, vals):
            ax2.text(xi + (k - 0.5) * 0.36, v + 0.4, f"{v:.0f}", ha="center", fontsize=9.5, color=INK)
    ax2.set_xticks(x)
    ax2.set_xticklabels(["Low", "Mild", "Moderate", "Severe"], fontsize=10)
    ax2.set_ylabel("Median deaths per fatal event", fontsize=10)
    ax2.set_title("By vulnerability level", fontsize=11, color=INK, loc="left")
    ax2.legend(frameon=False, fontsize=10, loc="upper left")
    ax2.spines["left"].set_visible(False)
    ax2.tick_params(axis="y", length=0)
    ax2.yaxis.grid(True, color=GRID)
    ax2.set_axisbelow(True)
    save(fig, "s_vulnerability_impacts.png")


# ------------------------------------------------------- 4. global clusters ----
def fig_global_clusters():
    g = countries()
    loc = pd.read_csv(CTRY / "local_clusters_country.csv")
    m = g.merge(loc[["iso3", "burden_amid_vulnerable__bv_cluster", "burden_affected__gi_spot"]], on="iso3", how="left")
    cls = {"high-high": "#b2182b", "low-low": "#4393c3", "high-low": "#f4a582", "low-high": "#92c5de"}
    fig = plt.figure(figsize=(6.2, 3.55))
    ax = world_axes(fig, [0, 0.12, 1, 0.88])
    m.plot(ax=ax, color="#eef1f4", edgecolor="white", linewidth=0.2)
    for k, col in cls.items():
        s = m[m.burden_amid_vulnerable__bv_cluster == k]
        if len(s):
            s.plot(ax=ax, color=col, edgecolor="white", linewidth=0.2)
    fit_world(ax, m)
    hh = Patch(color=cls["high-high"], label="High hazard burden, high-vulnerability neighbours")
    ll = Patch(color=cls["low-low"], label="Low burden, low-vulnerability neighbours")
    ot = Patch(color=cls["high-low"], label="Mixed (outliers)")
    fig.legend(handles=[hh, ll, ot], loc="lower center", ncol=1, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.01))
    save(fig, "s_global_bivariate_clusters.png")


# ----------------------------------------------------------- 5. archetypes ----
def fig_archetypes():
    g = countries()
    a = pd.read_csv(CTRY / "archetypes_country.csv").rename(columns={"Unnamed: 0": "iso3"})
    if "iso3" not in a:
        a = a.rename(columns={a.columns[0]: "iso3"})
    m = g.merge(a[["iso3", "archetype_label"]], on="iso3", how="left")
    col = {"Flood-led": HZ_COLOR["flood"], "Storm-led": HZ_COLOR["storm"], "Mixed: flood, heat and wildfire": HZ_COLOR["extreme_temp"]}
    fig = plt.figure(figsize=(6.2, 3.55))
    ax = world_axes(fig, [0, 0.12, 1, 0.88])
    m.plot(ax=ax, color="#eef1f4", edgecolor="white", linewidth=0.2)
    for k, c in col.items():
        s = m[m.archetype_label == k]
        s.plot(ax=ax, color=c, edgecolor="white", linewidth=0.2)
    fit_world(ax, m)
    fig.legend(handles=[Patch(color=c, label=k) for k, c in col.items()] + [Patch(color="#eef1f4", label="Fewer than 5 events")],
               loc="lower center", ncol=2, frameon=False, fontsize=9.5, bbox_to_anchor=(0.5, -0.01))
    save(fig, "s_archetypes_map.png")


# ------------------------------------------------ 6. province hot spots ----
def fig_province_hotspots():
    spec = [("PHL", "events_storm", "Philippines: storms"), ("BGD", "events_flood", "Bangladesh: floods"),
            ("AFG", "drought_months_spi6", "Afghanistan: drought months")]
    col = {"hot spot": "#b2182b", "cold spot": "#4393c3", "not significant": "#e6e9ed"}
    fig = plt.figure(figsize=(9.0, 3.3))
    widths = [2.4, 2.6, 3.2]
    x0 = 0.05
    for (iso, v, title), wd in zip(spec, widths):
        ax = fig.add_axes([x0 / 9, 0.12, wd / 9, 0.74])
        u = gpd.read_file(PROV / f"{iso.lower()}_units_stats.gpkg")
        c = f"{v}__gi_spot"
        if c not in u:
            c = f"{v}__lisa_cluster"
        u.plot(ax=ax, color=u[c].map(col).fillna("#e6e9ed"), edgecolor="white", linewidth=0.3)
        ax.set_axis_off()
        ax.set_title(title, fontsize=11.5, color=INK)
        x0 += wd + 0.1
    fig.legend(handles=[Patch(color=col["hot spot"], label="Hot spot (Gi*, FDR 5%)"), Patch(color=col["cold spot"], label="Cold spot"),
                        Patch(color=col["not significant"], label="Not significant")], loc="lower center", ncol=3, frameon=False, fontsize=10)
    save(fig, "s_province_hotspots.png")


# ------------------------------------------------------- 7. seasonality ----
def fig_seasonality():
    s = pd.read_csv(PROV / "seasonality_month_counts.csv")
    s.columns = [c if not c.replace(".0", "").isdigit() else int(float(c)) for c in s.columns]
    spec = [("PHL", "storm", "Philippines: storms"), ("BGD", "storm", "Bangladesh: storms"), ("BGD", "flood", "Bangladesh: floods"),
            ("AFG", "flood", "Afghanistan: floods")]
    fig = plt.figure(figsize=(9.0, 2.6))
    for k, (iso, hz, title) in enumerate(spec):
        ax = fig.add_axes([0.04 + k * 0.245, 0.2, 0.2, 0.62])
        r = s[(s.iso3 == iso) & (s.hgroup == hz)]
        vals = [float(r[m].iloc[0]) if m in r and len(r) else 0 for m in range(1, 13)]
        ax.bar(range(1, 13), vals, color=HZ_COLOR[hz], width=0.75)
        ax.set_xticks([1, 4, 7, 10])
        ax.set_xticklabels(["Jan", "Apr", "Jul", "Oct"], fontsize=9.5)
        ax.set_title(title, fontsize=10.5, color=INK, loc="left")
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", labelsize=9, length=0)
        ax.yaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
    fig.text(0.01, 0.02, "Records by start month, 2000–2025 (EM-DAT)", fontsize=9.5, color=MUTED)
    save(fig, "s_seasonality.png")


# ------------------------------------------------------- 8. drought trend ----
def fig_drought_trend():
    tr = pd.read_csv(PROV / "drought_trend_era5land.csv").set_index("region")
    fig = plt.figure(figsize=(9.0, 2.6))
    for k, (iso, col) in enumerate((("PHL", HZ_COLOR["drought"]), ("AFG", HZ_COLOR["drought"]), ("BGD", HZ_COLOR["drought"]))):
        ax = fig.add_axes([0.07 + k * 0.32, 0.13, 0.27, 0.6])
        mth = pd.read_csv(paths.DROUGHT_DIR / f"{iso.lower()}_monthly_drought_indices_1991_2025.csv", usecols=["year", "spi6"])
        sh = mth.assign(d=mth.spi6 <= -1).groupby("year").d.mean() * 100
        sh = sh[sh.index >= 1992]
        ax.bar(sh.index, sh.values, color=col, width=0.8, alpha=0.85)
        r = tr.loc[iso]
        yrs = np.array([1992, 2025])
        mid = sh.median() + (yrs - np.median(sh.index.values)) * r.theil_sen_pct_points_per_decade / 10
        ax.plot(yrs, mid, color=INK, lw=1.5, ls=(0, (4, 2)))
        star = " (p < 0.05)" if r.p < 0.05 else f" (p = {r.p:.2f})"
        ax.set_title(f"{P.NAMES[iso]}\n{r.theil_sen_pct_points_per_decade:+.1f} points per decade{star}", fontsize=10, color=INK, loc="left")
        ax.set_ylim(0, 80)
        ax.set_xticks([1995, 2005, 2015, 2025])
        ax.tick_params(labelsize=9.5, length=0)
        ax.spines["left"].set_visible(False)
        ax.yaxis.grid(True, color=GRID)
        ax.set_axisbelow(True)
        if k == 0:
            ax.set_ylabel("% unit-months in drought", fontsize=9.5)
    save(fig, "s_drought_trend.png")


if __name__ == "__main__":
    for f in (fig_trends, fig_cooccurrence, fig_vulnerability, fig_global_clusters, fig_archetypes,
              fig_province_hotspots, fig_seasonality, fig_drought_trend):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            print("FAILED", f.__name__, type(e).__name__, e)
