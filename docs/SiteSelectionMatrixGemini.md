# Site Selection Matrix & Strategy (Civic Center as Evening Thermal Refuge)

> **Scope / terminology note.** This document and
> `docs/plan_Site-specific-local-morphing.md` describe the *same* thesis site.
> That plan still calls it the "Public Thermal Transit Hub"; this document
> reframes it as a **Civic Center / evening thermal refuge**. They are one
> project. Site selection (this doc) chooses *where*; the morphing plan then
> produces the site-specific EPW for *that* location. Pick one name for the
> thesis and use it in both files.

## 1. Thesis Shift & Narrative Concept
The project has shifted from a pure transit hub to a **Civic Center acting as an evening thermal refuge**. Mobility remains a critical component, but the driving narrative is now rooted in **user behavior and temporal thermal dynamics**.

### The Core Hypothesis
Office workers leave air-conditioned environments around 17:00. By the time they return home, their residential buildings (particularly those lacking central cooling or built with high thermal mass) have baked in the sun all day. These buildings radiate heat just as the outdoor Urban Heat Island (UHI) intensity peaks (approx. 18:00–20:00). Therefore, the Civic Center serves as a highly desirable "third space" to wait out the evening heat curve before returning home to sleep.

This hypothesis is directly supported by the World Bank report already in the
repo (`Modeling_Spatio-Temporal_Characteristics.md`, Section 3.4): *"The most
severe urban heat exposure occurs during the evening and night-time hours."*
In Hot/Dry season peak UHII occurs at ~19:00 LT. The evening-refuge concept is
therefore anchored in the same dataset that drives the morphing pipeline — this
is a strength worth stating explicitly in the methodology chapter.

### The 2050 behavioral-shift argument (why the demographic is broader than "the poor")
An earlier version of this strategy filtered candidate sites to LCZ 3/7 on the
belief that *only* middle-to-lower-income residents (who lack private A/C) would
use the refuge. Looking toward a hotter 2050, that framing is too narrow, and
the empirical literature (see §5) explains why:

- **Heat reschedules urban life into the evening.** Bank-card transaction data
  across Australian cities shows daytime activity (12:00–18:00) collapses on
  days ≥35 °C while **evening/night activity is resilient and even rises**;
  mobility data shows movement falls ~20% on hot afternoons specifically. As
  Bangkok warms toward 2050, more of daily life is pushed into the exact
  17:00–21:00 window this project targets — for *all* income groups, not only
  the vulnerable.
- **Adaptation mode is income-stratified, not the behavioral shift itself.**
  Everyone changes behavior under heat; higher-income residents adapt privately
  (A/C, cars, food-delivery), lower-income residents rely on public refuges.
  So a shared refuge has the highest *equity value* for LCZ 3 residents, but is
  not used *only* by them.
- **Bangkok already proves mixed-income refuge use: the mall.** The
  air-conditioned mall is a documented universal "third place" used across all
  income groups purely for free cooling. This civic center is essentially a
  **non-commercial, UTCI-optimized, lower-carbon alternative to the mall** —
  which also answers the sustainability objection that private A/C adaptation
  is itself accelerating regional warming.

**Consequence for the method (see §3):** vulnerability (LCZ 3) is therefore
treated as a **weighted equity criterion — how much the refuge is *needed* —
not as a hard exclusion gate.** Gating on LCZ 3 would force the site into
poor-only neighborhoods and contradict the 2050 broadening thesis; weighting it
alongside the intercept/transit criteria yields a site that is both high-*need*
and high-*reach*. This also partly dissolves the LCZ 7 data problem below: we no
longer *exclude* sites for lacking a class the data cannot resolve.

