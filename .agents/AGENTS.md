# AGENTS.md — Weather Data Morphing Tool

## Project Goal

Build a **transparent, Python-based EPW weather data morphing tool** for projecting future climate conditions in Bangkok, implementing **two separate morphing methods** side-by-side:

1. **Normal Shift Method** (Belcher et al., 2005 / Jentsch, 2012) — the standard shift/stretch approach used by CURA-lab's Future Weather Generator and futureweather.co
2. **Bounded Temperature Weighted Stretch (BTWS)** (Eames et al., 2024) — an advanced morphing algorithm that independently preserves projected daily min, max, and mean temperature changes

The tool generates future `.epw` files for building performance simulation under CMIP6 Shared Socioeconomic Pathways (SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5), with the primary design scenario being **Bangkok 2070 SSP5-8.5**.

The two methods produce different morphed outputs by design — the goal is to **compare how each method handles the same climate projection** and understand where they diverge, especially for temperature extremes and solar radiation.

---

## Thesis Context

This tool is **Phase 01** of a KMITL Faculty of Architecture Year 5 thesis (Atin Punyanitya, 65020505) investigating the **Public Thermal Transit Hub** — a new civic building typology whose spatial form is derived from projected 2070 UTCI thermal stress data.

The morphed EPW file produced by this tool feeds directly into:
- **UTCI thermal mapping** via Grasshopper + Ladybug (Phase 02)
- **Cellular Automata form-finding** via Grasshopper + Anemone (Phase 07)
- **Architectural design** of transition zones, shading depth, and thermal gradients

### The Critical Finding This Tool Must Support

> **UTCI Floor Shift:** Under SSP5-8.5 at 2070, the future UTCI minimum (38.2°C) exceeds the present average (37.6°C). The entire outdoor thermal distribution shifts up one stress category. No outdoor point falls below "Very Strong" heat stress.

The accuracy of this finding depends entirely on the quality of the morphed EPW — particularly the temperature, solar radiation (GHR/DNR/DHR), humidity, and wind speed fields, since UTCI uses all four simultaneously.

---

## Architecture

### File Structure

```
Weather-Data-Morphing/
├── .agents/
│   └── AGENTS.md                              ← This file
├── morphing/                                  ← Core morphing tools
│   ├── belcher_morpher.py                     ← Method 1: Normal Shift/Stretch
│   ├── btws_morpher.py                        ← Method 2: Bounded Temperature Weighted Stretch
│   └── epw_morphing_engine.py                 ← Orchestrator: EPW I/O + dispatches to either method
├── data/                                      ← Input and baseline data
│   ├── deltas/
│   │   └── bangkok_ssp585_2070.csv            ← Monthly climate change factors
│   └── epw/
│       ├── Bangkok_baseline_2026_TMYx.epw     ← Present-day baseline EPW
│       └── Bangkok_CURA-lab_2070_ssp585.epw   ← CURA-lab Normal Shift benchmark EPW
├── docs/                                      ← Plans and analysis documents
│   ├── development_plan.md                    
│   ├── btws_thailand_analysis.md              
│   └── grasshopper_integration_plan.md        
├── research/
│   └── hamann_2025_weather_morphing.txt       ← Key research reference
└── thesis/                                    ← Thesis context and documentation
    ├── thesis_brief.docx
    ├── UTCI_metric_rationale.docx
    ├── UTCI_CA_process_document.docx
    └── fin_shading_study_summary.docx
```

### The Two Morphing Methods

#### Method 1: Belcher Normal Shift (`belcher_morpher.py`)

Three operations applied to baseline hourly data using monthly change factors:

| Operation | Formula | Used For |
|---|---|---|
| Shift | `x' = x + Δx` | Atmospheric pressure |
| Stretch | `x' = x × α` | Solar radiation, wind speed, precipitation, RH |
| Shift+Stretch | `x' = x + Δx + α(x - x̄)` | Dry bulb temperature, dew point temperature |

#### Method 2: BTWS (`btws_morpher.py`)

Operates on daily (24-hour) arrays with bounded normalization:

1. Normalize to [0,1]: `x = (T - Tmin) / (Tmax - Tmin)`
2. Transfer function: `g = x^m · (1-x)^n`
3. Scaling factor: `S = [(T'mean - T'min)/(T'max - T'min)] × [(Tmax - Tmin)/(Tmean - Tmin)] - 1`
4. Bounded transform: `x' = x + (S · x̄ · g) / ḡ`
5. Denormalize: `T' = T'min + x' · (T'max - T'min)`

Includes a **tropical climate guard**: when diurnal temperature range < 1°C (common in Bangkok monsoon), falls back to simple shift to prevent numerical instability.

