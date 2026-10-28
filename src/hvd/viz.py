"""Dashboard outputs for docs/ (GitHub Pages).

Maps join on ISO3 codes against Natural Earth 1:50m geometry (ISO_A3_EH, falling back to ADM0_A3),
instead of matching country names. Territories with no INFORM value are drawn in grey and labelled,
not filled with a neighbour's or sovereign's value. Plotly is loaded from its CDN to keep files small.
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

from .paths import NATURAL_EARTH_DIR

TIER_COLORS = {1: "#2ca02c", 2: "#ff7f0e", 3: "#d62728", 4: "#9467bd"}   # as in the original figure
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


def world_geojson(tolerance: float = 0.05) -> tuple[dict, pd.DataFrame]:
    a0 = gpd.read_file(f"zip://{NATURAL_EARTH_DIR / 'ne_50m_admin_0_countries.zip'}")
    a0["iso3"] = a0["ISO_A3_EH"].where(a0["ISO_A3_EH"] != "-99", a0["ADM0_A3"])
    a0 = a0[["iso3", "NAME", "geometry"]].copy()
    a0["geometry"] = a0.geometry.simplify(tolerance, preserve_topology=True).apply(_clockwise)
    gj = json.loads(a0.to_json())
    for f in gj["features"]:
        f["id"] = f["properties"]["iso3"]
    return gj, a0.drop(columns="geometry")


def _subset(gj: dict, keep: set) -> dict:
    return {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["id"] in keep]}


def vulnerability_map(df: pd.DataFrame, path) -> dict:
    gj, units = world_geojson()
    nodata = units[~units["iso3"].isin(df["iso3"]) & (units["iso3"] != "ATA")]
    d = df.assign(imputed_note=df["imputed"].map({True: "yes, some indicators imputed", False: "no"}))
    fig = go.Figure()
    # each geometry is embedded once: territories without a score in one trace, scored countries in the other
    fig.add_trace(go.Choropleth(geojson=_subset(gj, set(nodata["iso3"])), locations=nodata["iso3"], z=[0] * len(nodata),
                                colorscale=[[0, "#d9d9d9"], [1, "#d9d9d9"]], showscale=False,
                                text=nodata["NAME"], hovertemplate="%{text}<br>No INFORM score<extra></extra>",
                                marker_line_color="white", marker_line_width=0.3))
    fig.add_trace(go.Choropleth(geojson=_subset(gj, set(d["iso3"])), locations=d["iso3"], z=d["vulnerability_score"],
                                zmin=0, zmax=100, colorscale="YlOrRd", colorbar_title="Score (0-100)",
                                customdata=d[["country", "tier_label", "tier_stability", "imputed_note"]],
                                hovertemplate="<b>%{customdata[0]}</b><br>Score %{z:.1f}<br>%{customdata[1]}"
                                              "<br>Tier stability %{customdata[2]:.0%}<br>Imputed: %{customdata[3]}<extra></extra>",
                                marker_line_color="white", marker_line_width=0.3))
    fig.update_geos(projection_type="natural earth", projection_rotation_lon=0, center=dict(lon=0, lat=10),
                    lonaxis_range=[-180, 180], lataxis_range=[-60, 85],
                    showframe=False, showcoastlines=False, showcountries=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(title="Composite vulnerability score (v1.1, INFORM latest year)",
                      margin=dict(l=0, r=0, t=50, b=0), font_family="Inter, sans-serif")
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
        ax.scatter(g["tsne_1"], g["tsne_2"], s=60, alpha=0.8, color=TIER_COLORS[t], label=g["tier_label"].iat[0])
    ax.set_title("t-SNE projection of countries by vulnerability tier (v1.1)")
    ax.set_xlabel("t-SNE dimension 1"); ax.set_ylabel("t-SNE dimension 2")
    ax.legend(title="Tier", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout(); fig.savefig(path, dpi=200); plt.close(fig)
