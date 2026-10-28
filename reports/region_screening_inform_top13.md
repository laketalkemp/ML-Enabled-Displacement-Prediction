# Second-region screening: INFORM 2026 top 13

Oct 27, 2026 · LaKeta Kemp

The 13 countries screened are South Sudan, Yemen, Somalia, DR Congo, Chad, Sudan, Syria, Afghanistan, Central African Republic, Niger, Haiti, Mozambique and Myanmar. The first 12 hold INFORM Risk 2026 ranks 1–13 (ties share a rank); Myanmar is rank 17. Each was checked against the plan's five selection criteria, plus two extra tests: contrast with the Philippines' hazard archetype, and CORDEX coverage. Most of these countries have too few admin-1 units on their own, so neighbouring countries were grouped where that makes geographic sense.

## Recommendation

1. **Afghanistan** is the strongest second region on this list. It is the only country here with 30 or more admin-1 units on its own (34 provinces), and Natural Earth's provinces are current apart from two mislabels. Its drought, river-flood and earthquake profile contrasts clearly with the Philippines' cyclone and coastal-flood profile. It has IPC coverage and a large disaster-displacement signal for validation. CORDEX South Asia includes the same three REMO2015 runs planned for the Philippines.
2. **Somalia and Yemen (Gulf of Aden)** is the best option if you want all three of the plan's hazards (drought, cyclone, flood) plus the drought-to-famine pathway in one region. The costs are a sea-separated region, two conflict-affected data systems, and higher INFORM missingness.
3. **Niger, Chad and Sudan (Central Sahel)** works as a drought and flood region with enough units. Its admin-1 units vary enormously in size, Sudan's war disrupts reporting, and 2025 disaster displacement was low, which weakens validation.

Myanmar, Haiti, Syria and DR Congo don't work as stand-alone second regions (see below).

## INFORM 2026 hazard profiles

Scores are 0–10, from `INFORM_Risk_2026_v072.xlsx`.

| Country | Rank | Risk | River flood | Tropical cyclone | Coastal flood | Drought | Earthquake | Current conflict | Vulnerability | Coping capacity (lack) | Missing indicators |
|---|---|---|---|---|---|---|---|---|---|---|---|
| South Sudan | 1 | 8.5 | 7.7 | 0 | 0 | 3.7 | 2.7 | 7.8 | 8.9 | 9.2 | 16% |
| Yemen | 2 | 8.1 | 6.0 | 3.5 | 4.8 | 4.6 | 1.7 | 8.7 | 8.4 | 8.1 | 12% |
| Somalia | 2 | 8.1 | 7.8 | 1.8 | 5.9 | **10** | 1.3 | 8.5 | 9.4 | 7.1 | 12% |
| DR Congo | 4 | 8.0 | 7.0 | 0 | 1.0 | 2.3 | 4.2 | 10 | 7.7 | 8.1 | 2% |
| Chad | 5 | 7.9 | 8.1 | 0 | 0 | 5.5 | 0.1 | 6.3 | 8.2 | 8.6 | 4% |
| Sudan | 6 | 7.8 | 8.7 | 0 | 0.8 | 5.7 | 0.1 | 10 | 7.5 | 7.7 | 0% |
| Syria | 6 | 7.8 | 6.3 | 0 | 2.1 | 8.6 | 7.2 | 10 | 7.8 | 7.0 | 16% |
| Afghanistan | 6 | 7.8 | 7.3 | 0 | 0 | 8.7 | 8.8 | 7.1 | 8.3 | 7.4 | 8% |
| Central African Rep. | 9 | 7.6 | 6.0 | 0 | 0 | 3.0 | 0.1 | 6.5 | 8.0 | 8.7 | 6% |
| Niger | 10 | 7.5 | 6.6 | 0 | 0 | 6.3 | 0.1 | 8.4 | 7.4 | 7.7 | 2% |
| Haiti | 10 | 7.5 | 4.7 | **8.9** | 4.5 | 3.7 | 8.4 | 6.7 | 8.3 | 7.3 | 8% |
| Mozambique | 13 | 7.1 | 6.1 | 2.7 | 5.6 | 6.7 | 3.4 | 4.3 | 7.4 | 6.7 | 0% |
| Myanmar | 17 | 6.9 | 8.8 | 5.8 | **8.0** | 0.9 | 8.2 | 7.7 | 6.6 | 6.1 | 6% |
| *Philippines (reference)* | 46 | 5.3 | 6.7 | **9.2** | **8.9** | 3.5 | 9.7 | 4.7 | 4.9 | 3.7 | 6% |

For reference, Ethiopia is rank 16, Palestine 21 and Kenya 25.

**Takeaways**
- Only Haiti and Myanmar share the Philippines' cyclone and coastal-flood archetype, so they would add the least contrast.
- The drought-dominant countries are Somalia, Afghanistan and Syria (8.6–10), with Niger, Sudan, Chad and Mozambique in the mid-range (5.5–6.7).
- Somalia, Yemen and Mozambique combine substantial drought (4.6–10) with cyclone and coastal-flood exposure. Haiti and Myanmar have all three hazards too, but are weighted toward cyclones.
- South Sudan, Syria, Yemen and Somalia have the most imputed or missing INFORM indicators (12–16%). They would put the most weight on the imputation fix in the plan.