### Addressing Conceptual Nuances
To make this thesis methodology rigorous, the following nuances must be addressed in the site selection and program design:
1. **The Commute Geography:** The site must intercept users. If placed deep in a residential area, users must commute through peak heat. If placed deep in an office zone, it sits empty on weekends. The site must act as a **threshold** or intercept point between the CBD and residential zones. *(This is inherently a spatial-adjacency criterion, not a district attribute — see the Tier 0 pre-filter in §3.)*
2. **Socio-Economic Reality (weighted, not a filter):** High-income residents in high-rise condos (LCZ 1/4) bypass evening heat with private A/C; the highest *equity value* is for middle-to-lower-income residents in **Compact Low-Rise (LCZ 3)** typologies (dense shop-houses, flats) that trap heat and rely on failing natural ventilation. Per the 2050 behavioral-shift argument above, LCZ 3 is scored as a **need/equity weight, not an exclusion gate** — the refuge is *most valuable* there but not used *only* there. **Data reality check:** the narrative originally also named **LCZ 7 (Lightweight low-rise / informal settlements)**, but LCZ 7 does **not appear in any Bangkok district** as the dominant class, and appears in **zero cells** of the 120k-cell `bangkok_lcz_grid.csv`. This is a limitation of the source map, not a bug in the fetch scripts (see box below). **Decision (settled): option (a) — drop LCZ 7, use LCZ 3 as the vulnerability proxy.** The diagnostic below confirms LCZ 7 is genuinely absent from the source map (not a fixable script issue), and since LCZ is now a weight not a gate, its absence excludes no site. If informal settlements later prove essential to the thesis, the fallback is to hand-digitize target pockets at Tier 2 and state it as a known limitation.

> **Why LCZ 7 is missing — pipeline diagnosis (CONFIRMED).** The fetch scripts
> (`data/fetch_uhi_lcz.py`, `data/fetch_lcz_grid.py`) are **correct**: they map
> code 7 → "LCZ 7 (Lightweight low-rise)" and would emit it if present.
> `data/diagnose_lcz7.py` was run against the Bangkok bounding box and found
> **LCZ 7 = 0 pixels in BOTH the raw `LCZ` band and the `LCZ_Filter` band**
> (0 of ~343,557 classified px). This rules out the morphological filter and the
> per-district majority vote as causes: it is a **genuine gap in the Demuzere
> global LCZ map**, which is documented to systematically under-detect LCZ 7
> worldwide. Bangkok's lightweight/shophouse fabric is absorbed into LCZ 3
> (present) and LCZ 6/8. No band switch or reducer change recovers it — only a
> finer local classification would.
3. **Socio-economic proxy limitation:** LCZ classifies *built form*, not *income*. Using LCZ 3 as the vulnerability metric assumes compact-low-rise ⇒ lower-income + no central A/C, which is broadly true in Bangkok but not universal. Where feasible, corroborate with a census/income layer (NSO district data, or land value from the Treasury Department) at Tier 2. At minimum, name this as a stated proxy in the limitations section.
4. **Programmatic Relevance (17:00–21:00):** A traditional library won't hold people for 4 hours post-work. The architecture must integrate Bangkok's evening culture: food (night markets), recreation (sports, gyms), and socializing in thermally comfortable, semi-outdoor environments optimized via UTCI form-finding.

---

## 2. Data Inventory & Gaps
We build on the existing `bangkok_uhi_data.csv` (UHI Tier, seasonal Night/Evening UHII, LST, Dominant LCZ, Population). Before the matrix can run, be explicit about what is **in hand** vs. **still needed**, because the matrix cannot be scored until every criterion has data.

| Criterion | Metric | Source | Status |
|---|---|---|---|
| UHI severity | `UHII_HotDry_Evening_C`, `LST_Mean_C` | `bangkok_uhi_data.csv` | ✅ have |
| Housing vulnerability | `Dominant_LCZ` = LCZ 3 | `bangkok_uhi_data.csv` | ✅ have |
| Demographic density | `Population_Pct_BMA` | `bangkok_uhi_data.csv` | ✅ have |
| Transit / intercept | station + interchange count per district | OSM via QGIS `QuickOSM`, or BMA GIS | ❌ **needed** |
| Work/home adjacency | residential fabric within 200 m of a working zone, per district | OSM `landuse` via `data/fetch_land_use_osm.py` → `bangkok_intercept_scores.csv` | ✅ have (OSM proxy — see caveat below) |
| Micro land availability | underused plots near nodes | OSM signals via `data/fetch_vacant_plots_osm.py` → `bangkok_vacant_plots_scored.csv`; imagery for final check | 🟡 candidate shortlist auto-extracted (Tier 2); imagery verification still manual |

