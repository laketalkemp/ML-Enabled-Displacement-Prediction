"""Dashboard outputs for docs/ (GitHub Pages).

Maps join on the country crosswalk's keys (Natural Earth 1:50m, ISO_A3_EH falling back to ADM0_A3) instead of
matching country names, and show each place's display name from the crosswalk. Territories with no INFORM value are
drawn in gray and labeled, not filled with a neighbor's or sovereign's value; the one exception is Somaliland, which
INFORM, EM-DAT and IDMC count within Somalia. Disputed areas follow reports/disputed_areas.md: Natural Earth's
de facto boundaries, a hatched overlay, no sovereignty attributes, and a UN-style disclaimer. The Abyei Area is drawn
on its own, attributed to neither Sudan nor South Sudan. Plotly is loaded from its CDN to keep files small.
"""
from __future__ import annotations

import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import crosswalk
from .paths import NATURAL_EARTH_DIR

# Disputed areas: Natural Earth's breakaway and disputed areas layer, with neutral names (no sovereignty attributes).
DISPUTED_NAMES = {"B16": "Golan", "B19": "Western Sahara", "B20": "Northern Cyprus", "B29": "Kuril Islands",
                  "B30": "Somaliland", "B35": "Abkhazia", "B36": "Transnistrian region", "B37": "South Ossetia",
                  "B89": "Crimea", "C02": "Donetsk area", "C03": "Luhansk area", "C04": "Sabah (North Borneo)",
                  "B13": "Abyei Area"}
# Left out of the overlay: Nagorno-Karabakh (Artsakh) dissolved on January 1, 2024; Natural Earth 5.1.2 predates it.
DISPUTED_DROP = {"B38"}
# Features that are their own map unit, whose own hover text already explains them.
DISPUTED_OWN_UNIT = {"B13", "B20", "B30", "B45"}
MAP_DISCLAIMER = ("Boundaries and names shown and the designations used on this map do not imply endorsement or acceptance "
                  "by the authors or UC San Diego.<br>Hatched areas are disputed or of undetermined status; their shading "
                  "follows Natural Earth's de facto boundaries. References to Kosovo are in the context of<br>UN Security "
                  "Council resolution 1244 (1999). The final status of the Abyei Area is not yet determined, and it is "
                  "attributed to neither Sudan nor South Sudan.")
PLACE_NOTES = {"KOS": "In the context of UN Security Council resolution 1244 (1999)",
               "AB9": "Final status not yet determined; attributed to neither Sudan nor South Sudan.<br>"
                      "IDMC records displacement here; INFORM does not score it",
               "SOL": "Shown with Somalia's score: INFORM, EM-DAT and IDMC count it within Somalia",
               "CYN": "Disputed; no source scores it", "KAS": "Disputed; no source scores it",
               "ESH": "Non-self-governing territory; disputed"}

TIER_COLORS = {1: "#2ca02c", 2: "#ff7f0e", 3: "#d62728", 4: "#9467bd"}   # as in the original figure
# Reader-facing name of each group: "vulnerability level", never "tier" (project terminology, Nov 2026).
# Column names (tier, tier_label, tier_stability) stay for compatibility.
LEVEL_NAMES = {1: "Low", 2: "Mild", 3: "Moderate", 4: "Severe"}
HTML_KW = dict(include_plotlyjs="cdn", full_html=True)


def _clockwise(geom):
    """d3-geo (used by plotly) expects clockwise exterior rings, the reverse of the GeoJSON spec."""
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.geometry.polygon import orient
    if isinstance(geom, Polygon):
        return orient(geom, sign=-1.0)
    if isinstance(geom, MultiPolygon):
        return MultiPolygon([orient(g, sign=-1.0) for g in geom.geoms])
    return geom


def disputed_areas() -> gpd.GeoDataFrame:
    d = gpd.read_file(f"zip://{NATURAL_EARTH_DIR / 'ne_50m_admin_0_breakaway_disputed_areas.zip'}")
    d = d[~d.BRK_A3.isin(DISPUTED_DROP)].copy()
    d["label"] = d.BRK_A3.map(DISPUTED_NAMES).fillna(d.BRK_NAME)
    return d[["BRK_A3", "label", "geometry"]]


