# EM-DAT export profile

Oct 27, 2026 · LaKeta Kemp

**File:** `data/raw/emdat/emdat_public_2026-10-27.xlsx` (local only). EM-DAT data version **2026-10-23**, custom request created Oct 28, 2026 01:44 UTC.

**Citation:** "EM-DAT, CRED / UCLouvain, Brussels, Belgium – www.emdat.be"

## The export as a whole

- **Size and scope:** 10,923 records with 47 columns. All are natural hazards, from 220 countries, with start years 2000–2026, and none flagged historic.
- **Integrity:** every record ID (`DisNo.`) is unique and there are no duplicate rows.
- **Records vs. disasters:** each record is one country's part of a disaster. There are **9,018 distinct disasters**, of which 869 span more than one country. Count events on the first nine characters of `DisNo.` (e.g. `2023-0001`).
- **Records per year:** 337–505, typically ~400. **2026 is incomplete:** 177 records to Oct 23, against ~420 in a typical year, because of entry lag. **Use 2000–2025 for analysis.**
- **Biological hazards:** 925 epidemics and infestations. They fall from 115 in 2000 to 12 in 2025, which looks like a change in reporting. They are out of scope and excluded.
- **Records by hazard type:**

  | Type | Records |
  |---|---|
  | Flood | 4,296 |
  | Storm | 2,940 |
  | Earthquake | 708 |
  | Extreme temperature | 607 |
  | Wet mass movement | 505 |
  | Drought | 426 |
  | Wildfire | 358 |
- **Location fields:**
  - GAUL `Admin Units`: 76% of records
  - GADM `GADM Admin Units`: 72%
  - `Latitude`/`Longitude`: 17%
  - GADM entries are at level 1 (`gid_1`, `name_1`) or level 2 (`gid_2`, `name_2`). Each has a migration date and method.
- **Damages:**
  - `Total Damage, Adjusted ('000 US$)` is already adjusted for inflation by EM-DAT. That covers the inflation step in Week 4.
  - It is filled for only 30% of records, so damage-based features will be sparse.

## The three regions (2000–2025, epidemics excluded)

| | Philippines | Afghanistan | Bangladesh |
|---|---|---|---|
| Records | 388 | 158 | 146 |
| Main types | Storm 211, flood 109, earthquake 27, volcanic 18, wet mass movement 17 | Flood 92, wet mass movement 23, earthquake 22, storm 8, extreme temperature 7 | Storm 72, flood 46, extreme temperature 15 |
| **Drought records** | **4** | **6** | **1** |
| Records assigned to a unit | 93% | 97% | 99% |
| Assignment source | GADM 329, Location text 28, GAUL 5 | GADM 103, Location text 47, GAUL 4 | GADM 115, GAUL 15, Location text 14 |
| Analysis units | 81 provinces | 34 provinces | 64 districts |
| Events per unit, 2000–2025 (min / median / max) | 14 / 44 / 81 | 8 / 15 / 43 | 1 / 12 / 35 |
| Units with fewer than 5 events | 0 | 0 | 7 |

**How records were assigned to units:**
- Records go to provinces (districts for Bangladesh) using GADM codes first, then GAUL names, then province or district names found in the `Location` text.
- **Province names match in full.** All 34 Afghan provinces match the province layer, and the export uses the same spellings as Natural Earth. Two Afghan GADM codes (`AFG.3_1`, `AFG.5_1`) never appear with a name; GADM's alphabetical order makes them Baghlan and Bamyan. All 64 Bangladesh districts match geoBoundaries exactly. The 81 Philippine GADM provinces match after two aliases: North Cotabato is Cotabato, and Metropolitan Manila is Metro Manila.
- **GADM 4.1 has no Davao Occidental**, so for EM-DAT work it is folded into Davao del Sur. That gives 81 Philippine units, not 82.

**Spot checks:**
- Cyclone Sidr (2007) maps to the expected 12 coastal districts in Bangladesh.
- The October 2023 Herat earthquake maps to Herat.
- Typhoon Haiyan's GADM footprint lists Leyte, Western Samar, Cebu, Iloilo, Capiz, Aklan and Palawan, but **not Eastern Samar**, where it made landfall. Treat footprints as incomplete. For storms, check them against IBTrACS tracks.

## What this means for the plan

1. **Drought can't come from EM-DAT at province level.** There are only 11 drought records across all three regions. Afghanistan's drought archetype would rest on 6 national-level events. Recommendation: make an **observed drought index** (SPI/SPEI from ERA5-Land or CHIRPS, 2000–2025) a core input for every province. Keep CORDEX for the future-scenario layer, which remains the item to cut first.
2. **The province tables are big enough for spatial statistics.** Every Philippine and Afghan province has at least 8 events. Bangladesh has 7 districts with fewer than 5, so pool years or hazard types there.
3. **Assignments made from Location text are flagged as lower confidence** (89 records). For example, "Quezon City" can match Quezon province. Review them before the Week 4 hazard-signature table.
4. **Analysis window: 2000–2025.**

## Files

- `scripts/emdat_province_counts.py` reproduces everything below. It writes to `data/processed/emdat/`, which is git-ignored.
- `data/processed/emdat/ (local only) record_unit_assignment_PHL_AFG_BGD.csv` lists each record's units and the source of the assignment.
- `data/processed/emdat/ (local only) {phl,afg,bgd}_event_counts_by_unit_2000_2025.csv` has events per unit by hazard type.

These are EM-DAT-derived files. They stay local and out of the public repository (see `data/README.md`).
