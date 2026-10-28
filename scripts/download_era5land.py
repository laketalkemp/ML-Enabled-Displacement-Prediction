"""Download ERA5-Land monthly means for the three study regions (drought index input).

One-time run, about 5-15 minutes depending on the CDS queue. From the repository root:

    pip install cdsapi          # skip if already installed
    python scripts/download_era5land.py

Needs your existing CDS API key (~/.cdsapirc) and the ERA5-Land licence accepted on the
dataset's Download page (reanalysis-era5-land-monthly-means). Files that already exist are skipped,
so it is safe to re-run if it stops partway.

What it fetches: total precipitation and 2 m temperature, 1991-2025, monthly, 0.1 degree,
cropped to each region's bounding box. 1991-2020 is the WMO baseline for SPI/SPEI.
Note for processing: monthly-mean total_precipitation is the mean daily accumulation in metres;
multiply by days in the month x 1000 for mm/month.
"""
import os
import cdsapi

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "era5land")
os.makedirs(OUT, exist_ok=True)

# [North, West, South, East], padded ~0.5 degree beyond each country
REGIONS = {
    "PHL": [21.5, 116.0, 4.0, 127.0],
    "AFG": [39.0, 60.0, 29.0, 75.5],
    "BGD": [27.0, 87.5, 20.0, 93.0],
}
YEARS = [str(y) for y in range(1991, 2026)]

client = cdsapi.Client()
for iso, area in REGIONS.items():
    target = os.path.join(OUT, f"era5land_monthly_{iso}_1991_2025.nc")
    if os.path.exists(target) and os.path.getsize(target) > 0:
        print(f"{iso}: already downloaded, skipping")
        continue
    print(f"{iso}: requesting...")
    client.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["total_precipitation", "2m_temperature"],
            "year": YEARS,
            "month": [f"{m:02d}" for m in range(1, 13)],
            "time": ["00:00"],
            "area": area,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        target,
    )
    print(f"{iso}: saved {target} ({os.path.getsize(target) / 1e6:.1f} MB)")
print("Done.")
