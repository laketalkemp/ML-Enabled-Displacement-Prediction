"""Province/district drought indices from ERA5-Land monthly means (observed drought layer).

Run after scripts/download_era5land.py and scripts/download_era5land_tp_fix.py:

    python scripts/drought_indices.py

Method
- Precipitation: monthly-mean `tp` (mean daily accumulation, m) x days in month x 1000 = mm/month.
  Sep 2022-Feb 2024 comes from the "by hour of day" 00:00 product instead, because of a known ERA5-Land
  issue in the monthly product for those months (needs scripts/download_era5land_tp_fix.py).
- Unit means: area-weighted over ERA5-Land land cells (exact cell-polygon overlap, equal-area CRS).
  A unit with no valid land cell (small islands) takes the nearest land cell.
- PET: Thornthwaite from monthly 2 m temperature and the unit's latitude (climate-indices).
- SPI-3/6/12 (gamma) and SPEI-6/12 (Pearson III), calibrated on 1991-2020, computed on unit series.
- Drought month: index <= -1.0; severe: <= -1.5. Drought event: run of >= 3 consecutive months with
  SPI-6 <= -1.0; severity = sum of SPI-6 over the run.
Units match the EM-DAT tables: 81 Philippine provinces (Davao Occidental folded into Davao del Sur),
34 Afghan provinces, 64 Bangladesh districts.
Outputs (data/processed/drought/): monthly series, annual drought months, and a 2000-2025 summary per unit.
ERA5-Land: Copernicus Climate Change Service; cite Munoz Sabater (2019), doi:10.24381/cds.68d2bb30.
"""
import glob, os
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])   # paths below are repo-relative
os.environ.setdefault('CLIMATE_INDICES_LOG_LEVEL', 'WARNING')   # quiet the library's per-call logs
import numpy as np, pandas as pd, xarray as xr, geopandas as gpd
from shapely.geometry import box
from climate_indices import indices, eto, compute

DATA, OUT = 'data/raw/era5land', 'data/processed/drought'
CAL0, CAL1 = 1991, 2020
SUMMARY0, SUMMARY1 = 2000, 2025
EA = 6933  # equal-area CRS for weights
os.makedirs(OUT, exist_ok=True)


def load_units(iso):
    if iso == 'PHL':
        u = gpd.read_file('data/processed/regions/poc_provinces.gpkg', layer='phl_provinces')[['unit_id', 'name', 'geometry']]
        u.loc[u.unit_id == 'PH-DVO', ['unit_id', 'name']] = ['PH-DAS', 'Davao del Sur']   # match GADM 4.1 / EM-DAT
        u = u.dissolve(by='unit_id', aggfunc='first').reset_index()
    elif iso == 'AFG':
        u = gpd.read_file('data/processed/regions/poc_provinces.gpkg', layer='afg_provinces')[['unit_id', 'name', 'geometry']]
    else:
        u = gpd.read_file('data/external/geoboundaries/geoBoundaries-BGD-ADM2_simplified.geojson')
        u = u.rename(columns={'shapeName': 'name'}).assign(unit_id=lambda d: d['name'])[['unit_id', 'name', 'geometry']]
    return u.to_crs(4326)


def _tidy(ds):
    t = 'valid_time' if 'valid_time' in ds.dims else 'time'
    ds = ds.rename({t: 'time'})
    for extra in ('number', 'expver'):
        if extra in ds.dims:
            ds = ds.isel({extra: 0})
    ds = ds.drop_vars([v for v in ('number', 'expver') if v in ds.coords])
    return ds.sortby('time').sortby('latitude')


# Known ERA5-Land issue: the "monthly averaged reanalysis" product has wrong accumulated variables
# (incl. total precipitation) for Sep 2022-Feb 2024, and ECMWF is not replacing them. The documented
# workaround is the "monthly averaged reanalysis by hour of day" product at 00:00, fetched by
# scripts/download_era5land_tp_fix.py. Here it replaces tp for those months.
BAD0, BAD1 = '2022-09-01', '2024-02-01'


