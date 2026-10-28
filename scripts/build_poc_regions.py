"""Build proof-of-concept province layers (python scripts/build_poc_regions.py) for the Philippines and Afghanistan.

Philippines: geoBoundaries gbOpen PHL ADM2 (provinces; source NAMRIA/PSA via OCHA, CC BY 3.0 IGO),
  dissolved to 82 units (NCR districts -> Metro Manila, City of Isabela -> Basilan,
  Cotabato City -> Maguindanao). Natural Earth 1:10m lacks Dinagat Islands and Davao Occidental.
Afghanistan: Natural Earth 1:10m admin-1 (public domain), with Panjshir and Daykundi relabeled
  (Natural Earth names them Parwan and Uruzgan). Crosswalked to geoBoundaries for spelling aliases.
"""
import os
from pathlib import Path
os.chdir(Path(__file__).resolve().parents[1])   # run from anywhere; paths below are repo-relative
import geopandas as gpd, pandas as pd
NE = 'zip://data/raw/natural_earth/ne_10m_admin_1_states_provinces.zip'   # scripts/fetch_natural_earth.py
GB = 'data/external/geoboundaries'
OUT = 'data/processed/regions'
EA = 6933  # equal-area CRS

a1 = gpd.read_file(NE)

def best_overlap(src, src_key, tgt, tgt_cols):
    """For each src unit, the tgt unit holding the largest share of its area."""
    s, t = src.to_crs(EA), tgt.to_crs(EA)
    s['_a'] = s.area
    ov = gpd.overlay(s[[src_key, '_a', 'geometry']], t[tgt_cols + ['geometry']], how='intersection', keep_geom_type=True)
    ov['share'] = (ov.area / ov._a).round(3)
    ov = ov.sort_values('share', ascending=False)
    top = ov.groupby(src_key).head(1).set_index(src_key)
    others = ov.groupby(src_key).apply(lambda d: '; '.join(f"{r[tgt_cols[1]]} ({r.share:.0%})" for _, r in d.iloc[1:].iterrows() if r.share >= 0.05), include_groups=False)
    return top[tgt_cols + ['share']].join(others.rename('other_overlaps'))

# ---------------- Afghanistan ----------------
afg = a1[a1.adm0_a3 == 'AFG'][['adm1_code', 'name', 'iso_3166_2', 'code_hasc', 'gn_name', 'geometry']].copy()
afg['label_fixed'] = ''
for gn, nm, iso in [('Panjshir', 'Panjshir', 'AF-PAN'), ('Wilayat-e Daykundi', 'Daykundi', 'AF-DAY')]:
    m = afg.gn_name == gn; assert m.sum() == 1
    afg.loc[m, 'label_fixed'] = f"NE name '{afg.loc[m, 'name'].iat[0]}', ISO '{afg.loc[m, 'iso_3166_2'].iat[0]}'"
    afg.loc[m, ['name', 'iso_3166_2']] = [nm, iso]
assert len(afg) == 34 and afg.iso_3166_2.is_unique
gb_afg = gpd.read_file(f'{GB}/geoBoundaries-AFG-ADM1_simplified.geojson')
m = best_overlap(afg, 'iso_3166_2', gb_afg, ['shapeID', 'shapeName'])
afg = afg.merge(m.rename(columns={'shapeID': 'gb_shapeID', 'shapeName': 'gb_name', 'share': 'gb_overlap'}), left_on='iso_3166_2', right_index=True)
afg['aliases'] = afg.apply(lambda r: '' if r['name'] == r.gb_name else r.gb_name, axis=1)
afg = afg.rename(columns={'iso_3166_2': 'unit_id', 'adm1_code': 'ne_adm1_code', 'code_hasc': 'hasc'})
afg['geometry_source'] = 'Natural Earth 1:10m v5.1.2'
afg_cols = ['unit_id', 'name', 'aliases', 'hasc', 'ne_adm1_code', 'gb_shapeID', 'gb_overlap', 'other_overlaps', 'label_fixed', 'geometry_source']

# ---------------- Philippines ----------------
gb_phl = gpd.read_file(f'{GB}/geoBoundaries-PHL-ADM2_simplified.geojson')
merge_map = {'NCR, City of Manila, First District': 'Metro Manila', 'NCR, Second District': 'Metro Manila',
             'NCR, Third District': 'Metro Manila', 'NCR, Fourth District': 'Metro Manila',
             'City of Isabela': 'Basilan', 'Cotabato City': 'Maguindanao'}
