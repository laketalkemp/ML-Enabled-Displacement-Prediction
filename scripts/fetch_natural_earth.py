"""Download the Natural Earth layers used by the project (public domain).

    python scripts/fetch_natural_earth.py

Source: the official Natural Earth repository (nvkelso/natural-earth-vector), tag v5.1.2, the latest
tagged release. Each layer is saved as a zipped shapefile in data/raw/natural_earth/. The two small
admin-0 layers are already committed; this script fetches the rest (the 1:10m admin-1 layer is 15 MB).
"""
import io
import os
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "natural_earth"
BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2"
LAYERS = [
    "50m_cultural/ne_50m_admin_0_countries",
    "50m_cultural/ne_50m_admin_0_breakaway_disputed_areas",
    "10m_cultural/ne_10m_admin_1_states_provinces",   # admin-1 must be 1:10m (1:50m covers 9 countries)
    "50m_physical/ne_50m_coastline",
    "50m_physical/ne_50m_rivers_lake_centerlines",
    "50m_physical/ne_50m_lakes",
]
PARTS = ["shp", "shx", "dbf", "prj", "cpg", "README.html", "VERSION.txt"]

OUT.mkdir(parents=True, exist_ok=True)
for layer in LAYERS:
    name = layer.split("/")[-1]
    target = OUT / f"{name}.zip"
    if target.exists():
        print(f"{name}: present, skipping")
        continue
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for ext in PARTS:
            try:
                with urllib.request.urlopen(f"{BASE}/{layer}.{ext}") as r:
                    z.writestr(f"{name}.{ext}", r.read())
            except Exception as e:  # README/VERSION are optional
                if ext in ("shp", "shx", "dbf", "prj"):
                    raise SystemExit(f"{name}.{ext}: download failed ({e})")
    target.write_bytes(buf.getvalue())
    print(f"{name}: saved ({target.stat().st_size / 1e6:.1f} MB)")
print("Done.")