### Orchestrator (`epw_morphing_engine.py`)

Coordinates the full pipeline:
1. Reads baseline `.epw` file (8 header lines + 8,760 hourly data rows)
2. Loads monthly climate deltas from CSV
3. Dispatches to either `belcher` or `btws` method per variable
4. Applies post-morphing psychrometric consistency check (dew point ≤ dry bulb)
5. Writes the morphed `.epw` file

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Target city** | Bangkok only | Thesis site; optimize for Bangkok's specific climate |
| **SSP scenarios** | All four (SSP1-2.6 through SSP5-8.5) | Show full spectrum of futures |
| **Language** | Python | Existing morpher code; Rhino 8 CPython support; numpy for math |
| **Delivery** | Python scripts + GHPython components in Grasshopper | Scripts for batch processing/validation; GH for design integration |
| **GCM source** | Single GCM (UKESM1-0-LL via WorldClim) | Matches Hamann paper; sufficient for thesis scope |
| **Delta format** | Pre-calculated CSV | Downloaded from WorldClim GeoTIFFs offline, stored as simple CSV |
| **Solar fix** | Yes — co-morph GHI/DNI/DHI | Critical for UTCI accuracy (MRT depends on all three) |
| **Validation benchmark** | CURA-lab morphed EPW (Normal Shift, 2070, SSP5-8.5) | Already available; ground truth for Belcher method comparison |

---

## Validation Strategy

The tool must produce **five validation outputs** when comparing baseline, our Belcher, our BTWS, and the CURA-lab reference EPW:

1. **Monthly mean comparison charts** — baseline vs Belcher vs BTWS vs CURA-lab for DBT, GHR, RH, Wind Speed
2. **Hourly scatter/distribution plots** — showing how the temperature distribution shifts under each method
3. **UTCI re-run comparison** — run Ladybug UTCI on all three morphed EPWs, compare the floor shift values
4. **Solar consistency validation** — check that DHI ≤ GHI at every hour and report DNI recalculation error rate
5. **Statistical summary table** — min/mean/max per variable per month, with delta from baseline

---

## Development Phases (from `Morphing_Tool_Development_Plan.md`)

| Phase | Goal | Status |
|---|---|---|
| **Phase 1** — EPW Data Engine | Read, parse, and write `.epw` files | ✅ Done (`epw_morphing_engine.py`) |
| **Phase 2** — Morphing Algorithms | Implement both Belcher and BTWS | ✅ Done (`belcher_morpher.py`, `btws_morpher.py`) |
| **Phase 3** — Solar Physics Correction | Co-morph GHI/DNI/DHI to maintain `GHI = DNI·cos(θ) + DHI` | 🔲 Not started |
| **Phase 4** — Integration & Validation | GH components, delta CSV, comparison charts, UTCI handoff | 🔲 Not started |

---

## Coding Rules

- **Language:** Python 3. Use numpy for array math. No unnecessary dependencies.
- **EPW format:** Preserve the exact 8-line header structure. Data rows are comma-separated, 35+ fields. Do not alter field order or header format.
- **Documentation:** Every morpher method must include the equation number from the source paper (Eames 2024 / Belcher 2005) in its docstring.
- **Physical constraints:** Always enforce after morphing:
  - Dew point temperature ≤ Dry bulb temperature
  - Relative humidity ∈ [0, 100]%
  - Solar radiation ≥ 0 Wh/m²
  - Wind speed ≥ 0 m/s
  - Precipitation ≥ 0 mm
  - DHI ≤ GHI (after solar fix is implemented)
- **Modularity:** The two morphing methods must remain in **separate files** (`belcher_morpher.py` and `btws_morpher.py`). They are independent — the orchestrator dispatches to either one.
- **Delta CSV:** The monthly delta input format must remain a simple CSV with columns: `month, delta_tas, delta_tasmax, delta_tasmin, alpha_hurs, alpha_rsds, alpha_sfcWind, alpha_pr`. Optional columns can be added but must not break backward compatibility.

---

## References

- Hamann, S. et al. (2025). *Advanced Weather Data Morphing for Future Climate-Based Building Simulation.* ANNSIM 2025.
- Eames, M.E. et al. (2024). *A revised morphing algorithm for creating future weather for building performance evaluation.* BSER&T 45(1), 5–20.
- Belcher, S.E., Hacker, J.N. & Powell, D.S. (2005). *Constructing design weather data for future climates.* BSER&T 26(1), 49–61.
- Jentsch, M.F. (2012). *Technical Reference Manual for CCWeatherGen and CCWorldWeatherGen.*
- Rodrigues, E. et al. (2023). *Future weather generator for building performance research.* Building and Environment 233.
