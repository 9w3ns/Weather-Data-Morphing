# Plan: Site-Specific Local UHI Morphing

## Objective

Extend the existing citywide GCM morphing pipeline (`morphing/epw_morphing_engine.py`,
Belcher/BTWS) so that a chosen site's EPW reflects **both**:

1. Future global climate change (already implemented — CMIP6 monthly deltas), and
2. That site's measured local Urban Heat Island intensity, derived from the
   per-district data already computed in `data/gis/bangkok_uhi_data.csv`
   (real WRF UHII, Landsat LST, Demuzere LCZ — see
   `docs/uhi_data_sourcing_plan.md`).

This is Option #2 from the UHI/LCZ mapping discussion: instead of one generic
Bangkok EPW, produce a **site-specific** EPW for whichever district/site is
chosen for the Public Thermal Transit Hub (`docs/development_plan.md` Phase 4),
so the building energy simulation and form-finding workflow respond to that
site's real urban climate, not a citywide average.

## Why this is methodologically sound (supporting research)

This two-step structure — GCM morph, then local urban correction — is an
established pattern in building-performance simulation literature, not a
novel/unvalidated idea:

- Bueno, Norford, Hidalgo & Pigeon (2013), *"The Urban Weather Generator"*,
  Journal of Building Performance Simulation — foundational method for
  morphing a rural/airport EPW into an urban-canyon EPW using an urban
  canopy model.
  [ResearchGate](https://www.researchgate.net/publication/241683424_The_urban_weather_generator)
- Evola, Marletta & Cimino (2018), *"Weather data morphing to improve
  building energy modeling in an urban context"*, IIETA/MMEP — explicit
  two-step approach: climate-change morph first, then local UHI/urban-canopy
  correction, before simulation.
  [IIETA](https://www.iieta.org/journals/mmep/paper/10.18280/mmep.050312)
- *"Investigation of urban heat island and climate change and their combined
  impact on building cooling demand in the hot and humid climate of Qatar"* —
  same combined approach in a hot-humid climate analogous to Bangkok.
  [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2212095523002985)
- *"Combined impact of climate change and urban heat island on building
  energy use in three megacities in China"* (2025) — shows the two effects
  don't simply add linearly; useful if quantifying interaction effects.
  [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378778825001161)
- *"Local UHI mitigation and utilization: Urban building energy modeling,
  simulation, and urban design responses based on localized weather data"*
  (Building Simulation, 2026).
  [Springer](https://link.springer.com/article/10.1007/s12273-026-1410-7)
- Published UHI/cooling-load studies using the **Local Climate Zone (LCZ)
  scheme** specifically as the classification basis for per-site EPW
  correction — validates using `Dominant_LCZ` as an input variable, matching
  what `data/fetch_uhi_lcz.py` / `data/fetch_lcz_grid.py` already compute.
- Ladybug Tools **Dragonfly** "Run Urban Weather Generator" component — a
  ready-made, in-Grasshopper implementation of Bueno's UWG, already
  compatible with the toolchain used elsewhere in this repo
  (`docs/grasshopper_integration_plan.md`, `docs/morphing_gh_component.py`).
  [Component docs](https://docs.ladybug.tools/dragonfly-primer/components/6_alternativeweather/run_urban_weather_generator) ·
  [Ladybug Tools Academy — Modeling UHI with the UWG](https://docs.ladybug.tools/ladybug-tools-academy/urban-energy-with-dragonfly/modeling-urban-heat-island-with-the-uwg)

## Architecture: two independent tracks

**Track A — empirical, built from data already in this repo.** Add a local
UHI delta on top of the GCM-morphed dry bulb temperature, using the World
Bank WRF UHII values already sitting in `bangkok_uhi_data.csv`. Lower
engineering risk, reuses the existing `EPWMorphingEngine` architecture,
ships faster.

**Track B — physics-based, via Dragonfly/UWG.** Run the actual Urban Weather
Generator using urban-canyon parameters derived from the site's `Dominant_LCZ`
class. Heavier to set up, but it's the literature-standard method (Bueno et
al.) and gives Track A an independent cross-check — strong for a thesis
methodology chapter ("two independent local-correction methods, compared").

Recommend building Track A first (it's mostly data wrangling + a small
engine extension), then Track B as validation once a site is chosen.

## Diurnal treatment — resolved from the source report

The Public Thermal Transit Hub is a **civic + mixed-use space operating
8:00–20:00**. This matters a lot here: `bangkok_uhi_data.csv`'s two UHII
columns per season (Night, Evening) don't cover most of that window on
their own, so the question was what to do about the hours in between. The
full report text (`Modeling_Spatio-Temporal_Characteristics.md` in the repo
root — a text extraction of `research/Modeling Spatio-Temporal
Characteristics of Urban Heat in Bangkok.pdf`) resolves this directly,
with numbers, rather than requiring an assumption:

- **Confirmed hour windows** (Section 2.4/3.1, Table 1): Night = 00:00–02:00,
  Morning = 09:00–11:00, Evening = 18:00–20:00. **None of "Night" falls
  inside the 8:00–20:00 operating window.**
- **Daytime UHI is explicitly negligible-to-negative, not just unmeasured**
  (Section 3.3): *"During the morning and throughout the afternoon, the
  temperature difference between urban and rural areas becomes
  negligible... a modest urban cool island effect can emerge."* Morning
  BMA-wide mean UHII is ≈0°C in every season (−0.2°C Cool/Dry, −0.4°C
  Hot/Dry, +0.3°C Wet), and the cool-island effect is *strongest* around
  16:00 in Hot/Dry season (citing Kamma et al., 2017, a prior BMA study).
  This covers roughly 09:00–17:00 of the operating window.
- **Evening (18:00–20:00) is the operationally dominant window** — Section
  3.4: *"The most severe urban heat exposure occurs during the evening and
  night-time hours... From morning to late afternoon, the majority of the
  population is exposed to UHII levels below 2°C."* In Hot/Dry season, peak
  UHII actually occurs at 19:00 LT (3.3°C in compact high-rise zones,
  Section 3.3), driven by southerly winds advecting urban warm air
  (Section 3.1.2) — consistent with the Hot/Dry Evening > Night reversal
  already found in `bangkok_uhi_data.csv`. This is exactly the column
  already extracted (`UHII_*_Evening_C`).
- **One residual link to nighttime, even though the building is closed
  then**: Table 4 shows daily minimum temperature (Tmin, typically recorded
  06:00–08:00 — right at opening) has the *largest* urban-rural gap of any
  statistic in the report: +5.1°C (Cool/Dry), +2.4°C (Hot/Dry), +6.0°C
  (Wet). The building doesn't open into neutral conditions; it opens at the
  tail of the overnight heat buildup, before UHII collapses to ~0 by
  09:00–11:00.

**Resulting piecewise treatment for Step 3** (per season, applied to dry
bulb temperature only during operating hours — no correction needed outside
8:00–20:00 since the space is unoccupied then):

| Hours | Treatment |
|---|---|
| 08:00–09:00 | Small residual bump, informed by the Tmin gap (largest in Wet/Cool-Dry, smaller in Hot/Dry) |
| 09:00–17:00 | ≈0°C (cited directly from Section 3.3, not assumed) |
| 18:00–20:00 | `UHII_<season>_Evening_C` from `bangkok_uhi_data.csv` (already extracted) |

**Open design decision, not a data question**: if the building design uses
a passive night-flush/pre-cooling strategy (common for tropical civic
buildings), nighttime UHI (00:00–02:00) still matters *indirectly* even
though it's outside operating hours — a hotter night reduces how much free
cooling that strategy can bank before 08:00. Confirm whether this is part
of the design before deciding whether `UHII_*_Night_C` stays entirely out
of scope or feeds a separate thermal-mass pre-cooling calculation.

Calendar-month boundaries for the three seasons (Section 2.1, confirmed
from the report, not assumed): Cool/Dry = November–February, Hot/Dry =
March–May, Wet monsoon = June–October.

## Step-by-step

### Track A — empirical local UHI correction

1. **Pick the site(s).** Do **not** eyeball this — run the formal MCDA in
   `docs/SiteSelectionMatrixGemini.md` (Tier 0 intercept gate → Tier 1
   weighted ranking over UHI severity, LCZ vulnerability, transit, and
   population → Tier 2 plot selection). That process outputs an
   **intervention** district (high-UHI, LCZ 3, transit-served) and a
   **control** district (low-UHI-tier, non-LCZ-3) so this plan's validation
   plots and comparison energy sim can *show* the local correction matters
   rather than assert it. Note the site is the same building the matrix doc
   reframes as the "Civic Center / evening thermal refuge" — align the name.
   Feed the chosen district name(s) into Step 3.
2. **Confirm the operating-hours design decision**: decide whether the
   night-flush/pre-cooling caveat above applies to this design. If not,
   `UHII_*_Night_C` can be dropped from scope entirely and Step 3 only needs
   the piecewise table above.
3. **Build `data/derive_local_uhi_delta.py`**: for a given district name,
   read its `UHII_*_Evening_C` columns (and `UHII_*_Night_C` only if Step 2
   says the pre-cooling caveat applies) from `bangkok_uhi_data.csv`, and
   write a per-site delta table (a new small CSV, e.g.
   `data/gis/local_uhi_delta_<district>.csv`) using the resolved piecewise
   treatment above: ≈0°C for 09:00–17:00, a small Tmin-informed bump for
   08:00–09:00, the season's Evening value for 18:00–20:00.
4. **Extend the morphing engine**: add a new stage — either a method on
   `EPWMorphingEngine` (e.g. `apply_local_uhi(delta_csv_path)`) or a small
   new class `morphing/local_uhi_morpher.py` mirroring the style of
   `belcher_morpher.py`/`btws_morpher.py` — that adds the local delta to
   the already-GCM-morphed dry bulb (and optionally dew point) temperature
   array, indexed by hour-of-day instead of just month like the existing
   `_get_month_mask`/`_morph_dry_bulb` logic. Run it *after* `engine.morph()`,
   before `engine.save()`.
5. **Re-run `_enforce_psychrometric_consistency()`** (already exists) after
   the local UHI stage too, since adding a second temperature shift can
   reintroduce a DPT > DBT violation.
6. **Wire into Grasshopper**: extend `docs/morphing_gh_component.py`'s
   pattern (it already does `sys.path.append(repo/morphing)` +
   `from epw_morphing_engine import EPWMorphingEngine`) — add a
   `District_Name` input, load the matching local delta CSV from Step 3,
   call the new local-UHI stage before `engine.save()`. This slots into the
   same GH canvas already reading `Dominant_LCZ`/`UHI_Tier` via
   `data/gis/gh_data_matcher.py`.
7. **Validate**: plot baseline vs. GCM-only-morphed vs.
   GCM+local-UHI-morphed dry bulb temperature (reuse the pattern in
   `morphing/generate_plots.py` / `morphing/plot_hourly_diff.py`) and sanity
   check against the report's documented magnitude — 09:00–17:00 should sit
   near baseline (±0°C), 18:00–20:00 should show the Evening bump, matching
   Section 3.3/3.4's stated pattern.

### Track B — Dragonfly/UWG cross-check

8. **Map `Dominant_LCZ` → UWG urban-canyon parameters** (building height
   range, site coverage ratio, facade-to-site ratio, tree coverage,
   pavement fraction) using the Stewart & Oke (2012) LCZ characteristic
   table for the chosen site's class.
9. **Run Dragonfly's "Run Urban Weather Generator" component** in
   Grasshopper on the baseline (or GCM-morphed) EPW with those parameters
   to produce an independent UHI-corrected EPW.
10. **Compare** Track A's and Track B's dry bulb temperature output for the
    same site/hours — where they agree, that's a strong validated result;
    where they diverge, that's a discussion point for the thesis
    (empirical WRF-observed UHI vs. a generic physics-based canopy model
    may reasonably differ for Bangkok's specific building stock).

### Tie back to the design workflow

11. **Feed the final chosen EPW** (GCM + local UHI, or the Dragonfly/UWG
    version) into the existing Ladybug/Honeybee/Anemone form-finding chain
    (`docs/development_plan.md` Phase 4) for the Public Thermal Transit Hub.
12. **Run a comparison building energy simulation** (baseline vs.
    citywide-morph-only vs. site-corrected EPW) to quantify how much the
    local correction changes predicted cooling load — this is the number
    that justifies, in the thesis, why site-specific correction (and by
    extension, careful site selection using the UHI/LCZ maps) matters.
13. **Write up methodology and limitations** in the thesis methodology
    chapter, citing the sources above and being explicit about the Step 2
    simplifying assumption (2-sample diurnal interpolation) as a stated
    limitation, not a hidden one.

## Deliverables checklist

- [ ] Site(s) selected from `bangkok_uhi_data.csv`
- [x] Season/hour mapping confirmed from the World Bank report (Night
      00:00–02:00, Morning 09:00–11:00, Evening 18:00–20:00; season months
      confirmed Section 2.1)
- [ ] Night-flush/pre-cooling design decision confirmed (determines whether
      `UHII_*_Night_C` stays in scope)
- [ ] `data/derive_local_uhi_delta.py`
- [ ] `morphing/local_uhi_morpher.py` (or engine method)
- [ ] GH component wiring (extends `docs/morphing_gh_component.py` pattern)
- [ ] Validation plots (baseline vs. GCM vs. GCM+local UHI)
- [ ] Track B Dragonfly/UWG comparison (optional but strengthens the thesis)
- [ ] Comparison building-energy simulation results
- [ ] Methodology write-up with limitations stated

## Sources

- [Bueno, Norford, Hidalgo & Pigeon — The Urban Weather Generator](https://www.researchgate.net/publication/241683424_The_urban_weather_generator)
- [Evola, Marletta & Cimino — Weather data morphing to improve building energy modeling in an urban context (IIETA)](https://www.iieta.org/journals/mmep/paper/10.18280/mmep.050312)
- [Investigation of urban heat island and climate change... Qatar](https://www.sciencedirect.com/science/article/pii/S2212095523002985)
- [Combined impact of climate change and urban heat island on building energy use in three megacities in China](https://www.sciencedirect.com/science/article/abs/pii/S0378778825001161)
- [Local UHI mitigation and utilization: UBEM based on localized weather data (Building Simulation)](https://link.springer.com/article/10.1007/s12273-026-1410-7)
- [Run Urban Weather Generator — Dragonfly component docs](https://docs.ladybug.tools/dragonfly-primer/components/6_alternativeweather/run_urban_weather_generator)
- [Modeling Urban Heat Island with the UWG — Ladybug Tools Academy](https://docs.ladybug.tools/ladybug-tools-academy/urban-energy-with-dragonfly/modeling-urban-heat-island-with-the-uwg)
- `docs/uhi_data_sourcing_plan.md` (this repo — source of `bangkok_uhi_data.csv`)
- `docs/development_plan.md` (this repo — Phase 4, design workflow handoff)
- `research/Modeling Spatio-Temporal Characteristics of Urban Heat in Bangkok.pdf` (World Bank Policy Research Working Paper 11158) — see also `Modeling_Spatio-Temporal_Characteristics.md` (this repo root) for the extracted text used to resolve the diurnal treatment above (Sections 2.1, 2.4, 3.1–3.5)