**Metric caveat — LST is a daytime surface signal.** `LST_Mean_C` is Landsat
land-surface temperature at the ~10:30 overpass, i.e. a *daytime, surface* (not
air, not evening) measurement. It is defensible in an evening-peak criterion
**only** as a proxy for daytime heat storage that is re-radiated after sunset —
say so. If you want a purely evening-consistent severity metric, weight
`UHII_HotDry_Evening_C` more heavily and treat LST as secondary/confirmatory.

**Avoid double-counting.** `UHI_Tier` is itself derived largely from the Night
UHII field, so do **not** feed both `UHI_Tier` and a raw UHII column into the
matrix as if independent — that silently double-weights nighttime UHI. The
criteria below are chosen to be as orthogonal as possible: evening UHII (heat),
LCZ (built form), population (exposure), transit (access).

---

## 3. The Decision Matrix Implementation
Weighted Multi-Criteria Decision Analysis (MCDA), executed in **three** tiers. Tier 0 is a spatial pre-filter (the intercept logic is a location property, not a district score); Tier 1 ranks districts; Tier 2 selects the plot.

### Tier 0 — Intercept pre-filter (spatial gate, pass/fail)
Before scoring, discard districts that cannot serve the commute-intercept role.
Keep a district only if it **borders or contains a commercial/employment core
AND adjacent residential fabric** (a work↔home threshold). This encodes Nuance
#1 as a gate rather than diluting it into a 25% weight where a purely
residential or purely commercial district could still rank high. Output: a
shortlist (~10–20 districts) that advance to Tier 1.

**Operationalised (data now in hand).** `data/fetch_land_use_osm.py` pulls OSM
`landuse=residential` and `landuse ∈ {commercial, retail, industrial} + building=office`
polygons for Bangkok, buffers the working zones by **200 m** (a walkable
work↔home threshold), and measures where residential fabric falls inside that
buffer. Output is `bangkok_intercept_scores.csv`, one row per district with:
- `Intercept_Score_Pct` — % of the **district** area that is intercept fabric.
- `Intercept_Pct_of_Residential` — % of the district's **residential** fabric
  that is intercept-adjacent (less biased by how much of the district is parks,
  water, or unmapped, so prefer this for the gate).

**Suggested gate:** keep districts with `Intercept_Score_Pct` above a natural
break in the ranking (the top tier — Bang Rak 95%, Yan Nawa 71%, Sathon 66%,
Bang Kho Laem 43%, Din Daeng 39%, Khlong Toei 32% — sits well clear of the long
<10% tail). Treat the cutoff as a defensible threshold, not a hard law, and
sanity-check borderline districts against imagery.

> **Methodology caveats (state these in the thesis):**
> 1. **Areas are dissolved before measurement.** OSM landuse polygons overlap
>    and duplicate; an earlier version summed per-polygon areas and produced a
>    physically impossible >100% score for Bang Rak. The scorer now unions each
>    layer first, so scores are bounded to [0, 100] and overlaps aren't
>    double-counted.
> 2. **OSM landuse is an incomplete, volunteer-mapped proxy**, not an
>    authoritative cadastre — coverage is patchy and some areas are one coarse
>    polygon. It is defensible for **relative** district screening (the intended
>    Tier 0 use), not for absolute land-area claims. Where feasible, corroborate
>    the shortlist against the Bangkok Comprehensive Plan (Land Use) map.
> 3. The 200 m buffer is a modelling assumption (walkable intercept distance);
>    it is easy to re-run at 150/300 m to test sensitivity.

**Grasshopper visualisation.** Two GHPython scripts render this on the canvas
alongside the district curves:
- `data/gis/gh_landuse_zones.py` — residential vs working zone polygons as
  curves (shares the exact projection origin of `gh_geojson_to_curves.py`, so
  the layers register). Colour residential/working differently to read the
  work↔home seam directly.
- `data/gis/gh_intercept_scores.py` — returns `Intercept_Score_Pct` /
  `Intercept_Pct_of_Residential` per district in `District_Names` order, to
  drive a gradient (choropleth) on the existing district curves.

