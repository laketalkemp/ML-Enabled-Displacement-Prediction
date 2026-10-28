# Week 1 findings: requests and screening

Oct 27, 2026 · LaKeta Kemp

## Status

| Week 1 task | Status |
|---|---|
| Request EM-DAT access | **Done** (Oct 27) |
| Read EM-DAT licence on redistribution | Done. Aggregates aren't explicitly covered, so ask CRED (see below) |
| Confirm proof-of-concept region | **Philippines first: decided.** Second region: Horn of Africa or Palestinian Territory, still open |
| Download Natural Earth layers and record version | Done. v5.1.2, saved in `data/raw/natural_earth/` |
| Count admin-1 units per candidate | Done (see below) |
| Check CDS CORDEX catalog | Done (see below). Reuse of the other project's download is still open |

## Findings that change the plan

1. **Natural Earth admin-1 must be 1:10m.** The 1:50m admin-1 layer covers only nine countries (AUS, BRA, CAN, CHN, IDN, IND, RUS, USA, ZAF). Use 1:10m admin-1 and simplify it for the web. Keep 1:50m for admin-0, coastline and rivers.
2. **Natural Earth's admin-1 boundaries are out of date for the candidate countries.**
   - Kenya has 8 former provinces instead of the 47 counties.
   - Ethiopia has 11 units, which predate the regions created since 2020.
   - The Philippines has 118 units: 80 provinces plus 38 cities. Merging the cities into their provinces by ISO 3166-2 code gives 83 units. Some names are stale: Compostela Valley is now Davao de Oro, ARMM is now BARMM, and Maguindanao was split in 2022. The Caraga provinces are mislabeled "Dinagat Islands (Region XIII)".
