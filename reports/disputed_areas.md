# Disputed areas: how the maps show them

Policy confirmed by LaKeta Kemp on November 12, 2026, with the Abyei Area added on November 16. It applies to every
map on the dashboard and in project documents. The code is in `src/hvd/viz.py`; the place keys and names are in the
country crosswalk (`reports/country_crosswalk.md`).

## The rules

1. **De facto boundaries.** Country shapes are Natural Earth's default 1:50m admin-0 layer (v5.1.2), which draws the
   boundaries as they are administered on the ground. Each area is shaded with the score of the unit Natural Earth
   places it in.
2. **A hatched overlay** marks every area in Natural Earth's breakaway and disputed areas layer, so a reader sees that
   its status is contested whatever its shading.
3. **No sovereignty attributes.** Hover text names a disputed area neutrally and says only that it is disputed. It
   does not say who administers or claims it, although Natural Earth records both.
4. **A UN-style disclaimer** sits under every map:

   > Boundaries and names shown and the designations used on this map do not imply endorsement or acceptance by the
   > authors or UC San Diego. Hatched areas are disputed or of undetermined status; their shading follows Natural
   > Earth's de facto boundaries. References to Kosovo are in the context of UN Security Council resolution 1244
   > (1999). The final status of the Abyei Area is not yet determined, and it is attributed to neither Sudan nor South
   > Sudan.

## Exceptions to the de facto default

- **Abyei Area** (LaKeta, Nov 16). Natural Earth draws it inside Sudan. The map cuts it out and draws it on its own,
  gray and hatched, attributed to neither Sudan nor South Sudan. It matters to the humanitarian crisis between the two
  countries: IDMC records displacement there. It has no INFORM score, so it stays outside the country analyses.
- **Somaliland** (Nov 16). Natural Earth draws it as its own unit. INFORM, EM-DAT and IDMC count it within Somalia, so
  the map shades it with Somalia's score, hatched. Its name on the map is "Somaliland (Somalia)".

## The hatched areas

From Natural Earth 5.1.2's breakaway and disputed areas layer. Names are neutral; the layer's own names are used where
they are already geographic.

| Area | Shaded as (Natural Earth de facto) |
|---|---|
| Abyei Area | Own unit, no score (exception above) |
| Abkhazia; South Ossetia | Georgia |
| Aksai Chin; Demchok; Shaksam Valley | China |
| Arunachal Pradesh; Jammu and Kashmir; Junagadh and Manavadar; Bara Hotii, Samdu and Tirpani Valleys | India |
| Courantyne Headwaters | Guyana |
| Crimea; Kuril Islands | Russian Federation |
| Donetsk area; Luhansk area | Ukraine |
| Gilgit-Baltistan | Pakistan |
| Golan | Israel |
| Ilemi Triangle | Kenya |
| Lawa Headwaters | France |
| Northern Cyprus | Own unit, no score |
| Sabah (North Borneo) | Malaysia |
| Siachen Glacier | Own unit, no score |
| Somaliland | Somalia's score (exception above) |
| Transnistrian region | Republic of Moldova |
| Western Sahara | Partly Morocco, partly its own unit (no score) |

**Left out:** Nagorno-Karabakh (Natural Earth's "Artsakh"). The breakaway entity dissolved on January 1, 2024, and
the area is under Azerbaijan's control; Natural Earth 5.1.2 predates this.

## Open questions for LaKeta

Natural Earth's disputed layer does not include these, so they are not hatched now:

- **Kosovo (UNSCR 1244)**: its own unit, no score, with the resolution 1244 note in the hover and the disclaimer.
- **State of Palestine**: scored by INFORM and shaded with its score.
- **Taiwan Province of China**: its own unit, no score.
- **Falkland Islands (Malvinas)** and **British Indian Ocean Territory**: their own units, no score.

Hatching any of them would be a project decision rather than Natural Earth's.