def world_geojson(tolerance: float = 0.05) -> tuple[dict, pd.DataFrame]:
    a0 = gpd.read_file(f"zip://{NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
    a0["iso3"] = a0["ISO_A3_EH"].where(a0["ISO_A3_EH"] != "-99", a0["ADM0_A3"])
    a0 = a0[["iso3", "NAME", "geometry"]].dissolve("iso3", as_index=False)
    # places drawn from the disputed-areas layer (the Abyei Area), cut out of the units they overlap
    dl = gpd.read_file(f"zip://{NATURAL_EARTH_DIR / 'ne_50m_admin_0_breakaway_disputed_areas.zip'}")
    for key, brk in crosswalk.DISPUTED_LAYER_UNITS.items():
        geom = dl.loc[dl.BRK_A3 == brk, "geometry"].union_all()
        a0["geometry"] = a0.geometry.difference(geom)
        a0 = pd.concat([a0, gpd.GeoDataFrame({"iso3": [key], "NAME": [key], "geometry": [geom]}, crs=a0.crs)],
                       ignore_index=True)
    a0 = a0[~a0.geometry.is_empty]
    a0["geometry"] = a0.geometry.simplify(tolerance, preserve_topology=True).apply(_clockwise)
    gj = json.loads(a0.to_json())
    for f in gj["features"]:
        f["id"] = f["properties"]["iso3"]
    return gj, a0.drop(columns="geometry")


def _subset(gj: dict, keep: set) -> dict:
    return {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["id"] in keep]}


def display_names(keys: pd.Series, fallback: pd.Series | None = None) -> pd.Series:
    """Crosswalk display names (workplan/terminology.md); fallback where a key is not in the crosswalk."""
    return crosswalk.display_name(keys, fallback)


def _hatch(geoms, spacing_max: float = 0.9) -> tuple[list, list]:
    """45-degree hatch lines clipped to each geometry, as lon/lat lists with None breaks (one Scattergeo trace)."""
    from shapely.geometry import LineString
    lon, lat = [], []
    for g in geoms:
        x0, y0, x1, y1 = g.bounds
        step = max(0.2, min(spacing_max, ((x1 - x0) + (y1 - y0)) / 12))
        c = y0 - x1
        while c <= y1 - x0:
            seg = g.intersection(LineString([(x0 - 1, x0 - 1 + c), (x1 + 1, x1 + 1 + c)]))
            for part in getattr(seg, "geoms", [seg]):
                if part.geom_type == "LineString" and not part.is_empty:
                    xs, ys = part.xy
                    lon += list(xs) + [None]
                    lat += list(ys) + [None]
            c += step
        for ring in getattr(g, "geoms", [g]):                     # outline
            xs, ys = ring.exterior.xy
            lon += list(xs) + [None]
            lat += list(ys) + [None]
    return lon, lat