### Tier 1 — Macro-Scale district ranking (MCDA)
Score each surviving district on a normalized 0–10 scale per criterion.

**Normalization (state this explicitly in the thesis):** min–max across the
candidate set,
`score_i = 10 × (x_i − x_min) / (x_max − x_min)`,
so the best district on each axis = 10, worst = 0. For the LCZ criterion (categorical), use an ordinal map instead: LCZ 3 = 10 (target compact low-rise), LCZ 2 = 6 (compact midrise — hot but denser/wealthier), LCZ 8 = 4 (large low-rise), everything else = 2.

| # | Criterion | Weight | Metric | Rationale |
|---|---|---|---|---|
| 1 | UHI severity (evening peak) | **35%** | `UHII_HotDry_Evening_C` (primary) + `LST_Mean_C` (secondary, daytime-storage proxy) | Core driver of the thesis problem; evening-consistent. |
| 2 | Housing vulnerability (equity) | **30%** | `Dominant_LCZ` ordinal (LCZ 3 = 10) | The built form where evening heat retention is worst and A/C least available. **A weight, not a gate** — see §1's 2050 behavioral-shift argument. A non-LCZ-3 district is penalized on this axis but not excluded. |
| 3 | Transit / intercept potential | **25%** | station + interchange count per district | Accessibility for the 17:00 commuter crowd. **Requires the missing OSM data.** |
| 4 | Demographic density | **10%** | `Population_Pct_BMA` | Ensures the intervention serves a dense population. |

Final score = Σ (weight × normalized criterion). Rank descending; carry the **top 3** to Tier 2.

**Provisional ranking on data in hand (transit not yet gathered).** Scoring
criteria 1, 2, 4 only, with weights renormalized to 46.7 / 40 / 13.3%, the
current top candidates are:

| Rank | District | LCZ | Tier | HotDry Eve °C | LST °C | Pop % | Score |
|---|---|---|---|---|---|---|---|
| 1 | Bueng Kum | LCZ 3 | Medium | 3.1 | 45.14 | 2.51 | 8.90 |
| 2 | Chatuchak | LCZ 3 | Severe | 3.1 | 44.35 | 2.80 | 8.79 |
| 3 | Bang Sue | LCZ 3 | Severe | 3.2 | 44.70 | 2.17 | 8.72 |
| 4 | Lat Phrao | LCZ 3 | Medium | 3.1 | 44.66 | 2.08 | 8.60 |
| 5 | Din Daeng | LCZ 3 | Severe | 2.7 | 44.25 | 2.02 | 8.16 |

> **Note the discrepancy:** the earlier draft named **Din Daeng** as the obvious
> winner, but on the actual numbers it ranks **5th** without transit. This is
> exactly why the matrix exists rather than intuition. Din Daeng and Phaya Thai
> are transit-interchange-rich and will likely climb once criterion 3 is added —
> confirming that the **missing transit data is decisive**, not cosmetic. Gather
> it before treating any ranking as final.

**Sensitivity analysis (required for a defensible thesis MCDA).** MCDA weights
are subjective, so show the result is robust: re-run the ranking with each
weight perturbed ±10% (or swap to equal weights) and report whether the top 3
stays stable. If the top 3 is unstable, that is itself a finding — say the
top-tier districts are effectively tied and the choice defers to Tier 2
(micro-scale) factors.

### Tier 2 — Micro-Scale plot selection
Take the top 3 districts from Tier 1. Within each:
1. Map a **500 m walking radius** around major transit stations (empirically-supported comfortable walking distance in tropical heat; cite and note it may be shorter under Bangkok evening conditions).
2. Overlay the **Land Use Map** to find the exact threshold where commercial zoning transitions to residential (the Tier 0 gate, now at plot resolution).
3. Use the `bangkok_lcz_grid.csv` grid (200 m cells) to confirm the immediate surroundings are LCZ 3 fabric, and — if pursuing the informal-settlement angle — hand-digitize any LCZ 7-type pockets the continental map missed.
4. Use satellite imagery to identify a specific, buildable, underutilized plot (parking lot, low-density commercial) within that radius and threshold.

