# Data

The repository holds small, openly licensed inputs and derived tables. Large raw downloads are fetched by scripts. Restricted data is never committed: EM-DAT can't be redistributed, and GADM can't be redistributed without permission. `.gitignore` enforces this.

## Layout

| Folder | In git | Contents |
|---|---|---|
| `raw/inform/` | yes | The eight World Bank Data360 extracts used by the index (see `reports/data_dictionary.md`) |
| `raw/natural_earth/` | partly | 1:50m admin-0 countries and disputed areas are committed. The other layers come from `scripts/fetch_natural_earth.py` |
| `raw/era5land/` | **no** | ERA5-Land monthly means, from `scripts/download_era5land.py` and `scripts/download_era5land_tp_fix.py` (needs a CDS API key) |
| `raw/emdat/` | **no** | Your own EM-DAT export (manual download, see below) |
| `external/geoboundaries/` | yes | Province/district boundaries for the case-study countries |
| `processed/regions/` | yes | Province layers and crosswalks for the Philippines and Afghanistan (`scripts/build_poc_regions.py`) |
| `processed/drought/` | yes | SPI/SPEI per province or district, 1991–2025 (`scripts/drought_indices.py`) |
| `processed/index/` | yes | Vulnerability index v1.1, diagnostics, longitudinal scores (`scripts/run_index.py`) |
| `processed/emdat/` | **no** | EM-DAT event counts per province (`scripts/emdat_province_counts.py`) |

## Sources and licences

| Data | Source | Licence / terms | Citation |
|---|---|---|---|
| INFORM Risk indicators (`INFORM_*.csv`), 2016–2025 | European Commission JRC (DRMKC), via World Bank Data360 | Reuse is authorised with acknowledgement (European Commission reuse policy). Confirm on the INFORM site before publication | INFORM Risk Index, European Commission Joint Research Centre, drmkc.jrc.ec.europa.eu/inform-index |
| Climate-driven INFORM (`IMF_CDIR_*.csv`), 2013–2022 | IMF Climate Change Indicators Dashboard, via World Bank Data360 | Free use, redistribution and derivatives with attribution; material changes must be stated ([IMF terms](https://www.imf.org/en/About/copyright-and-terms)) | Source: International Monetary Fund, Climate Change Indicators Dashboard |
| Natural Earth v5.1.2 | naturalearthdata.com / nvkelso/natural-earth-vector | Public domain | Made with Natural Earth |
| geoBoundaries: AFG ADM1 | geoBoundaries (Wikimedia source) | Public domain | Runfola et al. (2020), geoBoundaries, PLOS ONE 15(4): e0231866 |
| geoBoundaries: PHL ADM2, BGD ADM2 | NAMRIA/PSA and BBS via OCHA (HDX COD-AB), packaged by geoBoundaries | CC BY 3.0 IGO (attribution required) | As above, plus OCHA COD-AB for the Philippines and Bangladesh |
| ERA5-Land monthly means | Copernicus Climate Change Service (C3S) / ECMWF | Copernicus licence: free use with attribution; derived products may be published | Muñoz Sabater, J. (2019), doi:10.24381/cds.68d2bb30 |
| EM-DAT | CRED / UCLouvain | **Non-commercial use after registration. No redistribution of records or a substantial part.** Until CRED confirms in writing, the public dashboard shows only country × year aggregates | EM-DAT, CRED / UCLouvain, Brussels, Belgium – www.emdat.be |
| GADM 4.1 | gadm.org | Academic and non-commercial use only; no redistribution without permission | Used only locally to join EM-DAT records; never committed |

## Restricted and large data: how to get them

- **EM-DAT:**
  1. Register at public.emdat.be (free for non-commercial use).
  2. Export all natural hazards, all countries, 2000 to present. Leave historic events out and the columns unchanged.
  3. Save the file as `data/raw/emdat/emdat_public_<YYYY-MM-DD>.xlsx`.

  The current analysis uses data version **2026-10-23**: 10,923 records, 9,018 distinct disasters.
- **ERA5-Land:**
  1. Create a CDS account. Put your token in `~/.cdsapirc` with `url: https://cds.climate.copernicus.eu/api` (`scripts/check_cds_auth.py` checks it).
  2. Accept the ERA5-Land licence on the dataset's Download page.
  3. Run `scripts/download_era5land.py`, then `scripts/download_era5land_tp_fix.py`.

  The second script fixes a known ERA5-Land error: the monthly product's precipitation is wrong for Sep 2022 – Feb 2024 (see `reports/era5land_drought_layer.md`).
- **Natural Earth:** run `scripts/fetch_natural_earth.py`.

## Committed files (SHA-256, first 16 characters)

| File | Size | SHA-256 |
|---|---|---|
| `raw/inform/IMF_CDIR_ECFRMC.csv` | 0.68 MB | `88b69848e2939785` |
| `raw/inform/IMF_CDIR_ECFRMH.csv` | 0.65 MB | `af970c5974ea2bef` |
| `raw/inform/IMF_CDIR_ECFRMR.csv` | 0.66 MB | `153ac585d3b0e8c1` |
| `raw/inform/IMF_CDIR_ECFRMV.csv` | 0.66 MB | `67d444dcab16f8ea` |
| `raw/inform/INFORM_CC.csv` | 0.74 MB | `409bafb939687498` |
| `raw/inform/INFORM_HA.csv` | 0.73 MB | `333edde0095cca03` |
| `raw/inform/INFORM_OVRL.csv` | 0.71 MB | `f80eeb825179f15c` |
| `raw/inform/INFORM_VU.csv` | 0.72 MB | `4455c53787453c7b` |
| `raw/natural_earth/ne_50m_admin_0_countries.zip` | 0.79 MB | `355131388b1e9d65` |
| `raw/natural_earth/ne_50m_admin_0_breakaway_disputed_areas.zip` | 0.05 MB | `cc4aadb09e1306e3` |
| `external/geoboundaries/geoBoundaries-AFG-ADM1_simplified.geojson` | 0.18 MB | `c0ae276c6df08d66` |
| `external/geoboundaries/geoBoundaries-PHL-ADM2_simplified.geojson` | 3.14 MB | `fa77b9f17db2e419` |
| `external/geoboundaries/geoBoundaries-BGD-ADM2_simplified.geojson` | 1.69 MB | `7dbdb186f3b8af10` |
