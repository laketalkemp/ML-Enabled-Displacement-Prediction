# Proof-of-concept regions: province layers

Built October 27, 2026. The proof-of-concept regions are the **Philippines** (first) and **Afghanistan** (second, replacing the Horn of Africa).

## Files

| File | Contents |
|---|---|
| `poc_provinces.gpkg` | Layers `phl_provinces` (82 units) and `afg_provinces` (34 units), in EPSG:4326 |
| `phl_province_crosswalk.csv` | Philippine units with ISO 3166-2 ID, aliases, matching Natural Earth province and overlap, merged geoBoundaries IDs, notes |
| `afg_province_crosswalk.csv` | Afghan units with ISO 3166-2 ID, HASC code, Natural Earth code, geoBoundaries spelling and overlap, label fixes |
| `scripts/build_poc_regions.py` | Rebuilds everything above: `python scripts/build_poc_regions.py` |
| `data/external/geoboundaries/` | geoBoundaries inputs and their metadata |

The join key is `unit_id`, the ISO 3166-2 code. Metro Manila uses `PH-00`, the NCR region code.

## Philippines: 82 provinces

- **Geometry:** PSA/NAMRIA provinces via OCHA, taken from geoBoundaries gbOpen PHL ADM2 (CC BY 3.0 IGO; source updated 2023). Attribution is required when published.
- **Why not Natural Earth:** its 1:10m layer has 118 units mixing provinces and cities, and it lacks Dinagat Islands (created 2006) and Davao Occidental (created 2013).
- **Merges:**
  - the four NCR districts into Metro Manila
  - City of Isabela into Basilan
  - Cotabato City into Maguindanao
- **Pre-2019/2022 names are kept on purpose**, to match the EM-DAT and GADM period (2000–2025):
  - Compostela Valley carries the alias Davao de Oro.
  - Maguindanao is kept whole (not split into del Norte and del Sur).
- **Small provinces:** 27 are smaller than four CORDEX 0.22° cells (~590 km² each). Aggregate with area-weighted fractional overlap and a land-sea mask.

## Afghanistan: 34 provinces

- **Geometry:** Natural Earth 1:10m v5.1.2 (public domain).
- **Label fixes:** Natural Earth names Panjshir "Parwan" (AF-PAR) and Daykundi "Uruzgan" (AF-URU). Both are corrected to AF-PAN and AF-DAY, and the `label_fixed` column records the original values.
- **Spelling aliases** from geoBoundaries:
  - Jawzjan / Jowzjan
  - Hirat / Herat
  - Nimroz / Nimruz
  - Paktya / Paktia
  - Hilmand / Helmand
  - Sari Pul / Sar-e Pol
  - Ghazni / "Ghanzi" (a geoBoundaries typo)

  EM-DAT/GADM and IPC may use other spellings. Add them to `aliases` as they appear.
- **Boundary match:** every province's largest overlap with geoBoundaries is the same-named province. Overlap is 91% or more for 26 provinces and 81–86% for Samangan, Kapisa and Wardak. Panjshir is lowest (76%) because of a different Panjshir–Kapisa boundary. Compare against OCHA COD-AB (AGCHO) when it can be downloaded from HDX.
- **Province size:** median ~14,600 km², and only Kapisa is smaller than four CORDEX cells.
- **Border:** Natural Earth draws the Durand Line as the Afghanistan–Pakistan border, which Afghanistan's authorities do not recognize. Note this in the disputed-area policy.

## Next joins

- **EM-DAT:** events carry GADM 4.1 admin units. Build the GADM → `unit_id` lookup from the export's admin-unit names and codes, using `aliases`.
- **Impact figures:** deaths, affected and damages are national only, so province allocation needs a stated rule.

## CORDEX ensemble (CDS, daily precipitation and max/min temperature)

| Region | Domain | REMO2015 runs (shared) | Second RCM |
|---|---|---|---|
| Philippines | South-East Asia, 0.22° | HadGEM2-ES, MPI-ESM-LR, NorESM1-M | RegCM4-7 (ICTP) × HadGEM2-ES, MPI-ESM-MR, NorESM1-M |
| Afghanistan | South Asia, 0.22° | HadGEM2-ES, MPI-ESM-LR, NorESM1-M | RegCM4-7 (ORNL) × MIROC5, MPI-ESM-MR, NorESM1-M |

- All runs offer historical, RCP2.6 and RCP8.5. The REMO2015 trio is identical in both regions, so use it for the head-to-head comparison.
- COSMO-crCLIM (MPI-ESM-LR, NorESM1-M, EC-Earth) is a South Asia alternative to RegCM4-7. Its EC-Earth run has RCP8.5 only.
- **Observational check:** CHIRPS precipitation and ERA5-Land temperature. Gauges are sparse in Afghanistan and CHIRPS is weaker over high terrain, so treat the check as indicative.
- **Afghanistan-specific index issues:**
  - Hyper-arid southern provinces (Nimroz, Hilmand, Kandahar) have many zero-rain months. Use SPI with the probability-of-zero adjustment and 6- or 12-month accumulations.
  - Drought there is partly snow-driven, which SPI misses. Pair it with SPEI.
