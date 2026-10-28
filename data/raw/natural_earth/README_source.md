# Natural Earth reference layers

Downloaded October 27, 2026 from the official Natural Earth GitHub repository (nvkelso/natural-earth-vector), tag **v5.1.2**, which is the latest tagged release. The naciscdn.org download site was not reachable from the download environment, so files came from the same release on GitHub. Natural Earth is public domain.

| File | Scale | Layer version (VERSION.txt) | Use |
|---|---|---|---|
| ne_50m_admin_0_countries.zip | 1:50m | 5.1.1 | Country polygons, join key for INFORM/IMF |
| ne_10m_admin_1_states_provinces.zip | 1:10m | 5.1.1 | Provinces/states (simplify for web) |
| ne_50m_admin_0_breakaway_disputed_areas.zip | 1:50m | 5.1.1 | Disputed-area layer |
| ne_50m_coastline.zip | 1:50m | 4.1.0 | Distance-to-coast proxy |
| ne_50m_rivers_lake_centerlines.zip | 1:50m | 5.0.0 | River-proximity proxy |
| ne_50m_lakes.zip | 1:50m | 5.0.0 | Lakes |

Each zip holds a shapefile (.shp, .shx, .dbf, .prj, .cpg) plus the layer's README and VERSION files. `geopandas.read_file("zip://ne_50m_admin_0_countries.zip")` reads them directly.

## Notes

- **Admin-1 is 1:10m, not 1:50m.** The 1:50m admin-1 layer covers only nine countries (AUS, BRA, CAN, CHN, IDN, IND, RUS, USA, ZAF), so it can't be used for the Philippines or the Horn of Africa. The 1:10m layer covers 251 countries and 4,596 units; simplify it before putting it on the web.
- **Join key.** `ISO_A3_EH` is -99 for Somaliland, Kosovo, Northern Cyprus and Siachen Glacier. `ADM0_A3` is always filled but differs from ISO for some places (Palestine is PSX, ISO PSE; South Sudan is SDS, ISO SSD). Join on `ISO_A3_EH` with an `ADM0_A3` fallback and an alias table.
- **Somalia/Somaliland.** Natural Earth splits Somaliland into its own admin-0 unit (SOL). INFORM and EM-DAT use SOM for the whole country. The disputed-area policy needs to cover this.
- **Palestine.** In the admin-0 attributes, `ADM0_A3` = PSX, `ISO_A3` = PSE, `TYPE` = Indeterminate and `SOVEREIGNT` = Israel. These attributes are the same in the default file and in the 1:10m Palestinian, Israeli and US worldview files. Don't show `SOVEREIGNT` on the dashboard; name the worldview in the methods page.
- **Worldview files** (`ne_10m_admin_0_countries_<iso>`) exist only at 1:10m.
