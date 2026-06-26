# Building a Grasshopper EPW Morphing Tool — Feasibility & Implementation Plan

## Overview

**Yes, it is absolutely possible** to implement the Belcher shift/stretch morphing logic (the same core methodology used by [futureweather.co](https://futureweather.co)) and build a custom Grasshopper tool. This document explains the methodology, architecture, and a step-by-step implementation plan.

---

## What FutureWeather.co Actually Does

FutureWeather.co uses the **Belcher et al. (2005)** morphing methodology with CMIP6 enhancements. The core math is straightforward — three operations applied to baseline EPW hourly data using monthly change factors (deltas) from climate models:

### The Three Morphing Operations

#### 1. Shift (Absolute Change)
Used when the climate model provides an absolute change (e.g., temperature in °C).

$$x' = x + \Delta x_m$$

- $x$ = original hourly value
- $\Delta x_m$ = monthly mean absolute change from GCM
- **Used for:** Atmospheric pressure, some temperature applications

#### 2. Stretch (Fractional/Percentage Change)
Used when the climate model provides a proportional change.

$$x' = x \cdot \alpha_m$$

- $\alpha_m$ = fractional change factor (e.g., 1.15 = +15%)
- **Used for:** Solar radiation, wind speed, precipitation

#### 3. Shift + Stretch (Combined)
Used to adjust both the mean and variance of a variable.

$$x' = x + \Delta x_m + \alpha_m \cdot (x - \bar{x}_m)$$

- $\bar{x}_m$ = monthly mean of the baseline time series
- $\Delta x_m$ = absolute shift in the mean
- $\alpha_m$ = scaling factor for the variance
- **Used for:** Dry bulb temperature (primary method), dew point temperature

### Which Operation for Which Variable

| EPW Variable | Morphing Operation | Change Factor Source |
|---|---|---|
| **Dry Bulb Temperature** | Shift + Stretch | $\Delta T_{mean}$, $\alpha_m$ from diurnal range change |
| **Dew Point Temperature** | Shift + Stretch | Derived from humidity change |
| **Relative Humidity** | Stretch | Fractional change in specific humidity |
| **Wind Speed** | Stretch | Fractional change $\alpha_m$ |
| **Global Horizontal Radiation** | Stretch | Fractional change $\alpha_m$ |
| **Precipitation** | Stretch | Fractional change $\alpha_m$ |
| **Atmospheric Pressure** | Shift | $\Delta P_m$ (usually negligible) |

> [!NOTE]
> FutureWeather.co adds **tail amplification** on top of this — scaling individual percentiles rather than just shifting the monthly mean — to better represent extreme weather hours. This is an enhancement you could add later but is not essential for a working first version.

---

## Architecture: How to Build It in Grasshopper

### Two Approaches

| Approach | Pros | Cons |
|---|---|---|
| **A. GHPython Script Component** | Full control, no plugins needed, portable | Must write all EPW parsing logic |
| **B. Ladybug + GHPython Hybrid** | Ladybug handles EPW I/O, you focus on morphing math | Requires Ladybug Tools installed |

**Recommended: Approach B (Ladybug + GHPython Hybrid)** — Ladybug already solves the hardest part (parsing/writing EPW files correctly). You focus purely on the morphing math.

### Component Architecture on the Grasshopper Canvas

```
┌─────────────────────────────────────────────────────────────────┐
│                    GRASSHOPPER CANVAS                           │
│                                                                 │
│  ┌──────────────┐                                               │
│  │  LB Import   │──▶ epw_obj                                    │
│  │  EPW File    │                                               │
│  └──────────────┘       ┌─────────────────────────┐             │
│                         │                         │             │
│  ┌──────────────┐       │   GHPython Component    │             │
│  │  Panel:      │──▶    │   "EPW_MORPHER"         │             │
│  │  Delta CSV   │       │                         │  ┌────────┐ │
│  │  File Path   │       │  Inputs:                │  │ LB     │ │
│  └──────────────┘       │   - epw_obj             │──▶│ Export │ │
│                         │   - delta_csv_path      │  │ EPW    │ │
│  ┌──────────────┐       │   - ssp_scenario        │  └────────┘ │
│  │  Value List: │──▶    │   - target_year         │             │
│  │  SSP126/245/ │       │                         │             │
│  │  370/585     │       │  Outputs:               │             │
│  └──────────────┘       │   - morphed_epw_obj     │             │
│                         │   - summary_text        │             │
│  ┌──────────────┐       │   - temp_comparison     │             │
│  │  Value List: │──▶    │   - validation_report   │             │
│  │  2030/2050/  │       │                         │             │
│  │  2070/2090   │       └─────────────────────────┘             │
│  └──────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Step 1: Prepare the Monthly Delta CSV

You need 12 monthly change factors. These can be:
- **Pre-calculated** from WorldClim CMIP6 data (future − historical)
- **Manually extracted** from published IPCC data for Thailand
- **Downloaded** from the Copernicus Climate Data Store

The CSV format:

```csv
month,delta_tas,delta_tasmax,delta_tasmin,alpha_hurs,alpha_rsds,alpha_sfcWind,alpha_pr
1,1.8,2.1,1.5,0.97,1.02,0.98,0.85
2,2.0,2.3,1.7,0.96,1.03,0.97,0.80
3,2.2,2.6,1.9,0.95,1.01,0.99,0.75
4,2.5,2.9,2.2,0.93,0.98,1.01,0.70
5,2.3,2.7,2.0,0.94,0.97,1.02,1.10
6,2.1,2.5,1.8,0.95,0.96,1.03,1.15
7,2.0,2.4,1.7,0.96,0.95,1.02,1.20
8,2.0,2.3,1.8,0.96,0.96,1.01,1.18
9,1.9,2.2,1.6,0.97,0.98,1.00,1.12
10,1.8,2.1,1.5,0.97,1.00,0.99,1.05
11,1.7,2.0,1.4,0.98,1.01,0.98,0.90
12,1.7,1.9,1.4,0.98,1.02,0.98,0.88
```

Where:
- `delta_tas` = change in mean temperature (°C)
- `delta_tasmax` / `delta_tasmin` = change in max/min temperature (°C)
- `alpha_*` = fractional multipliers (1.0 = no change, 1.15 = +15%)

### Step 2: The Core GHPython Morphing Script

```python
"""EPW Morphing Tool - Belcher Shift/Stretch Method
Inputs:
    epw_obj: Ladybug EPW object (from LB Import EPW)
    delta_csv: Path to monthly deltas CSV file
Output:
    morphed_epw: Modified EPW object ready for export
    report: Summary of changes applied
"""
import csv
import math
from copy import deepcopy

# ── 1. Read Deltas ──────────────────────────────────────────────
deltas = {}
with open(delta_csv, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        m = int(row['month'])
        deltas[m] = {
            'delta_tas':    float(row['delta_tas']),
            'delta_tasmax': float(row['delta_tasmax']),
            'delta_tasmin': float(row['delta_tasmin']),
            'alpha_hurs':   float(row['alpha_hurs']),
            'alpha_rsds':   float(row['alpha_rsds']),
            'alpha_sfcWind': float(row['alpha_sfcWind']),
            'alpha_pr':     float(row['alpha_pr']),
        }

# ── 2. Clone the EPW object ────────────────────────────────────
morphed_epw = deepcopy(epw_obj)

# ── 3. Morph Dry Bulb Temperature (Shift + Stretch) ────────────
dbt = morphed_epw.dry_bulb_temperature
for i, val in enumerate(dbt):
    month = (i // 730) + 1  # approximate month from hour index
    if month > 12: month = 12
    d = deltas[month]
    
    # Shift + Stretch: x' = x + delta_mean + alpha * (x - x_bar)
    # where alpha = (delta_max - delta_min) / (original diurnal range)
    # Simplified: apply mean shift (good first approximation)
    dbt[i] = val + d['delta_tas']

# ── 4. Morph Dew Point Temperature (Shift) ─────────────────────
dpt = morphed_epw.dew_point_temperature
for i, val in enumerate(dpt):
    month = (i // 730) + 1
    if month > 12: month = 12
    # Approximate: shift dew point by same delta as dry bulb
    dpt[i] = val + deltas[month]['delta_tas'] * 0.8

# ── 5. Morph Relative Humidity (Stretch) ────────────────────────
rh = morphed_epw.relative_humidity
for i, val in enumerate(rh):
    month = (i // 730) + 1
    if month > 12: month = 12
    rh[i] = max(0, min(100, val * deltas[month]['alpha_hurs']))

# ── 6. Morph Global Horizontal Radiation (Stretch) ─────────────
ghr = morphed_epw.global_horizontal_radiation
for i, val in enumerate(ghr):
    month = (i // 730) + 1
    if month > 12: month = 12
    ghr[i] = max(0, val * deltas[month]['alpha_rsds'])

# ── 7. Morph Wind Speed (Stretch) ──────────────────────────────
ws = morphed_epw.wind_speed
for i, val in enumerate(ws):
    month = (i // 730) + 1
    if month > 12: month = 12
    ws[i] = max(0, val * deltas[month]['alpha_sfcWind'])

# ── 8. Generate Report ─────────────────────────────────────────
report = "EPW Morphing Complete\n"
report += "=" * 40 + "\n"
for m in range(1, 13):
    d = deltas[m]
    report += "Month {:2d}: dT={:+.1f}°C  RH×{:.2f}  GHR×{:.2f}  WS×{:.2f}\n".format(
        m, d['delta_tas'], d['alpha_hurs'], d['alpha_rsds'], d['alpha_sfcWind']
    )
```

> [!IMPORTANT]
> The script above is a **simplified starter version** using pure Shift for temperature. For the full Shift+Stretch (which adjusts both mean and variance), you would integrate the `BTWSMorpher` class from your existing [btws_morpher.py](file:///C:/Users/9w3n/Desktop/Topic%20Research/00_Repo/Weather-Data-Morphing/btws_morpher.py) — or use the simpler Belcher shift+stretch formula: $x' = x + \Delta x_m + \alpha_m \cdot (x - \bar{x}_m)$.

### Step 3: Validate & Export

After morphing, connect the output to:
1. **LB Export EPW** — writes the morphed `.epw` file
2. **LB Hourly Plot** — visual comparison of baseline vs morphed data
3. **LB UTCI Map** — direct thermal comfort assessment

---

## What You'd Need to Source

| Item | Source | Notes |
|---|---|---|
| **Baseline EPW file** | [Ladybug EPW Map](https://www.ladybug.tools/epwmap/) | Bangkok TMYx available |
| **Monthly climate deltas** | [WorldClim CMIP6](https://worldclim.org/data/cmip6/cmip6climate.html) | Download future + historical GeoTIFFs, calculate delta at Bangkok coordinates |
| **Alternative deltas** | [Copernicus CDS](https://cds.climate.copernicus.eu/) | API access, more GCMs available |
| **Ladybug Tools** | [food4rhino](https://www.food4rhino.com/en/app/ladybug-tools) | Required for EPW I/O in Grasshopper |

---

## Comparison: Your Custom Tool vs FutureWeather.co

| Feature | FutureWeather.co | Your Custom GH Tool |
|---|---|---|
| Core method | Belcher shift/stretch + tail amplification | Belcher shift/stretch (+ BTWS option) |
| GCMs | 23 CMIP6 models (ensemble) | Start with 1, expandable |
| EPW I/O | Built-in | Via Ladybug Tools |
| Cost | Credits-based (~$5/file) | Free (your own compute) |
| Transparency | Closed source | Fully transparent & modifiable |
| Thailand-specific tweaks | None | You can add psychrometric checks, humidity guards |
| Integration | Separate step → import EPW | **Native on the GH canvas** — direct to simulation |
| BTWS advanced morphing | No (standard Belcher only) | Yes, via your existing `btws_morpher.py` |

---

## Recommended Development Phases

### Phase 1: Minimum Viable Morpher *(1–2 weeks)*
- GHPython component reading a delta CSV
- Simple shift for temperature, stretch for other variables
- Export morphed EPW via Ladybug
- Visual comparison charts

### Phase 2: Full Belcher Shift+Stretch *(1 week)*
- Implement the combined formula for temperature
- Proper month-hour mapping (not approximate)
- Psychrometric consistency check (dew point ≤ dry bulb)

### Phase 3: BTWS Integration *(1 week)*
- Port your existing `BTWSMorpher` class into the GHPython component
- Apply BTWS for temperature and GHI
- Add the solar radiation correction (co-morph GHI/DNI/DHI)

### Phase 4: Multi-GCM & Polish *(2 weeks)*
- Support multiple GCM delta files, compute ensemble mean
- Add statistical percentiles (p10, p50, p90)
- Package as a reusable Grasshopper cluster or `.ghuser` component

---

## Conclusion

Building your own Grasshopper morphing tool is not only possible — it gives you significant advantages over futureweather.co for your specific use case:

1. **Free and transparent** — no per-file costs, full control over the math
2. **Thailand-optimized** — you can add the tropical climate guards identified in the [BTWS analysis](file:///C:/Users/9w3n/Desktop/Topic%20Research/00_Repo/Weather-Data-Morphing/applybtwsforthailandclimate.md)
3. **Native GH integration** — morphed data flows directly into your Ladybug/Honeybee simulation pipeline without leaving the canvas
4. **BTWS capability** — you already have the advanced algorithm implemented in [btws_morpher.py](file:///C:/Users/9w3n/Desktop/Topic%20Research/00_Repo/Weather-Data-Morphing/btws_morpher.py), which futureweather.co does not offer

The core Belcher math is simple enough that a working prototype can be built in a few days. The complexity lies in data sourcing (getting good CMIP6 deltas for Bangkok) and validation — not in the morphing algorithm itself.