gb_phl['name'] = gb_phl.shapeName.replace(merge_map)
phl = gb_phl.dissolve(by='name', aggfunc={'shapeID': lambda s: ';'.join(sorted(s)), 'shapeName': lambda s: '; '.join(sorted(s))}).reset_index()
phl = phl.rename(columns={'shapeID': 'gb_shapeIDs', 'shapeName': 'gb_names_merged'})
assert len(phl) == 82, len(phl)
ne_phl = a1[a1.adm0_a3 == 'PHL'][['iso_3166_2', 'name', 'type_en', 'geometry']]
ne_prov = ne_phl[ne_phl.type_en == 'Province'].rename(columns={'iso_3166_2': 'ne_iso', 'name': 'ne_nm'})  # provinces only
m = best_overlap(phl, 'name', ne_prov, ['ne_iso', 'ne_nm'])
m.columns = ['ne_iso_3166_2', 'ne_name', 'ne_overlap', 'ne_other_overlaps']
phl = phl.merge(m, left_on='name', right_index=True, how='left')
phl.loc[phl.name == 'Metro Manila', ['ne_iso_3166_2', 'ne_name', 'ne_overlap', 'ne_other_overlaps']] = [None, 'NCR cities (17 units)', None, None]
# ISO 3166-2 unit IDs: take the Natural Earth province code, override where NE has no matching province
override = {'Metro Manila': 'PH-00', 'Dinagat Islands': 'PH-DIN', 'Davao Occidental': 'PH-DVO',
            'Davao del Sur': 'PH-DAS', 'Compostela Valley': 'PH-COM'}
phl['unit_id'] = phl.name.map(override).fillna(phl.ne_iso_3166_2)
phl['notes'] = ''
notes = {'Compostela Valley': 'Renamed Davao de Oro (2019); keep old name to match EM-DAT/GADM, alias added',
         'Maguindanao': 'Split into Maguindanao del Norte/del Sur (2022); kept whole for a consistent 2000-2025 series; includes Cotabato City',
         'Metro Manila': 'Dissolved from four NCR districts; ISO code is the NCR region code',
         'Basilan': 'Includes City of Isabela',
         'Dinagat Islands': 'Created 2006; missing from Natural Earth (inside Surigao del Norte there)',
         'Davao Occidental': 'Created 2013; missing from Natural Earth (inside Davao del Sur there)'}
phl['notes'] = phl.name.map(notes).fillna('')
phl['aliases'] = phl.name.map({'Compostela Valley': 'Davao de Oro', 'Occidental Mindoro': 'Mindoro Occidental',
                               'Oriental Mindoro': 'Mindoro Oriental', 'Metro Manila': 'National Capital Region; NCR'}).fillna('')
phl['geometry_source'] = 'geoBoundaries gbOpen PHL ADM2 (NAMRIA/PSA via OCHA), CC BY 3.0 IGO'
dups = phl[phl.unit_id.duplicated(keep=False)]
print('PHL duplicate unit_ids:'); print(dups[['name', 'unit_id', 'ne_name', 'ne_overlap']].to_string(index=False))
phl_cols = ['unit_id', 'name', 'aliases', 'ne_iso_3166_2', 'ne_name', 'ne_overlap', 'ne_other_overlaps', 'gb_shapeIDs', 'gb_names_merged', 'notes', 'geometry_source']

# ---------------- write ----------------
gpkg = f'{OUT}/poc_provinces.gpkg'
gpd.GeoDataFrame(phl[phl_cols + ['geometry']], crs=phl.crs).to_file(gpkg, layer='phl_provinces', driver='GPKG')
gpd.GeoDataFrame(afg[afg_cols + ['geometry']], crs=afg.crs).to_file(gpkg, layer='afg_provinces', driver='GPKG')
phl[phl_cols].sort_values('unit_id').to_csv(f'{OUT}/phl_province_crosswalk.csv', index=False)
afg[afg_cols].sort_values('unit_id').to_csv(f'{OUT}/afg_province_crosswalk.csv', index=False)
print(f'PHL {len(phl)} units, unique ids: {phl.unit_id.is_unique}; AFG {len(afg)} units, unique ids: {afg.unit_id.is_unique}')
print('PHL low NE overlap (<0.8):'); print(phl[phl.ne_overlap < 0.8][['name', 'unit_id', 'ne_name', 'ne_overlap', 'ne_other_overlaps']].to_string(index=False))
print('AFG with aliases or low overlap:'); print(afg[(afg.aliases != '') | (afg.gb_overlap < 0.8)][['unit_id', 'name', 'aliases', 'gb_overlap', 'other_overlaps']].to_string(index=False))
