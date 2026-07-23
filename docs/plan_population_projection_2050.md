# Plan: BMA population projection to 2050 (registered + functional, per-district + city)

**Status:** proposed, awaiting review. Nothing coded yet.
**Ask:** project Bangkok (BMA) population to 2050, using births/demographic data.
**Decisions locked:** base = **both** registered (spine) + functional/de-facto
(uplift band); method = **adopt official national projection + Bangkok share**;
granularity = **city total + per-district (50)**.

## 0. The demographic reality this must respect

A "birth-rate projection" of Bangkok points **down and older**, not up:
- **Thailand's population has peaked (~2020) and is declining;** TFR ~1.3 (replacement 2.1).
- **Bangkok's TFR is among the world's lowest (~0.8-1.0)**, and its **registered
  population (~5.45M) has been slowly falling** for years (deregistration to suburbs).
- The **growth / demand** story for Bangkok is **functional (daytime/de-facto)
  population** — migration + urbanisation, ~8-10M actual users — which registered
  statistics do not capture. Modelling that gap honestly is the point of "both".

Implication: the interesting 2050 findings are **aging** (median age, %65+, dependency
ratio), **inner-district decline vs fringe growth**, and the **registered-vs-functional
gap** — not a single headline growth number.

## 1. Data sources

| Layer | Source | Fetchable? |
|---|---|---|
| Registered pop per district, annual series | **DOPA** `stat.bora.dopa.go.th` (สถิติทะเบียนราษฎร) | **Yes — series** |
| Thailand projection to 2100, with age-sex | **UN WPP 2024** `population.un.org/wpp` (CSV/API) | **Yes — spine** |
| Official Thai projection to ~2040 | **NESDC** (สศช.) population projection report | Yes — cross-check |
| De-facto / present population benchmark | **NSO census** 2010 & 2020 (สำมะโนประชากรและเคหะ) | Yes — **snapshot, not series** |
| Functional uplift (de-facto ÷ registered) | Derived from census + documented estimates | Derived assumption (band) |

We currently have only `Population_Pct_BMA` (shares) — no absolute counts, no series,
no age structure. Step 1 is fetching the DOPA registered series.

## 2. Method — adopt official + Bangkok share (not a DIY cohort model)

1. **Fetch** DOPA registered population per district, annual (target 2000-2024) →
   `data/gis/bangkok_registered_pop_history.csv`. Compute Bangkok's **share of
   national** and each **district's share of Bangkok**, and their **trends** (shares
   are NOT frozen — Bangkok's national share and inner-district shares are declining).
2. **Spine:** take **UN WPP 2024** Thailand total (primary, reaches 2050 with age-sex);
   cross-check against **NESDC** (needs extension past 2040).
3. **Bangkok registered total 2050** = national projection x Bangkok share (share
   trended forward, with a documented trend model — linear/log on the historical share).
4. **Per-district 2050** = Bangkok total x each district's trended share → captures
   inner decline vs fringe growth. Constrain district shares to sum to 1 each year.
5. **Functional band** = registered projection x functional uplift ratio, from the NSO
   census de-facto/registered ratio (city-wide; per-district where census supports it).
   Report as a **low-high band**, never a false-precise point.
6. **Aging (optional, high value):** apply UN WPP Thailand age-sex proportions to
   Bangkok (noting Bangkok ages faster) → **median age, %65+, old-age dependency ratio**
   for 2050. This is the "civic infrastructure for an aging city" angle.

## 3. Outputs

- `data/gis/bangkok_registered_pop_history.csv` — DOPA series, per district, annual.
- `data/gis/bangkok_population_projection_2050.csv` — per district: registered 2024,
  registered 2050, functional 2050 (low/high), growth %, %65+ / median age (if step 6).
- `data/gis/bangkok_population_bma_total.csv` — city-wide trajectory by year to 2050,
  registered + functional band.
- `docs/population_projection_2050.md` — method, sources, assumptions, the aging /
  gap story, with citations.
- Optional: a chart (trajectory + band) and a GH-joinable per-district table so
  districts can be **coloured by projected 2050 growth/decline** over the basemap.

## 4. Assumptions & caveats (write into the docs)

- **Registered != residents.** Functional uplift is an estimate band, not a count.
- **Share method** assumes Bangkok tracks the national trajectory with a trended share;
  it does **not** model migration mechanistically (that's the cohort-component method
  we deliberately did not choose — heavier, and less citable than the official spine).
- **District share extrapolation** can drift; constrain to sum-to-one and sanity-check
  against the last observed year. Fringe districts growing, core shrinking.
