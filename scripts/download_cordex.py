"""Download CORDEX daily precipitation and temperature for the three study regions and reduce them to
province/district daily series as they arrive. Raw files are deleted once processed, so disk use stays small.

Run from the repository root (it reads the region layers in data/). Keep the Mac awake with caffeinate:

    caffeinate -i python scripts/download_cordex.py --test                  # 1 small request, ~2-5 min
    caffeinate -i python scripts/download_cordex.py --out "<grant folder>/CORDEX/units"
    # or, from the grant folder's CORDEX/ (finds POC_regions/ and units/ itself):
    caffeinate -i python download_cordex.py --phase E

Needs: the CDS API key in ~/.cdsapirc, the CORDEX licence accepted on the dataset's Download page,
and `pip install cdsapi` plus the repository requirements (xarray, netCDF4, geopandas).
Safe to stop and re-run: finished pieces are skipped. Failed requests are listed in <out>/failed.log
and retried on the next run.

What it fetches (dataset projections-cordex-domains-single-levels, daily means, 0.22 degree, r1i1p1,
cropped on the server to each region's box):
  South-East Asia domain -> Philippines;  South Asia domain -> Afghanistan and Bangladesh.
  12 GCM-driven runs: REMO2015 x (HadGEM2-ES, MPI-ESM-LR, NorESM1-M) in both domains;
                      RegCM4-7 x (HadGEM2-ES, MPI-ESM-MR, NorESM1-M) in South-East Asia (ICTP),
                      RegCM4-7 x (MIROC5, MPI-ESM-MR, NorESM1-M) in South Asia (ORNL).
  4 evaluation runs (ERA-Interim driven): REMO2015 and RegCM4-7 (ICTP) in both domains.
Phases, in the order they run (use --phase to limit):
  A  precipitation for the observed period: historical 1986-2005, RCP8.5 2006-2025, evaluation 1986-2016/17
  B  precipitation for the future: RCP2.6 and RCP8.5, 2041-2099
  C  2 m temperature for everything in A and B (for SPEI and heat)
  D  precipitation and temperature 1976-1985 (completes a 30-year model baseline, 1976-2005)
  E  precipitation and temperature 2026-2040, RCP2.6 and RCP8.5 (added Nov 2, 2026: fills the gap so the
     near-term window 2026-2045 can be computed); 144 requests
Output: <out>/<ISO>/<pr|tas>/<rcm>__<gcm>__<experiment>__<y0>-<y1>.csv.gz, one row per model day
(dates as written by the model calendar; HadGEM2-ES uses 360-day years), one column per unit, values in
mm/day (pr) or deg C (tas). Unit means are weighted by the exact overlap of each model cell with the unit
polygon, in an equal-area projection; a unit that overlaps no cell takes the nearest cell.
Units match the EM-DAT and ERA5-Land tables: 81 Philippine provinces (Davao Occidental folded into Davao
del Sur), 34 Afghan provinces, 64 Bangladesh districts.
CORDEX: cite the CORDEX initiative and each model group; data from the Copernicus Climate Data Store.
"""
import argparse, json, os, shutil, sys, tempfile, threading, time, traceback, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np, pandas as pd, xarray as xr, geopandas as gpd
import shapely

DATASET = 'projections-cordex-domains-single-levels'
EA = 6933  # equal-area CRS for overlap weights
REGIONS = {  # iso: (CDS domain, short name, [N, W, S, E] crop box, padded beyond the country)
    'PHL': ('south_east_asia', 'SEA', [21.5, 114.0, 4.0, 127.0]),
    'AFG': ('south_asia', 'WAS', [39.0, 60.0, 29.0, 75.5]),
    'BGD': ('south_asia', 'WAS', [27.0, 87.5, 20.0, 93.0]),
}
RUNS = {
    'SEA': [('gerics_remo2015', g) for g in ('mohc_hadgem2_es', 'mpi_m_mpi_esm_lr', 'ncc_noresm1_m')]
           + [('ictp_regcm4_7', g) for g in ('mohc_hadgem2_es', 'mpi_m_mpi_esm_mr', 'ncc_noresm1_m')],
    'WAS': [('gerics_remo2015', g) for g in ('mohc_hadgem2_es', 'mpi_m_mpi_esm_lr', 'ncc_noresm1_m')]
           + [('ornl_regcm4_7', g) for g in ('miroc_miroc5', 'mpi_m_mpi_esm_mr', 'ncc_noresm1_m')],
}
EVAL_END = {'gerics_remo2015': 2017, 'ictp_regcm4_7': 2016}
VARS = {'pr': 'mean_precipitation_flux', 'tas': '2m_air_temperature'}