def open_era5(path, iso):
    ds = _tidy(xr.open_dataset(path))
    tp = ds['tp']
    fix = sorted(glob.glob(f'{DATA}/era5land_byhour00_tp_{iso}_*.nc'))
    bad = (tp.time >= np.datetime64(BAD0)) & (tp.time <= np.datetime64(BAD1))
    if not fix:
        raise SystemExit(f'{iso}: missing the precipitation fix file for Sep 2022-Feb 2024 '
                         f'(run scripts/download_era5land_tp_fix.py first)')
    tp00 = _tidy(xr.open_dataset(fix[-1]))['tp']
    # the by-hour product stamps each month on day 2 at 00:00; align to month start like the monthly product
    tp00 = tp00.assign_coords(time=tp00.time.values.astype('datetime64[M]').astype('datetime64[ns]'))
    tp00 = tp00.reindex_like(tp, method=None)
    # check the by-hour product against the monthly product in months outside the affected period
    ok = (~bad) & tp00.notnull().any(['latitude', 'longitude'])
    a, b = tp.where(ok).mean(['latitude', 'longitude']), tp00.where(ok).mean(['latitude', 'longitude'])
    ratio = float((b / a).median(skipna=True))
    print(f'{iso}: by-hour-00 vs monthly product, unaffected overlap months median ratio {ratio:.3f}')
    if not 0.9 < ratio < 1.1:
        raise SystemExit(f'{iso}: fix file does not agree with the monthly product (ratio {ratio:.2f}); check units')
    tp = xr.where(bad, tp00, tp).transpose(*ds['tp'].dims)
    missing = int(((tp.notnull().sum(['latitude', 'longitude']) == 0) & bad).sum())
    if missing:
        raise SystemExit(f'{iso}: {missing} affected months not covered by the fix file')
    print(f'{iso}: replaced total precipitation for {int(bad.sum())} months (Sep 2022-Feb 2024) with the 00:00 by-hour product')
    days = ds.time.dt.days_in_month
    precip = tp * days * 1000.0                 # mm/month
    temp = ds['t2m'] - 273.15                   # deg C (instantaneous variable, not affected)
    return precip.transpose('time', 'latitude', 'longitude'), temp.transpose('time', 'latitude', 'longitude')


def cell_weights(lat, lon, valid, units):
    """Exact overlap weights between 0.1-degree cells and unit polygons."""
    dlat, dlon = abs(float(lat[1] - lat[0])), abs(float(lon[1] - lon[0]))
    LA, LO = np.meshgrid(lat, lon, indexing='ij')
    cells = gpd.GeoDataFrame({'i': np.repeat(np.arange(len(lat)), len(lon)), 'j': np.tile(np.arange(len(lon)), len(lat))},
                             geometry=[box(x - dlon / 2, y - dlat / 2, x + dlon / 2, y + dlat / 2) for y, x in zip(LA.ravel(), LO.ravel())],
                             crs=4326)
    cells = cells[valid.ravel()]
    ov = gpd.overlay(units[['unit_id', 'geometry']].to_crs(EA), cells.to_crs(EA), how='intersection', keep_geom_type=True)
    ov['w'] = ov.area
    W = {u: g[['i', 'j', 'w']] for u, g in ov.groupby('unit_id')}
    # fallback: nearest valid cell to a representative point
    fallback = []
    vi, vj = np.where(valid)
    for _, r in units.iterrows():
        if r.unit_id not in W or W[r.unit_id].w.sum() == 0:
            p = r.geometry.representative_point()
            k = np.argmin((LA[vi, vj] - p.y) ** 2 + ((LO[vi, vj] - p.x) * np.cos(np.radians(p.y))) ** 2)
            W[r.unit_id] = pd.DataFrame({'i': [vi[k]], 'j': [vj[k]], 'w': [1.0]})
            fallback.append(r.unit_id)
    return W, fallback


def unit_series(arr, W):
    a = arr.values
    out = {}
    for u, w in W.items():
        vals = a[:, w.i.values, w.j.values]
        out[u] = np.nansum(vals * w.w.values, axis=1) / np.sum(w.w.values)
    return pd.DataFrame(out, index=pd.to_datetime(arr.time.values))


