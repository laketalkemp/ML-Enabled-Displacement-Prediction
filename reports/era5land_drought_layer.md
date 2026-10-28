# ERA5-Land drought layer

Built October 27, 2026. This is the observed drought input for the hazard-signature tables. EM-DAT has too few drought records to serve at province level: 11 across the three regions.

## Data

- **Source:** ERA5-Land monthly means (C3S/ECMWF), 1991–2025, 0.1°: total precipitation and 2 m temperature, cropped to the Philippines, Afghanistan and Bangladesh.
- **Files:**
  - `data/raw/era5land/era5land_monthly_{PHL,AFG,BGD}_1991_2025.nc` (not committed): the main download.
  - `data/raw/era5land/era5land_byhour00_tp_{PHL,AFG,BGD}_2022_2024.nc` (not committed): precipitation fix for **Sep 2022 – Feb 2024**.
- **The fix:**
  - ECMWF has confirmed that the monthly product's accumulated variables are wrong for these months and won't replace them ([announcement](https://forum.ecmwf.int/t/issue-affecting-era5-land-monthly-averaged-reanalysis-for-the-period-september-2022-to-february-2024/2370)). Uncorrected, the error shows up as a false 2023 drought in all three regions, with rainfall at about half of normal.
  - The fix uses ECMWF's documented workaround, the "by hour of day" product at 00:00. In unaffected months it matches the monthly product exactly (ratio 1.000).
  - `scripts/drought_indices.py` refuses to run without the fix files.
- **Citation:** Muñoz Sabater, J. (2019): ERA5-Land monthly averaged data from 1950 to present. Copernicus Climate Change Service (C3S) Climate Data Store. doi:10.24381/cds.68d2bb30.

## Method (`scripts/drought_indices.py`)

1. **Unit averages.** Each grid cell is weighted by its exact area of overlap with the unit, using land cells only. Batanes (PH-BTN) has no land cell, so it takes the nearest one.
2. **Units.** These match the EM-DAT tables: 81 Philippine provinces (Davao Occidental folded into Davao del Sur), 34 Afghan provinces and 64 Bangladesh districts.
3. **Indices.** SPI-3/6/12 use a gamma distribution. SPEI-6/12 use Pearson III with Thornthwaite potential evaporation. Both are calibrated on **1991–2020** with the `climate-indices` package.
4. **Drought definitions.**
   - A drought month has an index of −1.0 or lower; a severe one, −1.5 or lower.
   - A drought event is 3 or more consecutive months with SPI-6 at −1.0 or lower.
5. **Fit warnings.** The gamma fit is weak for a few calendar months, mostly the dry summer months in arid Afghan provinces (9 warnings; 1 for Bangladesh, none for the Philippines).

## Outputs (`data/processed/drought/`)

| File | Contents |
|---|---|
| `{iso}_monthly_drought_indices_1991_2025.csv` | Per unit and month: precipitation, temperature, potential evaporation, SPI-3/6/12, SPEI-6/12 |
| `{iso}_drought_annual_2000_2025.csv` | Per unit and year: precipitation, drought months (SPI-6, SPEI-6), severe months, minimum SPI-12 |
| `{iso}_drought_summary_2000_2025.csv` | Per unit: drought and severe months, number of events, longest event, worst severity, mean annual precipitation |

These files contain no EM-DAT data and can be published with the ERA5-Land citation above.

## Checks

**Agreement with EM-DAT droughts.** For each recorded drought, this is the share of months in drought (SPI-6 ≤ −1) across the provinces EM-DAT lists. By chance it would be about 16%. The full table is in `data/processed/emdat/` (local only).

| Agreement | Records |
|---|---|
| Strong (≥ 48%) | Afghanistan 2000–02 (60%), 2006 (54%), 2008 (75%), 2011 (70%); Philippines 2002 (100%); Bangladesh 2009 (57%) |
| Moderate (26–37%) | Afghanistan 2021–23 (34%); Philippines 2015–16 (37%), 2019 (26%) |
| None in window | Afghanistan 2018–19 (12%); Philippines 2007 (0%) |

The 2018 Afghan deficit peaked in **January–March 2018**, when SPI-6 fell to about −2. EM-DAT's record starts in April 2018, after the rain shortfall. Impacts lag the deficit, so link EM-DAT impacts to the index with a lead window of a few months.

**Drought years, 2000–2025** (ranked by the average number of drought months per unit):

| Region | Top years |
|---|---|
| Afghanistan | 2000, 2001, 2025, 2021, 2008 |
| Bangladesh | 2014, 2012, 2022, 2023 |
| Philippines | 2005, 2010, 2003, 2004, 2015 |

## Caveats

- **The Philippine baseline may be shifting.** The Philippines was wetter in 2000–2025 than in the 1991–2020 baseline: 2020–2025 all sit above the baseline mean, and 2025 is +39%. Its provinces therefore show fewer drought months (median 28 of 312) than Afghanistan (69) or Bangladesh (66). ERA5 precipitation trends can be inhomogeneous, so compare against CHIRPS or PAGASA stations before interpreting trends.
- **Snow drought is missed.** In Afghanistan, drought is partly driven by snowpack, which SPI misses. SPEI and winter-season (October–March) totals help.
- **Reanalysis rainfall is model output** constrained by sparse observations, especially in Afghanistan. Treat the indices as exposure estimates.