**Semi-automated candidate extraction (step 4, operationalised).**
`data/fetch_land_use_osm.py`'s sibling `data/fetch_vacant_plots_osm.py` now pulls
OSM vacancy *signals* city-wide and ranks them so step 4 starts from a shortlist
instead of a blank satellite view. It fetches explicit vacant tags
(`landuse=brownfield`/`greenfield`/`construction`) plus open-vegetation gaps
(`landuse=grass`, `natural=scrub`), keeps discrete polygons ≥ 400 m², and tags
each plot with the funnel criteria:
- `dist_to_station_m` / `nearest_station` — nearest of the ~160 rail stations.
- `intercept_score` — the district's Tier-0 intercept % (joined from
  `bangkok_intercept_scores.csv`).
- `in_intercept_surface` — whether the plot sits on the work↔home intercept
  surface (`res_union ∩ work_buffer(200 m)`).
- `source_class` / confidence — brownfield/greenfield/construction = high;
  grass/scrub = low (noisy landscaping, kept but down-weighted).

A composite `rank_score` (transit proximity 35% + district intercept 25% +
intercept-surface bonus 20% + source confidence 10% + buildable-size band 10%)
sorts them. Outputs: `bangkok_vacant_plots.geojson`,
`bangkok_vacant_plots_scored.csv`, `docs/bangkok_vacant_plots_map.png`. The
current top candidates land in **Bang Rak, Sathon and Khlong Toei** (the top
intercept districts) and are all high-confidence `construction`/`brownfield`
plots 80–530 m from a station.

> **Caveats (state in the thesis, same standard as Tier 0):**
> - **Candidates, not confirmed vacant.** OSM has no reliable vacant tag and
>   absence of a building ≠ empty land. The pipeline maximises *recall +
>   relevance ranking*; **manual satellite/Street-View verification of the top
>   plots remains the required final step** (step 4 proper).
> - `landuse=construction` is *transitional* — a site under construction may
>   already be committed development, not available land. Filter `source_class`
>   to `brownfield`/`greenfield` if you want genuinely undeveloped plots.
> - grass/scrub are mostly landscaping, not buildable; they dominate by count and
>   are flagged low-confidence for exactly that reason.
> - Authoritative upgrade path (out of scope): cadastral data (Dept. of Lands) or
>   a recent-satellite land-cover classification.

**Grasshopper:** `data/gis/gh_vacant_plots.py` draws the top-N plots as curves in
the shared canvas frame (same origin as the district curves / transit network),
coloured by `rank_score`, for overlay against the stations and intercept zones.

### Sampling design — intervention + control
The morphing plan (Track A validation) needs to *demonstrate the local
correction matters*, which requires contrast. Decide the study design now:
- **Intervention site:** the Tier 1/Tier 2 winner (high-UHI, LCZ 3, transit-served).
- **Control / counterfactual (recommended):** one low-UHI-tier, non-LCZ-3 district (e.g. a peripheral LCZ 6 district such as Min Buri or Lat Krabang) run through the *same* morphing pipeline, so the site-specific EPW delta is shown against a genuinely different urban climate — not just asserted.

This reconciles the two documents: this matrix outputs the **where**, the
sampling pair (intervention vs. control) feeds the morphing plan's **validation
plots** and comparison energy simulation.

---

## 4. Next Steps
1. **Gather transit data:** BTS/MRT station + interchange counts per district (OSM `QuickOSM`), the only missing Tier-1 input.
2. **Resolve remaining open decision:** confirm the intervention + control sampling design. *(LCZ 7 decision settled — dropped; `data/diagnose_lcz7.py` confirmed it is absent from the source map, not a fixable pipeline issue.)*
3. **Build the scoring script** — a small `data/build_site_selection_matrix.py` reading `bangkok_uhi_data.csv` + the transit counts, applying Tier 0 gate → Tier 1 min–max normalization → weighted sum → sensitivity sweep, and writing a ranked `data/gis/site_selection_scores.csv`. (Provisional scorer already prototyped — see §3 table.)
4. **Run scoring**, output Top 3 candidate districts + the control district.
5. **Proceed to Tier 2** micro-scale plot selection for the final thesis site.
6. **Hand off** the chosen district name to `data/derive_local_uhi_delta.py` (morphing plan, Track A Step 3).

