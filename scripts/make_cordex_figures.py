"""Maps of projected change from the CORDEX ensemble (scripts/stats_cordex.py outputs).

    python scripts/make_cordex_figures.py

One diverging scale in every panel: red = the mapped hazard increases (more drought months, heavier downpours), blue = it decreases. Thick outline = Gi* hot spot (FDR 5%);
hatching = fewer than 5 of 6 runs agree on the sign. CORDEX-derived only (no EM-DAT content).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402

from hvd import paths  # noqa: E402
from hvd.stats import province as P  # noqa: E402

D = paths.PROCESSED / "cordex"
OUT = D / "figures"
OUT.mkdir(exist_ok=True)
h = pd.read_csv(D / "future_change_hotspots.csv")

PANELS = [  # region, scenario, window, metric, title, unit, cmap
    ("AFG", "rcp_8_5", "2041-2070", "drought_share_change_pp", "Afghanistan: more drought months\nRCP8.5, 2041–2070", "percentage points", "RdBu_r"),
    ("BGD", "rcp_8_5", "2041-2070", "rx5day_change_pct", "Bangladesh: heavier 5-day rainfall\nRCP8.5, 2041–2070", "% change in Rx5day", "RdBu_r"),
    ("PHL", "rcp_8_5", "2071-2099", "rx5day_change_pct", "Philippines: heavier 5-day rainfall\nRCP8.5, 2071–2099", "% change in Rx5day", "RdBu_r"),
]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "hatch.linewidth": 0.5})
fig, axes = plt.subplots(1, 3, figsize=(12.5, 5.8), gridspec_kw={"width_ratios": [1.25, 0.8, 0.85]})
fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.1, wspace=0.08)
for ax, (iso, scen, win, met, title, unit, cmap) in zip(axes, PANELS):
    u = P.load_units(iso)
    g = h[(h.region == iso) & (h.scenario == scen) & (h.window == win) & (h.metric == met)].set_index("unit_id")
    u = u.join(g[["value", "robust", "gi_spot"]], on="unit_id")
    lim = float(np.nanmax(np.abs(u.value)))
    norm = TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim)
    u.plot(column="value", cmap=cmap, norm=norm, ax=ax, edgecolor="white", linewidth=0.3)
    u[~u.robust.astype(bool)].plot(ax=ax, facecolor="none", edgecolor="#6b6b6b", hatch="////", linewidth=0)
    hs = u[u.gi_spot == "hot spot"]
    if len(hs):
        hs.dissolve().boundary.plot(ax=ax, color="#1a1a1a", linewidth=1.6)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.045, pad=0.02, shrink=0.85)
    cb.set_label(unit, fontsize=8)
    cb.ax.tick_params(labelsize=8)
    ax.set_axis_off()
    x0 = ax.get_position().x0
    fig.text(x0, 0.965, title, fontsize=10.5, va="top")
fig.text(0.01, 0.015, "Ensemble median of 6 CORDEX runs vs each run's own 1991–2020. Thick outline: Gi* hot spot (FDR 5%). "
         "Hatched: fewer than 5 of 6 runs agree on the sign. Red = the hazard increases, blue = it decreases.", fontsize=8, color="#444")
fig.savefig(OUT / "cordex_change_hotspots.png", dpi=170)
print("wrote", OUT / "cordex_change_hotspots.png")