def drought_runs(series, thresh=-1.0, min_len=3):
    runs, cur = [], []
    for v in series.values:
        if np.isfinite(v) and v <= thresh:
            cur.append(v)
        else:
            if len(cur) >= min_len:
                runs.append(cur)
            cur = []
    if len(cur) >= min_len:
        runs.append(cur)
    return runs


for iso in ['PHL', 'AFG', 'BGD']:
    files = sorted(glob.glob(f'{DATA}/era5land_monthly_{iso}_*.nc'))
    if not files:
        print(f'{iso}: no file in {DATA}, skipped')
        continue
    precip, temp = open_era5(files[-1], iso)
    start = int(precip.time.dt.year[0])
    if start > CAL0:
        raise SystemExit(f'{iso}: data start {start} is after calibration start {CAL0}')
    units = load_units(iso)
    valid = np.isfinite(precip.isel(time=0).values) & np.isfinite(temp.isel(time=0).values)
    W, fallback = cell_weights(precip.latitude.values, precip.longitude.values, valid, units)
    P, T = unit_series(precip, W), unit_series(temp, W)
    lat = units.set_index('unit_id').geometry.representative_point().y

    rows = []
    for u in P.columns:
        p, t = P[u].values, T[u].values
        pet = eto.eto_thornthwaite(t, float(lat[u]), start)
        rec = {'unit_id': u, 'date': P.index, 'precip_mm': p, 't2m_c': t, 'pet_mm': pet}
        for s in (3, 6, 12):
            rec[f'spi{s}'] = indices.spi(p, s, indices.Distribution.gamma, start, CAL0, CAL1, compute.Periodicity.monthly)
        for s in (6, 12):
            rec[f'spei{s}'] = indices.spei(p, pet, s, indices.Distribution.pearson, compute.Periodicity.monthly, start, CAL0, CAL1)
        rows.append(pd.DataFrame(rec))
    m = pd.concat(rows)
    m['year'] = m.date.dt.year
    m.to_csv(f'{OUT}/{iso.lower()}_monthly_drought_indices_{start}_{m.year.max()}.csv', index=False, float_format='%.4f')

    w = m[(m.year >= SUMMARY0) & (m.year <= SUMMARY1)]
    annual = w.groupby(['unit_id', 'year']).agg(
        precip_mm=('precip_mm', 'sum'),
        drought_months_spi6=('spi6', lambda x: int((x <= -1).sum())),
        severe_months_spi6=('spi6', lambda x: int((x <= -1.5).sum())),
        drought_months_spei6=('spei6', lambda x: int((x <= -1).sum())),
        min_spi12=('spi12', 'min')).reset_index()
    annual.to_csv(f'{OUT}/{iso.lower()}_drought_annual_{SUMMARY0}_{SUMMARY1}.csv', index=False, float_format='%.3f')

    summ = []
    for u, g in w.groupby('unit_id'):
        runs = drought_runs(g.sort_values('date').spi6)
        summ.append({'unit_id': u, 'name': units.set_index('unit_id').name[u],
                     'mean_annual_precip_mm': g.groupby('year').precip_mm.sum().mean(),
                     'drought_months_spi6': int((g.spi6 <= -1).sum()),
                     'severe_months_spi6': int((g.spi6 <= -1.5).sum()),
                     'drought_months_spei6': int((g.spei6 <= -1).sum()),
                     'drought_events_spi6': len(runs),
                     'longest_event_months': max((len(r) for r in runs), default=0),
                     'worst_event_severity': min((sum(r) for r in runs), default=0.0),
                     'nearest_cell_fallback': u in fallback})
    pd.DataFrame(summ).to_csv(f'{OUT}/{iso.lower()}_drought_summary_{SUMMARY0}_{SUMMARY1}.csv', index=False, float_format='%.3f')
    base = m[(m.year >= CAL0) & (m.year <= CAL1)].spi6
    print(f'{iso}: {len(units)} units, {P.index.min():%Y-%m} to {P.index.max():%Y-%m}; '
          f'fallback cells for {len(fallback)} units {fallback[:6]}; '
          f'baseline SPI-6 mean {base.mean():.2f}, sd {base.std():.2f}; missing index values {int(m.spi6.isna().sum())}')
print('Done. Outputs in', OUT)