- **Bangkok ages faster than the nation**, so borrowing national age structure
  understates %65+ — flag as conservative.
- The projection is a **scenario, not a forecast**; report the UN low/medium/high
  fertility variants as a band where feasible.

## 5. Open decisions (small — for review)

1. **Spine:** UN WPP 2024 as primary (reaches 2050 + age-sex, easy) vs NESDC as primary
   (official Thai, but ~2040 and needs extension). **Recommend UN WPP primary, NESDC
   cross-check.**
2. **Historical window** for the share trend: 2000-2024 (long, more stable) vs 2010-2024
   (recent, captures the current decline slope). **Recommend showing both.**
3. **Functional uplift:** single city-wide ratio vs per-district ratios (data-permitting).
4. **Aging indicators (step 6):** include or defer.

## 6. Order of work
Fetch DOPA registered series → fetch UN WPP Thailand spine → compute shares + trends →
project registered (city + district) → apply functional uplift band → (optional) aging →
write CSVs + docs → (optional) chart + GH colour-by-growth.
Step 1 (DOPA fetch) is the foundation and gates everything.

---

## 7. Gridded population on the LCZ grid (added — current + 2050, registered/non-reg)

User extension: put population on the **same 200 m grid as the LCZ mesh**
(330×259, local XY frame, `bangkok_lcz_grid_meta.json`), for **current + projected
2050**, split **registered vs non-registered**. This gives sub-district resolution and
overlays the LCZ mesh / satellite / BMA sites with no registration.

### Data
- **WorldPop 100 m, Thailand, 2020 UN-adjusted** (`tha_ppp_2020_UNadj.tif`) — de-facto
  spatial distribution, people-per-pixel, CC-BY. Primary raster.
- **DOPA registered per district** (§1) — for the registered/non-reg split.
- **UN WPP + per-district projection** (§2) — for the 2050 scaling.
- GHS-POP 2020/2030 as optional cross-check (and for the built-up "urban density" grid
  like Pawinee Iamtrakul 2024 — that image is built-up *extent*, not population).

### Dependency (decision D1 — the one blocker)
No raster libs installed (rasterio/GDAL/rioxarray all MISSING; have numpy + geopandas).
Two routes:
- **(a) `pip install rasterio`** (self-contained Windows wheels) + use WorldPop 100 m.
  Best fit — 100 m → 200 m is a clean 2× zonal sum. **Recommended.**
- **(b) No install:** use **Kontur Population** (H3 hexagons, GeoPackage — geopandas
  reads it) → area-weighted onto the 200 m cells. ~400 m source, so coarser, but zero
  new deps.

### Method
1. Fetch WorldPop tif (or Kontur gpkg).
2. **Resample to the LCZ grid:** each of the 85,470 LCZ cells has a lon/lat rectangle
   (cell centre X,Y ±100 m in local XY, back-projected — equirectangular is linear, so
   a cell = a lon/lat box, same maths as the satellite basemap). **Zonal SUM** of
   people-per-pixel into each cell (counts → sum, area-weight edge pixels), NOT average.
3. **Registered split (the "percentage from statistics"):** aggregate the grid to
   district → grid de-facto per district; `registered_share = DOPA_registered /
   grid_defacto` per district. Per cell: `registered = cell × share`,
   `non_registered = cell − registered` (≥0). NOTE: core districts can have
   `share > 1` (people keep registration but live elsewhere — the "ghost registration"
   effect); surface it, floor non-registered at 0.
4. **2050:** per-district growth factor = `proj_2050 / current` (from §2). Scale each
   cell by its district's factor → future grid. Inner districts shrink, fringe grow —
   captured because the factor is per-district. Re-split reg/non-reg (same or trended
   share).

### Outputs
- `data/gis/bangkok_lcz_grid_population.csv` — aligned to the LCZ grid (same `X,Y`):
  `pop_defacto_2020, pop_registered_2020, pop_nonreg_2020, pop_defacto_2050,
  pop_registered_2050, pop_nonreg_2050`.
- `data/gis/gh_population_grid.py` — colours the grid as a mesh, same structure as
  `gh_lcz_grid_mesh.py` (single ready-coloured Mesh; pick the field + a sequential ramp).

### Caveats
- Gridded pop is a **modeled dasymetric estimate** (redistributed census), not a count;
  WorldPop anchors to UN totals (≈ de-facto), DOPA is registered — using both is the
  honest pairing (see the source-comparison discussion).
- 2050 grid holds each cell's *within-district* share constant (only the district total
  moves) — it does not model intra-district redistribution. State as a limitation.

**Decisions to confirm:** D1 (rasterio-install + WorldPop **[rec]** vs Kontur no-install).
