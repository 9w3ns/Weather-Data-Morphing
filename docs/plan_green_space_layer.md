# Plan: green-space layer (coverage, access, per-capita, สวน15นาที)

**Status:** DONE 2026-07-22. All 5 built. Decisions: population = %×5.45M estimate;
สวน15นาที = CKAN (found the official CSV — no browser capture needed). Green tags
= broad, split park/vegetation. Access = nearest-park + 800 m + green_15min flag.
**Trigger:** UDDC "15-minute green city" scrollytelling (uddc.net/scrollytellingminsgreen).
That page is a *narrative*, not a dataset — no export. But the green data behind it
is pullable from OSM + BMA. User wants all four: coverage layer, per-site green
access, per-capita by district, and the สวน15นาที BMA plots.

**Why this matters here:** green space is both a UHI-mitigation lever and, via สวน15นาที,
the one public lead for *vacant* BMA land — the documented blind spot of the BMA land
layer (`docs/bma_land_sourcing_notes.md` §5.2). Kept as a parallel layer, like bma_land.

## Sources — what is actually pullable

| Source | Pullable? | Gives |
|---|---|---|
| **OSM green** (osmnx) | Yes — reliable backbone | Parks/gardens/forest/grass polygons, city-wide |
| **สวน15นาที** greener.bangkok.go.th | **Not cleanly** — 529 gardens load via JS, no static API/export | The BMA 15-min-park plots (incl. ~42 BMA-owned) |
| **data.bangkok.go.th** (CKAN) | Maybe — same portal as the school registry | Possible official park/green dataset |
| **tgu.onep.go.th** (Thai Green Urban DB, ONEP) | To investigate | Possibly authoritative green-space GIS |
| Population per district | Only `Population_Pct_BMA` (%) in `bangkok_uhi_data.csv` | Need an absolute basis (see decision 1) |

## Deliverables & method

### 1. Green coverage layer (backbone)
`data/fetch_green_space_osm.py` → `data/gis/bangkok_green_space.geojson` (EPSG:4326).
- OSM tags: `leisure=park|garden|nature_reserve|pitch|common`,
  `landuse=grass|forest|recreation_ground|village_green|meadow|cemetery?`,
  `natural=wood|scrub`. (Breadth = decision 2.)
- Clip to `bangkok_districts.geojson`; per feature: `green_id, green_type, name,
  district (centroid-in), area_sqm`. Dedup overlaps.
- Mirrors `fetch_bma_facilities.py` / `fetch_vacant_plots_osm.py` conventions.

### 2. Per-site green access
Extend the site attributes (small join script, or into `build_bma_land_layer.py`):
for each BMA site → `dist_to_nearest_green_m` (sjoin_nearest to the coverage layer)
and `green_area_within_800m_sqm` (area of green intersecting an 800 m buffer — 800 m
= UDDC's 15-min walk). Written into `bangkok_bma_land_scored.csv` + the geojson, so
`gh_bma_land.py` can surface/colour it like `dist_to_station_m`.

### 3. Per-capita green by district
`data/build_green_by_district.py` → `data/gis/bangkok_green_by_district.csv`:
`district, green_sqm, district_area_sqm, green_pct, population, green_sqm_per_capita`.
Benchmarks vs UDDC's **7.6** m²/capita city-wide and WHO **9**. Population basis =
decision 1.

### 4. สวน15นาที BMA plots (best-effort, uncertain)
Attempt, in order: (a) `data.bangkok.go.th` CKAN search for a 15-min-park / green
dataset; (b) `tgu.onep.go.th` for an ArcGIS/GeoJSON endpoint; (c) inspect the
greener.bangkok.go.th map's live data call (needs browser capture — the
`claude-in-chrome` skill, requires your Chrome + site permission). If any yields the
529 plots → `data/gis/bangkok_15min_parks.geojson`, flagged for the ~42 BMA-owned as
extra city-land leads. If none → documented as a manual/contact lead, not fabricated.

### 5. Grasshopper
`data/gis/gh_green_space.py` → green coverage curves in the shared local XY frame
(same pattern as `gh_landuse_zones.py` / `gh_bma_land.py`), so green overlays the
LCZ mesh, BMA sites, and satellite basemap with no registration.

## Open decisions (for review)

1. **Population basis for per-capita** — (a) `Population_Pct_BMA` × total registered
   BMA population (~5.45M, one documented assumption, fast) or (b) fetch absolute
   registered population per district from DOPA (more accurate, extra fetch).
2. **Green tag breadth** — parks/gardens only (what people use), or all vegetation
   landuse incl. forest/scrub/cemetery (matches "green cover" but inflates access).
3. **สวน15นาที effort** — CKAN/ONEP attempt only (fast, may miss), or also browser-
   capture the live 529-garden layer (more complete, needs Chrome permission).
4. **Access metric** — 800 m buffer + nearest-green distance as specified, or also a
   coarse "15-min-green: yes/no" flag per site (matches UDDC's 17% headline).

## Order of work
1 (OSM backbone) → 2 + 3 (both build on it) → 5 (GH) → 4 (สวน15นาที, parallel/uncertain).
Deliverable 1 is decision-independent and can start immediately.
