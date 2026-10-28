"""Fix download for a known ERA5-Land issue (precipitation, Sep 2022-Feb 2024).

ECMWF's "monthly averaged reanalysis" product has wrong accumulated variables, including total
precipitation, for September 2022 to February 2024, and the files are not being replaced. The
documented workaround is the "monthly averaged reanalysis by hour of day" product at 00:00.
https://forum.ecmwf.int/t/issue-affecting-era5-land-monthly-averaged-reanalysis-for-the-period-september-2022-to-february-2024/2370

Run once from the repository root (a few minutes; one small request per region):

    python scripts/download_era5land_tp_fix.py

It fetches total precipitation only, for all months of 2022-2024. The unaffected months are used to
check that the two products agree before drought_indices.py substitutes the affected ones.
Files are saved to data/raw/era5land/; existing files are skipped.
"""
import os
import cdsapi

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw", "era5land")
os.makedirs(OUT, exist_ok=True)

REGIONS = {  # [North, West, South, East], same boxes as the main download
    "PHL": [21.5, 116.0, 4.0, 127.0],
    "AFG": [39.0, 60.0, 29.0, 75.5],
    "BGD": [27.0, 87.5, 20.0, 93.0],
}

client = cdsapi.Client()
for iso, area in REGIONS.items():
    target = os.path.join(OUT, f"era5land_byhour00_tp_{iso}_2022_2024.nc")
    if os.path.exists(target) and os.path.getsize(target) > 0:
        print(f"{iso}: already downloaded, skipping")
        continue
    print(f"{iso}: requesting...")
    client.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "product_type": ["monthly_averaged_reanalysis_by_hour_of_day"],
            "variable": ["total_precipitation"],
            "year": ["2022", "2023", "2024"],
            "month": [f"{m:02d}" for m in range(1, 13)],
            "time": ["00:00"],
            "area": area,
            "data_format": "netcdf",
            "download_format": "unarchived",
        },
        target,
    )
    print(f"{iso}: saved {target} ({os.path.getsize(target) / 1e6:.1f} MB)")
print("Done. Next: python scripts/drought_indices.py")