3. **EM-DAT now geocodes to GADM 4.1, not Natural Earth.** EM-DAT used GAUL 2015 until 2025 and switched to GADM 4.1 from 2026. About 90% of footprints had been migrated as of January 2026, and GAUL codes are being retired by the end of 2027. Geocoding covers only non-biological natural hazards since 2000.
   - **Impact figures are national only.** Deaths, affected and damages stay at the country level and aren't split across provinces. A province-level hazard-signature table can count events per province directly. Province-level impacts need an allocation rule (equal split or population-weighted), and that rule should be stated in the methods.
   - **GADM is non-commercial and not freely redistributable** (per GADM's licence; confirm on gadm.org). Join EM-DAT on GADM codes for the analysis. Publish on Natural Earth or another open boundary set, crosswalked via HASC or ISO 3166-2 codes (Natural Earth has `code_hasc` and `iso_3166_2`).
   - **Week 4 change:** join Philippine events through their GADM codes, not by matching to Natural Earth polygons.
4. **Country key.** `ISO_A3_EH` is -99 for Somaliland, Kosovo, Northern Cyprus and Siachen Glacier. `ADM0_A3` is always filled but differs from ISO for some places (Palestine is PSX, ISO PSE; South Sudan is SDS, ISO SSD). Join on `ISO_A3_EH`, fall back to `ADM0_A3`, and keep an alias table. Natural Earth splits Somaliland (SOL) from Somalia, while INFORM and EM-DAT use SOM for both.
5. **Palestine in Natural Earth** has `TYPE` = Indeterminate and `SOVEREIGNT` = Israel. This is the same in the default file and in the Palestinian, Israeli and US worldview files (attributes checked; geometry not compared). The disputed-area policy should name the worldview used, and the dashboard shouldn't show `SOVEREIGNT`.

## Admin-1 counts (Natural Earth 1:10m)

| Region | Natural Earth units | Current official units (approx.) |
|---|---|---|
| Philippines | 118 (83 after merging cities into provinces) | 82 provinces plus Metro Manila |
| Horn of Africa (KEN, SOM, ETH) | 32 (8 + 13 + 11) | ~79 (47 counties, 18 regions, ~14 regions/cities) |
| Palestinian Territory | 2 (Gaza Strip, West Bank) | 16 governorates (11 West Bank, 5 Gaza) |
| Bay of Bengal (BGD, MMR) | 21 | — |
| Mozambique Channel (MOZ, MDG, MWI) | 61 | — |

For the Horn of Africa, the plan's 30+ unit threshold is met only with current boundaries from OCHA COD-AB or geoBoundaries. Check the licence for each country before using them.

## EM-DAT licence

- Use is free for non-commercial academic work after registration. Commercial use needs a paid subscription.
- The terms prohibit distributing EM-DAT or "a substantial part" of it, sharing "any portion" over the internet with unauthorized users, and creating substitute or derivative databases.
- **They say nothing explicit about publishing aggregated statistics or maps.** CRED itself publishes yearly country × disaster-type aggregates on HDX (EM-DAT Country Profiles). It also recommends the versioned EM-DAT Archive (CC BY-NC-ND 4.0) for research.
- Required citation: "EM-DAT, CRED / UCLouvain, Brussels, Belgium – www.emdat.be".
- **Action:** email CRED to confirm that admin-1 × hazard × year aggregates, with no event rows, can go on GitHub Pages. Until then, keep the public dashboard at country-year aggregates. Pin the analysis to an Archive version for reproducibility. (Not legal advice.)

## CORDEX on the Climate Data Store

Dataset: *CORDEX regional climate model data on single levels* (`projections-cordex-domains-single-levels`). The dataset page names its licence only as "CORDEX licence".

- **14 domains**, including South-East Asia, Africa, Middle East and North Africa, and Mediterranean.
- **Experiments:** evaluation (ERA-Interim), historical, RCP2.6, RCP4.5 and RCP8.5. The drivers are CMIP5 only; this entry has no CORDEX-CMIP6 runs.
- **Variables cover every index in the plan.** Daily precipitation supports SPI, consecutive dry days, Rx5day and R95p. Daily max and min temperature support heat-wave days and Hargreaves potential evapotranspiration for SPEI. Evaporation is also offered.
- **South-East Asia** has 14 GCM–RCM pairs with daily precipitation, all at 0.22°. Six of them form a clean 3 × 2 matrix with historical, RCP2.6 and RCP8.5: REMO2015 and RegCM4-7, each driven by HadGEM2-ES, MPI-ESM and NorESM1-M. RCP4.5 exists only for the RegCM4-3 and RCA4 runs.
- **Africa** has 37 pairs at 0.22° or 0.44°. The same REMO2015 and RegCM4-7 × HadGEM2-ES/MPI-ESM/NorESM1-M matrix exists at 0.22° with RCP2.6 and RCP8.5.
- **Middle East and North Africa** has 6 pairs, mostly at 0.44°. Only RCA4, driven by EC-Earth and GFDL-ESM2M, is at 0.22°. The Mediterranean domain has 2 pairs at 0.11°.

**Suggested ensemble:** the 6-member REMO2015/RegCM4-7 × 3-GCM matrix at 0.22°, historical plus RCP2.6 and RCP8.5. The same design is available for the Philippines and the Horn of Africa, so the two regions are directly comparable. One caveat: REMO2015 uses MPI-ESM-LR and RegCM4-7 uses MPI-ESM-MR.

**Still open:** whether the downscaling project's CORDEX files can be reused. Downloads need a CDS account and acceptance of the CORDEX licence.

## Second region: Horn of Africa vs. Palestinian Territory

| Criterion (from the plan) | Horn of Africa (KEN, SOM, ETH) | Palestinian Territory |
|---|---|---|
| 1. ≥30 admin-1 units | ~79 with current boundaries (32 in Natural Earth) | 16 governorates (2 in Natural Earth) in two disconnected pieces. **Below threshold;** Moran's I, LISA and Gi* won't be meaningful |
| 2. Dense EM-DAT record, >1 hazard type | Drought and flood, recurring | Few natural-hazard events (floods, storms, heat; verify in the export). EM-DAT doesn't record conflict |
| 3. Hazard variation inside the region | Strong: arid lowlands, highlands, coast | Limited; about 6,000 km² in total |
| 4. IDMC outcomes | 2025: Somalia 214k conflict / 335k disaster; Ethiopia 353k / 244k | 2025: ~2.76M displacements listed for Palestine. The GRID summary gives no conflict/disaster split, but nearly all are likely conflict-related (verify). That would validate a conflict signal, not hazard clusters |
| 5. Open subnational data | IPC, FEWS NET, county data | PCBS, OCHA, IPC for Gaza |
| CORDEX fit | Africa domain, 0.22°, matches the Philippine ensemble | MENA domain, mostly 0.44°. Gaza (~340 km²) is smaller than one 0.22° cell (~500 km²); the West Bank is ~11 cells |
| Famine pathway | Drought → food insecurity, the plan's intended proxy | IPC confirmed famine in Gaza Governorate in Aug 2025. No area is in Phase 5 in the Apr–Dec 2026 analysis, but 67% are projected in Phase 3+. Drivers are hostilities and access restrictions, not drought |
| Disputed-area handling | Somaliland | Central to the case |

**Recommendation:**
- **Horn of Africa** is the stronger second case for the hazard-clustering statistics.
- **Palestinian Territory** fits poorly as a spatial-statistics region but strongly as a **data-justice case study** for March (the plan allows 2–3 case studies). It would show how standard sources render a place, a central concern of this project:
  - Natural Earth's attributes list its sovereign as Israel.
  - EM-DAT excludes conflict.
  - Its hazard grid cells are coarser than its governorates.
  - IPC's famine pathway there runs through conflict, not drought.

  It would also give the Workshop 3 ethics presentation a concrete example.

## Next actions

**LaKeta**
- [ ] Choose the second region, or Horn of Africa for statistics plus Palestine as a case study
- [ ] Email CRED about publishing aggregates on GitHub Pages
- [ ] Export EM-DAT (full or PHL, KEN, SOM, ETH, PSE) into the grant folder, not into the public repo
- [ ] Check whether the downscaling project's CORDEX files can be reused (domain, variables, licence)
- [ ] Create a CDS account and accept the CORDEX licence, if not done already

**Claude**
- [ ] Week 2: refactor the notebook into a repository and reproduce the baseline
- [ ] Week 3: build the crosswalk with GADM ↔ Natural Earth via HASC/ISO 3166-2, decide the Philippine geometry, and draft the disputed-area policy