## Admin-1 units

Counts are from Natural Earth 1:10m. Current official counts are approximate; verify them against OCHA COD-AB.

| Country | Natural Earth | Current official | Natural Earth issue |
|---|---|---|---|
| Afghanistan | 34 | 34 | Panjshir is labeled "Parwan" and Daykundi is labeled "Uruzgan"; the `gn_name` field has the correct names |
| Chad | 22 | 23 | One province missing |
| Yemen | 21 | 22 | Socotra missing |
| Sudan | 17 | 18 | West Kordofan missing |
| Central African Rep. | 17 | ~20 prefectures + Bangui | Pre-2020 prefectures |
| Syria | 15 | 14 | Includes a UNDOF zone as a 15th unit |
| Myanmar | 14 | 15 | Naypyidaw missing |
| Somalia | 13 (+1 Somaliland) | 18 | Somaliland split out |
| DR Congo | 11 | 26 | Pre-2015 provinces |
| Mozambique | 11 | 11 | Current |
| South Sudan | 10 | 10 + 3 administrative areas | Areas missing |
| Haiti | 10 | 10 | Current |
| Niger | 8 | 8 | Current |

## Candidate regions vs. the selection criteria

| Region | Admin-1 (Natural Earth / current) | Plan hazards present | Contrast with Philippines | IDMC 2025 (conflict / disaster displacements) | Food-security data | CORDEX at 0.22° | Main drawbacks |
|---|---|---|---|---|---|---|---|
| **Afghanistan** | 34 / 34 | Drought, flood (plus earthquake) | Strong | 168k / 253k; 2.6M disaster IDPs at end of 2025 | IPC | South Asia domain: REMO2015 × 3 GCMs (same as the Philippines) + RegCM4-7 × 3 | One national vulnerability value for the whole region; data access since 2021; no coast |
| **Somalia + Yemen** | 35 / 40 | Drought, cyclone, coastal and river flood | Partial (both have cyclones) | Somalia 214k / 335k; Yemen 57k / 264k | IPC (both) | Africa domain: 6-run matrix | Sea between them, so distance-band weights; two conflict-affected data systems; Somaliland and Yemen's split authorities; 12% missing INFORM indicators |
| **Niger + Chad + Sudan** | 47 / 49 | Drought, river flood | Strong | Sudan 1.73M / 30k; Chad 36k / 89k; Niger 166k / 1.9k | Cadre Harmonisé (Niger, Chad) + IPC (Sudan) | Africa domain: 6-run matrix | Units range from 119 to 622,000 km²; war disrupts reporting in Sudan; low disaster displacement in 2025 |
| Mozambique + Malawi + Madagascar | 61 | All three | Partial (cyclones) | Mozambique 339k / 669k | IPC | Africa domain: 6-run matrix | Only Mozambique is in the top 13 |
| Sudan + South Sudan + Chad + CAR | 66 / ~72 | Mostly river flood | Moderate | Driven mostly by conflict | IPC + Cadre Harmonisé | Africa domain | A conflict story more than a hazard one |
| Myanmar (+ Bangladesh) | 14 (21) | Cyclone, flood | Weak | 573k / 406k | No IPC (verify) | South Asia domain | Too few units; same archetype as the Philippines; data limited since 2021 |
| Haiti (+ Dominican Republic) | 10 (42) | Cyclone, flood, earthquake | Weak | 977k / 9.5k | IPC (Haiti) | Central America domain: only 3 runs | Same archetype as the Philippines; one island shared with a much less vulnerable neighbour |
| Syria | 15 | Drought, earthquake | Strong | 531k (category not given) | No IPC (verify) | Africa domain | Too few units; 16% missing indicators |
| DR Congo (+ CAR, South Sudan) | 38 with outdated DRC boundaries | Flood | Weak | DRC 9.7M / 313k | IPC | Africa domain | Outdated boundaries; conflict-dominated; EM-DAT likely sparse |

## Notes

- **CORDEX domain coverage** was tested on the Natural Earth polygons, excluding a 10-cell relaxation zone.
  - The Africa domain fully covers 10 of the 13 countries, including Yemen and Syria.
  - Afghanistan needs the South Asia or Central Asia domain.
  - Myanmar needs the South Asia domain, because only 85% of it falls inside the South-East Asia domain.
  - Haiti needs the Central America domain.
- **EM-DAT density** (criterion 2) still needs to be checked in your export: events since 2000 by hazard type for each candidate, and the share with admin units filled in. Drought events are often coded at the national level, which limits province-level drought signatures everywhere.
- **Afghanistan is a single country**, so every province shares one national vulnerability score. All within-region variation would come from hazard exposure. This is the plan's "subnational hazard, national vulnerability" setup, and it should be labeled that way. Somalia + Yemen and the Sahel option include two or three national values.

## Decision needed

Choose one:

- **Afghanistan**
- **Somalia + Yemen**
- **Niger + Chad + Sudan**
- **Keep the Horn of Africa**

Palestine remains an option as a case study, whichever is chosen.

**Sources:** INFORM Risk 2026 v0.7.2 (grant folder); Natural Earth v5.1.2; IDMC GRID 2026 summary; Copernicus CDS CORDEX catalogue (queried Oct 27, 2026); CORDEX domain definitions via py-cordex.