def vulnerability_map(df: pd.DataFrame, path) -> dict:
    gj, units = world_geojson()
    units = units.assign(name=display_names(units["iso3"], units["NAME"]))
    parents = {k: v for k, v in crosswalk.DATA_PARENT.items() if v in set(df["iso3"])}
    nodata = units[~units["iso3"].isin(df["iso3"]) & ~units["iso3"].isin(parents) & (units["iso3"] != "ATA")]
    nodata = nodata.assign(note=nodata["iso3"].map(PLACE_NOTES).fillna("No INFORM score").where(
        ~nodata["iso3"].isin(PLACE_NOTES), "No INFORM score<br>" + nodata["iso3"].map(PLACE_NOTES)))
    d = df.assign(name=display_names(df["iso3"], df["country"]),
                  imputed_note=df["imputed"].map({True: "yes, some indicators imputed", False: "no"}),
                  level_note=df["tier"].map(lambda t: f"{LEVEL_NAMES[t]} vulnerability level"))
    # places shaded with another key's score (Somaliland with Somalia's)
    extra = [d[d.iso3 == p].assign(iso3=k, name=display_names(pd.Series([k])).iat[0],
                                   level_note=PLACE_NOTES[k]) for k, p in parents.items()]
    d = pd.concat([d] + extra, ignore_index=True)
    fig = go.Figure()
    # each geometry is embedded once: territories without a score in one trace, scored countries in the other
    fig.add_trace(go.Choropleth(geojson=_subset(gj, set(nodata["iso3"])), locations=nodata["iso3"], z=[0] * len(nodata),
                                colorscale=[[0, "#d9d9d9"], [1, "#d9d9d9"]], showscale=False,
                                customdata=nodata[["name", "note"]],
                                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
                                marker_line_color="white", marker_line_width=0.3))
    fig.add_trace(go.Choropleth(geojson=_subset(gj, set(d["iso3"])), locations=d["iso3"], z=d["vulnerability_score"],
                                zmin=0, zmax=100, colorscale="YlOrRd", colorbar_title="Score (0-100)",
                                customdata=d[["name", "level_note", "tier_stability", "imputed_note"]],
                                hovertemplate="<b>%{customdata[0]}</b><br>Score %{z:.1f}<br>%{customdata[1]}"
                                              "<br>Same level in %{customdata[2]:.0%} of refits<br>Imputed: %{customdata[3]}<extra></extra>",
                                marker_line_color="white", marker_line_width=0.3))
    # disputed areas: transparent hover layer (where the area sits inside another unit), then the hatch lines
    dis = disputed_areas()
    dis["geometry"] = dis.geometry.simplify(0.05, preserve_topology=True)
    inner = dis[~dis.BRK_A3.isin(DISPUTED_OWN_UNIT)].copy()
    inner["geometry"] = inner.geometry.apply(_clockwise)
    ign = json.loads(inner.to_json())
    for f in ign["features"]:
        f["id"] = f["properties"]["BRK_A3"]
    fig.add_trace(go.Choropleth(geojson=ign, locations=inner["BRK_A3"], z=[0] * len(inner), showscale=False,
                                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], marker_line_width=0,
                                text=inner["label"],
                                hovertemplate="<b>%{text}</b><br>Disputed area (hatched). Shading follows Natural Earth's"
                                              "<br>de facto boundaries; no position on its status is implied<extra></extra>"))
    hx, hy = _hatch(dis.geometry)
    fig.add_trace(go.Scattergeo(lon=hx, lat=hy, mode="lines", line=dict(width=0.6, color="#3a3a3a"),
                                hoverinfo="skip", showlegend=False))
    fig.add_annotation(text=MAP_DISCLAIMER, x=0, y=-0.02, xref="paper", yref="paper", xanchor="left", yanchor="top",
                       showarrow=False, align="left", font=dict(size=9, color="#555"))
    fig.update_geos(projection_type="natural earth", projection_rotation_lon=0, center=dict(lon=0, lat=10),
                    lonaxis_range=[-180, 180], lataxis_range=[-60, 85],
                    showframe=False, showcoastlines=False, showcountries=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(title="Composite vulnerability score (v1.1, INFORM latest year)",
                      margin=dict(l=0, r=0, t=50, b=70), font_family="Inter, sans-serif")
    fig.write_html(path, div_id="vulnerability-map", **HTML_KW)
    return {"countries_mapped": int(d["iso3"].isin(units["iso3"]).sum()), "units_without_score": int(len(nodata))}


def temporal_slider(long: pd.DataFrame, path):
    """Animated choropleth; the geometry is stored once and each year's frame only updates the values."""
    gj, _ = world_geojson()
    years = sorted(long["year"].unique())
    iso = sorted(long["iso3"].unique())
    gj = _subset(gj, set(iso))
    piv = long.pivot(index="iso3", columns="year", values="vulnerability_score").reindex(iso)
    names = long.drop_duplicates("iso3").set_index("iso3")["country"].reindex(iso)
    names = display_names(pd.Series(names.index, index=names.index), names)
    base = go.Choropleth(geojson=gj, locations=iso, z=piv[years[0]].round(2), zmin=0, zmax=100, colorscale="YlOrRd",
                         colorbar_title="Score", text=names, marker_line_color="white", marker_line_width=0.3,
                         hovertemplate="<b>%{text}</b><br>Score %{z:.1f}<extra></extra>")
    frames = [go.Frame(data=[go.Choropleth(z=piv[y].round(2))], name=str(y)) for y in years]
    fig = go.Figure(data=[base], frames=frames)
    steps = [dict(method="animate", label=str(y), args=[[str(y)], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
             for y in years]
    fig.update_layout(
        title=f"Longitudinal vulnerability trajectory ({years[0]}-{years[-1]})",
        sliders=[dict(active=0, steps=steps, currentvalue=dict(prefix="Year: "))],
        updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=0.02, buttons=[
            dict(label="Play", method="animate", args=[None, dict(frame=dict(duration=900, redraw=True), fromcurrent=True)])])],
        margin=dict(l=0, r=0, t=50, b=0))
    fig.update_geos(projection_type="natural earth", projection_rotation_lon=0, center=dict(lon=0, lat=10),
                    lonaxis_range=[-180, 180], lataxis_range=[-60, 85],
                    showframe=False, showcoastlines=False, showcountries=False)
    fig.write_html(path, div_id="temporal-slider", **HTML_KW)


def top10_race(long: pd.DataFrame, path):
    frames = [g.nlargest(10, "vulnerability_score").sort_values("vulnerability_score") for _, g in long.groupby("year")]
    d = pd.concat(frames)
    d = d.assign(country=display_names(d["iso3"], d["country"]).to_numpy())
    vmax = long["vulnerability_score"].max()
    fig = px.bar(d, x="vulnerability_score", y="country", animation_frame="year", orientation="h",
                 color="vulnerability_score", color_continuous_scale="OrRd",
                 range_x=[0, vmax * 1.05], range_color=[long["vulnerability_score"].min() - 5, vmax],
                 labels={"country": "Country", "vulnerability_score": "Composite vulnerability score"},
                 title="Countries with the highest composite vulnerability score")
    fig.update_layout(plot_bgcolor="white", margin=dict(l=150, r=50, t=80, b=50))
    fig.write_html(path, div_id="top10-race", **HTML_KW)


def comparative_metrics(df: pd.DataFrame, labels: dict, path):
    fig, buttons = go.Figure(), []
    df = df.assign(country=display_names(df["iso3"], df["country"]).to_numpy())
    cols = list(labels)
    for i, c in enumerate(cols):
        top = df[["country", c]].dropna().nlargest(10, c).sort_values(c)
        fig.add_trace(go.Bar(x=top[c], y=top["country"], orientation="h", visible=(i == 0),
                             marker=dict(color=top[c], colorscale="OrRd"), text=top[c].round(2),
                             textposition="inside", name=labels[c]))
        vis = [j == i for j in range(len(cols))]
        buttons.append(dict(label=labels[c], method="update",
                            args=[{"visible": vis}, {"title": f"Top 10: {labels[c]} (latest year)"}]))
    fig.update_layout(updatemenus=[dict(active=0, buttons=buttons, x=0, xanchor="left", y=1.15, yanchor="top")],
                      title=f"Top 10: {labels[cols[0]]} (latest year)", plot_bgcolor="white",
                      margin=dict(l=150, r=50, t=130, b=50), xaxis_title="Index score (0-10)")
    fig.write_html(path, div_id="comparative-metrics", **HTML_KW)


def tsne_png(df: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(10, 8))
    for t, g in df.groupby("tier"):
        ax.scatter(g["tsne_1"], g["tsne_2"], s=60, alpha=0.8, color=TIER_COLORS[t], label=LEVEL_NAMES[t])
    ax.set_title("t-SNE projection of countries by vulnerability level (v1.1)")
    ax.set_xlabel("t-SNE dimension 1"); ax.set_ylabel("t-SNE dimension 2")
    ax.legend(title="Vulnerability level", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)