---

## 5. Annotated Bibliography — behavioral shift under heat
Evidence base for §1's 2050 behavioral-shift argument and the "weight, don't
gate" treatment of LCZ vulnerability. Grouped by the claim each supports.

### A. Heat reschedules activity into the evening/night (core hypothesis support)
- **Adaptive urban economies: intra-day temporal behavioural adaptation to extreme heat in Australian cities** — *npj Urban Sustainability* (2025). Bank-card data: daytime spending collapses on days ≥35 °C while evening/night activity is resilient and rises. Direct support for the 17:00–21:00 refuge window. https://www.nature.com/articles/s42949-025-00297-7
- **Extreme heat reduces and reshapes urban mobility** — *PMC*. Mobile-phone mobility falls ~10% on hot days, ~20% on hot afternoons; activity displaced from peak-heat hours. https://pmc.ncbi.nlm.nih.gov/articles/PMC13077673/
- **Intraday adaptation to extreme temperatures in outdoor activity** — *Scientific Reports* (2022). Temporal substitution — avoiding the hottest hours — is an established, measurable adaptation. https://www.nature.com/articles/s41598-022-26928-y

### B. Adaptation mode is income-stratified (the tension to address honestly)
- **The Role of Cooling Centers in Protecting Vulnerable Individuals from Extreme Heat** — *PMC*. Public cooling refuges are used predominantly by lower-income, energy-burdened residents. https://pmc.ncbi.nlm.nih.gov/articles/PMC9378433/
- **Assessing Vulnerability to Urban Heat: access to refuge by socio-demographic status, Portland OR** — *PMC*. Disproportionate heat exposure + refuge-access gaps by income/race. https://pmc.ncbi.nlm.nih.gov/articles/PMC5923682/
- **Vulnerable, Resilient, or Both? Adaptation behaviors of low-income UHI residents** — *PMC*. Qualitative account of adaptive capacity constraints for the target demographic. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9517765/
- **Urban food delivery services as extreme heat adaptation** — *Nature Cities* (2024). Private adaptation (delivery orders +12.6% at 35 °C) — how higher-income residents avoid public exposure. https://www.nature.com/articles/s44284-024-00172-z

### C. Mixed-income refuge precedent + sustainability rationale (rescues the broadening argument)
- **Shopping malls as Bangkok's cultural thermometer** — *Bangkok Post*. The A/C mall as a universal, all-income "third place" for free cooling — precedent for a non-commercial civic equivalent. https://www.bangkokpost.com/life/social-and-lifestyle/3200778/shopping-malls-as-bangkoks-cultural-thermometer
- **Southeast Asia's air conditioning is burning up the Earth** — *Kontinentalist*. Private A/C adaptation as regional-warming driver — the low-carbon case for a shared refuge. https://kontinentalist.com/stories/air-conditioning-in-southeast-asia-is-worsening-climate-change

### D. Comfort behavior is program-driven, not pure avoidance (supports 4-hour program need)
- **Counter-intuitive heat adaptation: 360° behavioral tracking in parks** — *ScienceDirect* (2026). Functional/social motivation can override thermal sensation — people stay in warm spaces for program. https://www.sciencedirect.com/science/article/abs/pii/S221067072600288X
- **Behavioural (mal)adaptation to extreme heat in Australia** — *ScienceDirect* (2023). Not all adaptation is beneficial; frames the maladaptation risk. https://www.sciencedirect.com/science/article/pii/S2212095523003668

### E. Future-climate framing (2050 horizon)
- **Identifying analogs of future thermal comfort under projection scenarios in 352 Chinese cities** — *ScienceDirect* (2022). Cities shift toward hotter comfort analogs by 2050 even under optimistic scenarios. https://www.sciencedirect.com/science/article/abs/pii/S2210670722002128

> **Note on transferability.** Items A, B, D and E are largely from Australian /
> US / Chinese contexts. Flag in the thesis that behavioral-adaptation magnitudes
> may differ for Bangkok's tropical, humidity-dominated regime; item C provides
> the local (SEA/Bangkok) anchor. Where possible, corroborate with a
> Thailand-specific source before relying on a transferred number.