def chunks(y0, y1, size=10):
    out, a = [], y0
    while a <= y1:
        b = min(a + size - 1, y1)
        out.append((a, b))
        a = b + 1
    return out


def build_jobs():
    jobs = []  # (phase, iso, var, rcm, gcm, experiment, y0, y1)
    for phase, var in (('A', 'pr'), ('C', 'tas')):
        for iso, (_, dom, _) in REGIONS.items():
            for rcm, gcm in RUNS[dom]:
                for a, b in chunks(1986, 2005):
                    jobs.append((phase, iso, var, rcm, gcm, 'historical', a, b))
                for a, b in chunks(2006, 2025):
                    jobs.append((phase, iso, var, rcm, gcm, 'rcp_8_5', a, b))
            for rcm, end in EVAL_END.items():
                for a, b in chunks(1986, end):
                    jobs.append((phase, iso, var, rcm, 'era_interim', 'evaluation', a, b))
    for phase, var in (('B', 'pr'), ('C', 'tas')):
        for iso, (_, dom, _) in REGIONS.items():
            for rcm, gcm in RUNS[dom]:
                for exp in ('rcp_2_6', 'rcp_8_5'):
                    for a, b in chunks(2041, 2099):
                        jobs.append((phase, iso, var, rcm, gcm, exp, a, b))
    for var in ('pr', 'tas'):
        for iso, (_, dom, _) in REGIONS.items():
            for rcm, gcm in RUNS[dom]:
                jobs.append(('D', iso, var, rcm, gcm, 'historical', 1976, 1985))
    for var in ('pr', 'tas'):
        for iso, (_, dom, _) in REGIONS.items():
            for rcm, gcm in RUNS[dom]:
                for exp in ('rcp_2_6', 'rcp_8_5'):
                    for a, b in chunks(2026, 2040):
                        jobs.append(('E', iso, var, rcm, gcm, exp, a, b))
    order = {'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4}
    return sorted(jobs, key=lambda j: order[j[0]])


def out_path(out, job):
    _, iso, var, rcm, gcm, exp, a, b = job
    return Path(out) / iso / var / f'{rcm}__{gcm}__{exp}__{a}-{b}.csv.gz'


# ---------- province / district polygons ----------
HERE = Path(__file__).resolve().parent


def _first(*paths):
    """The first path that exists: the repository layout, then the grant-folder layout (POC_regions/ beside CORDEX/)."""
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError('none of: ' + '; '.join(str(p) for p in paths) +
                            ' (pass --repo <repository root>, or run the copy in the grant folder CORDEX/)')


def load_units(iso, repo):
    reg = _first(Path(repo) / 'data' / 'processed' / 'regions' / 'poc_provinces.gpkg',
                 HERE.parent / 'POC_regions' / 'poc_provinces.gpkg')
    if iso == 'PHL':
        u = gpd.read_file(reg, layer='phl_provinces')[['unit_id', 'name', 'geometry']]
        u.loc[u.unit_id == 'PH-DVO', ['unit_id', 'name']] = ['PH-DAS', 'Davao del Sur']
        u = u.dissolve(by='unit_id', aggfunc='first').reset_index()
    elif iso == 'AFG':
        u = gpd.read_file(reg, layer='afg_provinces')[['unit_id', 'name', 'geometry']]
    else:
        u = gpd.read_file(_first(Path(repo) / 'data' / 'external' / 'geoboundaries' / 'geoBoundaries-BGD-ADM2_simplified.geojson',
                                 HERE.parent / 'POC_regions' / 'source' / 'geoBoundaries-BGD-ADM2_simplified.geojson'))
        u = u.rename(columns={'shapeName': 'name'}).assign(unit_id=lambda d: d['name'])[['unit_id', 'name', 'geometry']]
    return u.to_crs(4326)


# ---------- model grid -> unit weights ----------
def _corners(c):
    """Cell-corner array (ny+1, nx+1) from 2-D cell centres, by averaging neighbours on an extrapolated grid."""
    p = np.pad(c, 1, mode='edge').astype(float)
    p[0, :] = 2 * p[1, :] - p[2, :]
    p[-1, :] = 2 * p[-2, :] - p[-3, :]
    p[:, 0] = 2 * p[:, 1] - p[:, 2]
    p[:, -1] = 2 * p[:, -2] - p[:, -3]
    return 0.25 * (p[:-1, :-1] + p[1:, :-1] + p[:-1, 1:] + p[1:, 1:])


def unit_weights(lat2, lon2, units, box):
    N, W, S, E = box
    ny, nx = lat2.shape
    cla, clo = _corners(lat2), _corners(lon2)
    ring = np.stack([np.stack([clo[:-1, :-1], cla[:-1, :-1]], -1), np.stack([clo[:-1, 1:], cla[:-1, 1:]], -1),
                     np.stack([clo[1:, 1:], cla[1:, 1:]], -1), np.stack([clo[1:, :-1], cla[1:, :-1]], -1)], axis=2)
    flat = np.arange(ny * nx)
    keep = ((lat2 >= S - 1) & (lat2 <= N + 1) & (lon2 >= W - 1) & (lon2 <= E + 1)).ravel()
    polys = shapely.polygons(ring.reshape(ny * nx, 4, 2)[keep])
    cells = gpd.GeoDataFrame({'k': flat[keep]}, geometry=polys, crs=4326).to_crs(EA)
    ov = gpd.overlay(units[['unit_id', 'geometry']].to_crs(EA), cells, how='intersection', keep_geom_type=True)
    ov['w'] = ov.area
    Wt, fallback = {}, []
    for u, g in ov.groupby('unit_id'):
        Wt[u] = (g.k.values.astype(int), g.w.values)
    for _, r in units.iterrows():
        if r.unit_id not in Wt or Wt[r.unit_id][1].sum() == 0:
            p = r.geometry.representative_point()
            d = (lat2.ravel() - p.y) ** 2 + ((lon2.ravel() - p.x) * np.cos(np.radians(p.y))) ** 2
            Wt[r.unit_id] = (np.array([int(np.argmin(d))]), np.array([1.0]))
            fallback.append(r.unit_id)
    return Wt, fallback


# ---------- reading one downloaded piece ----------
def open_nc(path):
    try:
        return xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    except (AttributeError, TypeError):
        return xr.open_dataset(path, use_cftime=True)


def latlon(ds, v):
    names = {n.lower(): n for n in list(ds.coords) + list(ds.data_vars)}
    la = ds[names.get('lat') or names.get('latitude')]
    lo = ds[names.get('lon') or names.get('longitude')]
    if la.ndim == 1 and lo.ndim == 1:
        lo2, la2 = np.meshgrid(lo.values, la.values)
    else:
        la2, lo2 = la.values, lo.values
    lo2 = np.where(lo2 > 180, lo2 - 360, lo2)
    if la2.shape != tuple(ds[v].shape[-2:]):
        raise ValueError(f'lat/lon shape {la2.shape} does not match data {ds[v].shape}')
    return la2, lo2


def to_units(path, var, iso, ctx):
    ds = open_nc(path)
    v = var if var in ds.data_vars else [n for n in ds.data_vars if ds[n].ndim >= 3][0]
    da = ds[v]
    la2, lo2 = latlon(ds, v)
    key = (iso, la2.shape, float(np.round(la2.sum(), 3)), float(np.round(lo2.sum(), 3)))
    with ctx['lock']:
        if key not in ctx['weights']:
            Wt, fb = unit_weights(la2, lo2, ctx['units'][iso], REGIONS[iso][2])
            ctx['weights'][key] = Wt
            info = {'grid_shape': list(la2.shape), 'lat_range': [float(la2.min()), float(la2.max())],
                    'lon_range': [float(lo2.min()), float(lo2.max())], 'fallback_units': fb,
                    'cells_per_unit_median': float(np.median([len(w[0]) for w in Wt.values()]))}
            ctx['grid_info'].setdefault(iso, []).append(info)
    Wt = ctx['weights'][key]
    arr = da.values.reshape(da.shape[0], -1).astype('float64')
    units = str(da.attrs.get('units', ''))
    if var == 'pr' and ('s-1' in units or 's**-1' in units or '/s' in units):
        arr = arr * 86400.0                      # kg m-2 s-1 -> mm/day
    if var == 'tas' and units.strip().upper() in ('K', 'KELVIN'):
        arr = arr - 273.15                       # K -> deg C
    cols = {}
    for u, (idx, w) in Wt.items():
        vals = arr[:, idx]
        ok = ~np.isnan(vals)
        cols[u] = np.where(ok.any(1), np.nansum(vals * w, 1) / np.maximum((ok * w).sum(1), 1e-12), np.nan)
    tname = [d for d in da.dims if 'time' in d.lower()][0]
    dates = [t.strftime('%Y-%m-%d') if hasattr(t, 'strftime') else str(pd.Timestamp(t).date()) for t in ds[tname].values]
    ds.close()
    return pd.DataFrame(cols, index=pd.Index(dates, name='date')), units


def run_job(job, out, tmp_root, ctx, test=False):
    phase, iso, var, rcm, gcm, exp, a, b = job
    target = out_path(out, job)
    if target.exists() and target.stat().st_size > 0:
        return 'skipped', job
    dom, _, box = REGIONS[iso]
    req = {
        'domain': dom, 'experiment': exp, 'horizontal_resolution': '0_22_degree_x_0_22_degree',
        'temporal_resolution': 'daily_mean', 'variable': VARS[var], 'gcm_model': gcm, 'rcm_model': rcm,
        'ensemble_member': 'r1i1p1', 'year': [str(y) for y in range(a, b + 1)],
        'month': [f'{m:02d}' for m in range(1, 13)], 'area': box,
    }
    import cdsapi
    work = Path(tempfile.mkdtemp(prefix='cordex_', dir=tmp_root))
    try:
        dl = work / 'download.bin'
        cdsapi.Client(quiet=True, progress=False).retrieve(DATASET, req, str(dl))
        files = []
        if zipfile.is_zipfile(dl):
            with zipfile.ZipFile(dl) as z:
                z.extractall(work / 'x')
            files = sorted(p for p in (work / 'x').rglob('*.nc'))
        else:
            files = [dl]
        if not files:
            raise RuntimeError('no netCDF file in the download')
        parts, units = [], ''
        for f in files:
            df, units = to_units(f, var, iso, ctx)
            parts.append(df)
        df = pd.concat(parts).sort_index()
        df = df[~df.index.duplicated()]
        target.parent.mkdir(parents=True, exist_ok=True)
        tmpfile = target.with_suffix('.part')
        df.round(4).to_csv(tmpfile, compression='gzip')
        os.replace(tmpfile, target)
        mb = dl.stat().st_size / 1e6
        if test:
            print(f'  request: {json.dumps({k: v for k, v in req.items() if k not in ("year", "month")})}')
            print(f'  downloaded {mb:.1f} MB, {len(files)} file(s); source units "{units}"')
            print(f'  grid info: {json.dumps(ctx["grid_info"].get(iso, [])[-1])}')
            print(f'  {df.shape[0]} days x {df.shape[1]} units; first unit sample:', df.iloc[:5, 0].round(2).tolist())
        return 'done', job, mb
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=None, help='output folder (default: units/ beside this script if it exists, '
                    'as in the grant folder CORDEX/; else data/raw/cordex_units)')
    ap.add_argument('--repo', default='.', help='repository root holding data/processed/regions')
    ap.add_argument('--phase', default='ABCDE', help='phases to run, e.g. A, AB or E (default all, in order)')
    ap.add_argument('--workers', type=int, default=4, help='parallel CDS requests (CDS queues extra ones)')
    ap.add_argument('--tmp', default=None, help='scratch folder for downloads (default: system temp, outside Google Drive)')
    ap.add_argument('--test', action='store_true', help='run one small request and print what came back')
    ap.add_argument('--list', action='store_true', help='print the job counts and exit')
    args = ap.parse_args()
    if args.out is None:
        args.out = str(HERE / 'units') if (HERE / 'units').is_dir() else 'data/raw/cordex_units'
    print(f'Output folder: {args.out}')

    jobs = [j for j in build_jobs() if j[0] in args.phase.upper()]
    if args.list:
        print(pd.Series([j[0] for j in jobs]).value_counts().sort_index().to_string())
        print(f'{len(jobs)} requests in total')
        return
    ctx = {'lock': threading.Lock(), 'weights': {}, 'grid_info': {},
           'units': {iso: load_units(iso, args.repo) for iso in REGIONS}}
    for iso, u in ctx['units'].items():
        print(f'{iso}: {len(u)} units')
    tmp_root = args.tmp or tempfile.gettempdir()
    out = Path(args.out)

    if args.test:
        out = out / '_test'
        job = ('A', 'PHL', 'pr', 'gerics_remo2015', 'mohc_hadgem2_es', 'historical', 2005, 2005)
        t0 = time.time()
        print('Test request: Philippines, REMO2015 x HadGEM2-ES, historical 2005, precipitation ...')
        res = run_job(job, out, tmp_root, ctx, test=True)
        print(f'Test {res[0]} in {time.time() - t0:.0f} s. Output: {out_path(out, job)}')
        return

    out.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not (out_path(out, j).exists() and out_path(out, j).stat().st_size > 0)]
    print(f'{len(jobs)} requests in phases {args.phase.upper()}; {len(jobs) - len(todo)} already done; {len(todo)} to go.')
    t0, done, failed, mb_total = time.time(), 0, 0, 0.0
    log = open(out / 'failed.log', 'a')
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_job, j, out, tmp_root, ctx): j for j in todo}
        for f in as_completed(futs):
            j = futs[f]
            try:
                res = f.result()
                done += 1
                mb_total += res[2] if len(res) > 2 else 0
            except Exception as e:
                failed += 1
                log.write(f'{time.strftime("%Y-%m-%d %H:%M")}\t{j}\t{type(e).__name__}: {e}\n')
                log.flush()
                print(f'  FAILED {j}: {type(e).__name__}: {str(e)[:200]}')
            n = done + failed
            el = time.time() - t0
            eta = el / n * (len(todo) - n) / 3600 if n else 0
            print(f'[{n}/{len(todo)}] {j[0]} {j[1]} {j[2]} {j[3]} {j[4]} {j[5]} {j[6]}-{j[7]} | '
                  f'{done} ok, {failed} failed, {mb_total:.0f} MB, ~{eta:.1f} h left', flush=True)
    gi = out / 'grid_info.json'
    old = json.load(open(gi)) if gi.exists() else {}
    old.update(ctx['grid_info'])   # keep the earlier phases' entries
    json.dump(old, open(gi, 'w'), indent=1)
    print(f'Finished: {done} ok, {failed} failed. Re-run the same command to retry failures.')


if __name__ == '__main__':
    main()
