# Delta Improvement Method — Fixing the Identical CSV Files

## The Problem

All 8 delta files in `data/deltas/` are byte-identical copies. Every scenario from SSP1-2.6/2050 to SSP5-8.5/2070 produces the same morphed EPW, making multi-scenario comparison meaningless.

```
bangkok_ssp126_2050.csv  ← identical
bangkok_ssp126_2070.csv  ← identical
bangkok_ssp245_2050.csv  ← identical
bangkok_ssp245_2070.csv  ← identical
bangkok_ssp370_2050.csv  ← identical
bangkok_ssp370_2070.csv  ← identical
bangkok_ssp585_2050.csv  ← identical
bangkok_ssp585_2070.csv  ← identical
```

The only file with real, differentiated data is `derived_cura_deltas.csv`, which was reverse-engineered from the CURA-lab benchmark EPW (SSP5-8.5, 2070).

---

## The Data Sourcing Problem

> **WARNING: WorldClim CMIP6 does NOT provide future projections for all the variables we need.**
>
> WorldClim future data only includes: `tmin`, `tmax`, and `prec` (precipitation).
> It does **not** include: `srad` (solar radiation), `wind` (wind speed), or `vapr` (vapor pressure/humidity).
>
> These three variables are only available in the WorldClim **historical** baseline (1970–2000), not in any future SSP projection.

This means we need a **two-tier sourcing strategy**.

---

## Sourcing Strategy

### Tier 1: WorldClim CMIP6 (Temperature + Precipitation)

| Variable | WorldClim Code | What We Extract | Delta Type |
|---|---|---|---|
| Monthly mean min temp | `tmin` | `delta_tasmin` = future − historical | Absolute shift (°C) |
| Monthly mean max temp | `tmax` | `delta_tasmax` = future − historical | Absolute shift (°C) |
| Monthly mean temp | derived | `delta_tas` = (tmin+tmax)/2 future − (tmin+tmax)/2 historical | Absolute shift (°C) |
| Monthly precipitation | `prec` | `alpha_pr` = future / historical | Ratio (dimensionless) |

**Source:** `https://geodata.ucdavis.edu/cmip6/10m/UKESM1-0-LL/`

**File naming convention:**
```
wc2.1_10m_tmin_UKESM1-0-LL_ssp585_2061-2080.tif   ← future tmin
wc2.1_10m_tmax_UKESM1-0-LL_ssp585_2061-2080.tif   ← future tmax
wc2.1_10m_prec_UKESM1-0-LL_ssp585_2061-2080.tif   ← future precip
```

**Historical baseline** (shared across all SSPs):
```
wc2.1_10m_tmin.tif   ← from https://geodata.ucdavis.edu/climate/worldclim/2_1/base/
wc2.1_10m_tmax.tif
wc2.1_10m_prec.tif
```

Each `.tif` is a **multi-band GeoTIFF** with 12 bands (one per month).

**Downloads required for Tier 1:**
- 1 × historical tmin + 1 × historical tmax + 1 × historical prec = **3 files**
- 8 × future tmin + 8 × future tmax + 8 × future prec = **24 files**
- Total: **27 downloads** (~10–50 MB each)

### Tier 2: Copernicus CDS (Solar Radiation, Wind Speed, Humidity)

WorldClim doesn't provide future solar/wind/humidity, but the **Copernicus Climate Data Store (CDS)** does, via the dataset:

> **"CMIP6 climate projections — monthly averages"**
> `projections-cmip6` on CDS

This provides monthly mean values from UKESM1-0-LL for:

| Variable | CMIP6 Name | What We Extract | Delta Type |
|---|---|---|---|
| Surface downwelling shortwave radiation | `rsds` | `alpha_rsds` = future / historical | Ratio |
| Near-surface wind speed | `sfcWind` | `alpha_sfcWind` = future / historical | Ratio |
| Near-surface relative humidity | `hurs` | `alpha_hurs` = future / historical | Ratio |

**Access:** Requires a free CDS account + API key. Data is requested via the CDS API (Python `cdsapi` package) as NetCDF files, which are then point-extracted for Bangkok.

### Tier 2 — Fallback: Scale from CURA-lab Derived Deltas

If CDS access is too slow or impractical, we can use a **physically-grounded approximation**:

We already have real solar/wind/humidity deltas for **one known scenario** (SSP5-8.5 at 2070) from `derived_cura_deltas.csv`. We can scale these to other scenarios using the **temperature ratio** as a proxy.

The logic:
1. The CURA-lab deltas tell us that SSP5-8.5/2070 has `delta_tas ≈ 3.0°C` and `alpha_rsds ≈ 1.02`
2. If SSP1-2.6/2050 has `delta_tas ≈ 0.8°C` from WorldClim, that's ~27% of the SSP5-8.5/2070 warming
3. Scale the non-temperature deltas proportionally: `alpha_rsds ≈ 1 + 0.27 × (1.02 − 1) = 1.005`

This is an approximation, but it's physically defensible because:
- Solar radiation changes are driven by cloud cover changes, which correlate with temperature forcing
- Wind speed changes are driven by pressure gradient changes, which scale with warming magnitude
- Humidity changes are thermodynamically linked to temperature via Clausius-Clapeyron

> **Recommendation:** Use the fallback for the thesis. The approximation is good enough for the comparative analysis, and it avoids a complex multi-day CDS data pipeline. Note the limitation in the thesis methodology section.

---

## Extraction Math — Per Variable

### Temperature Deltas (from WorldClim GeoTIFFs)

For each month `m` (bands 1–12 in the GeoTIFF):

```python
# Read the pixel value at Bangkok (13.7264°N, 100.56°E)
hist_tmin[m] = historical_tmin_raster.sample(lat=13.7264, lon=100.56, band=m)
hist_tmax[m] = historical_tmax_raster.sample(lat=13.7264, lon=100.56, band=m)
fut_tmin[m]  = future_tmin_raster.sample(lat=13.7264, lon=100.56, band=m)
fut_tmax[m]  = future_tmax_raster.sample(lat=13.7264, lon=100.56, band=m)

# Calculate deltas
delta_tasmin[m] = fut_tmin[m] - hist_tmin[m]
delta_tasmax[m] = fut_tmax[m] - hist_tmax[m]
delta_tas[m]    = ((fut_tmin[m] + fut_tmax[m]) / 2) - ((hist_tmin[m] + hist_tmax[m]) / 2)
```

### Precipitation Alpha (from WorldClim GeoTIFFs)

```python
hist_prec[m] = historical_prec_raster.sample(lat=13.7264, lon=100.56, band=m)
fut_prec[m]  = future_prec_raster.sample(lat=13.7264, lon=100.56, band=m)

# Ratio (guard against zero baseline)
alpha_pr[m] = fut_prec[m] / hist_prec[m]  if hist_prec[m] > 0  else 1.0
```

### Solar, Wind, Humidity Alphas (Fallback Method)

Using CURA-lab SSP5-8.5/2070 as the anchor:

```python
# Reference: CURA-lab derived deltas (SSP5-8.5, 2070)
cura_delta_tas[m]     = derived_cura_deltas['delta_tas'][m]        # ~3.0°C
cura_alpha_rsds[m]    = derived_cura_deltas['alpha_rsds'][m]       # ~1.02
cura_alpha_sfcWind[m] = derived_cura_deltas['alpha_sfcWind'][m]    # ~1.05
cura_alpha_hurs[m]    = derived_cura_deltas['alpha_hurs'][m]       # ~0.96

# Scale factor: how does this scenario's warming compare to SSP5-8.5/2070?
scale[m] = delta_tas[m] / cura_delta_tas[m]    # e.g., 0.8 / 3.0 = 0.27

# Apply proportional scaling (1.0 = no change baseline)
alpha_rsds[m]    = 1.0 + scale[m] * (cura_alpha_rsds[m] - 1.0)
alpha_sfcWind[m] = 1.0 + scale[m] * (cura_alpha_sfcWind[m] - 1.0)
alpha_hurs[m]    = 1.0 + scale[m] * (cura_alpha_hurs[m] - 1.0)
```

### Humidity — Detailed Derivation (if using CDS data instead of fallback)

If sourcing vapor pressure from CDS:

```python
# Tetens formula for saturation vapor pressure
def e_sat(T_celsius):
    return 0.6108 * exp(17.27 * T / (T + 237.3))   # kPa

# Historical and future RH
hist_rh[m] = (hist_vapr[m] / e_sat(hist_tavg[m])) * 100
fut_rh[m]  = (fut_vapr[m]  / e_sat(fut_tavg[m]))  * 100

alpha_hurs[m] = fut_rh[m] / hist_rh[m]
```

This captures the Clausius-Clapeyron effect: even if absolute humidity increases, *relative* humidity can decrease because warmer air's saturation point rises faster.

---

## Expected Output — How the Files Should Differ

After fixing, the delta files should look approximately like this (January example):

| File | `delta_tas` | `delta_tasmax` | `delta_tasmin` | `alpha_rsds` | `alpha_sfcWind` | `alpha_hurs` |
|---|---|---|---|---|---|---|
| SSP1-2.6 / 2050 | +0.7 | +0.8 | +0.6 | 1.003 | 1.012 | 0.990 |
| SSP1-2.6 / 2070 | +0.9 | +1.1 | +0.8 | 1.004 | 1.016 | 0.987 |
| SSP2-4.5 / 2050 | +1.1 | +1.3 | +0.9 | 1.005 | 1.019 | 0.983 |
| SSP2-4.5 / 2070 | +1.7 | +2.0 | +1.4 | 1.008 | 1.030 | 0.974 |
| SSP3-7.0 / 2050 | +1.3 | +1.5 | +1.1 | 1.006 | 1.022 | 0.980 |
| SSP3-7.0 / 2070 | +2.3 | +2.7 | +2.0 | 1.010 | 1.040 | 0.966 |
| SSP5-8.5 / 2050 | +1.6 | +1.9 | +1.3 | 1.007 | 1.027 | 0.976 |
| **SSP5-8.5 / 2070** | **+3.1** | **+3.1** | **+3.2** | **1.013** | **1.059** | **0.949** |

*(Last row matches the real CURA-lab derived deltas as a sanity check.)*

The key pattern: **higher SSP + further future = larger deltas**, as expected.

---

## Script Architecture

One Python script: `extract_worldclim_deltas.py`, placed in the project root.

```
extract_worldclim_deltas.py
│
├── Step 0: Create data/worldclim/ directory for raw downloads
│
├── Step 1: Download WorldClim GeoTIFFs
│   ├── Historical: tmin, tmax, prec (3 files, ~150 MB)
│   └── Future: 4 SSPs × 2 periods × 3 vars (24 files, ~1.2 GB)
│
├── Step 2: Extract Bangkok pixel values
│   ├── Open each GeoTIFF with rasterio (or GDAL)
│   ├── Sample at (13.7264°N, 100.56°E) for all 12 bands
│   └── Store in a dict: {ssp}_{period} → {month → {tmin, tmax, prec}}
│
├── Step 3: Calculate temperature and precipitation deltas
│   ├── delta_tas    = (fut_tmin + fut_tmax)/2 − (hist_tmin + hist_tmax)/2
│   ├── delta_tasmax = fut_tmax − hist_tmax
│   ├── delta_tasmin = fut_tmin − hist_tmin
│   └── alpha_pr     = fut_prec / hist_prec
│
├── Step 4: Scale solar/wind/humidity from CURA-lab anchor
│   ├── Load derived_cura_deltas.csv
│   ├── For each scenario, compute scale = delta_tas / cura_delta_tas
│   └── alpha_x = 1 + scale × (cura_alpha_x − 1)
│
├── Step 5: Write 8 CSV files to data/deltas/
│   └── Each with correct, unique, scenario-specific values
│
└── Step 6: Print summary comparison table
```

### Dependencies

```
rasterio       ← for reading GeoTIFFs (pip install rasterio)
numpy          ← already in use
requests       ← for downloading files (stdlib-adjacent)
```

> **Note:** `rasterio` requires GDAL. On Windows, the easiest install is via:
> ```
> pip install rasterio
> ```
> or if that fails:
> ```
> conda install -c conda-forge rasterio
> ```

---

## Validation

After generating the new delta files, we verify by:

1. **Monotonicity check**: For each month, `delta_tas` should increase as SSP severity increases (126 < 245 < 370 < 585) and as time advances (2050 < 2070)
2. **CURA-lab match**: The SSP5-8.5/2070 file should produce nearly identical results to `derived_cura_deltas.csv` for temperature — any deviation would indicate a WorldClim data problem
3. **Physical bounds**:
   - All `alpha_*` values should be positive
   - `alpha_hurs` should generally be ≤ 1.0 (RH decreases under warming in the tropics)
   - Temperature deltas should be positive (Bangkok gets warmer under all SSPs)
4. **Re-run morphing engine**: Morph with each of the 8 new delta files and confirm the output EPWs now show meaningfully different temperature distributions

---

## File Changes Summary

| File | Action |
|---|---|
| `extract_worldclim_deltas.py` | **Create** — new script in project root |
| `data/worldclim/` | **Create** — directory for downloaded GeoTIFFs |
| `data/deltas/bangkok_ssp126_2050.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp126_2070.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp245_2050.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp245_2070.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp370_2050.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp370_2070.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp585_2050.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/bangkok_ssp585_2070.csv` | **Overwrite** with real extracted deltas |
| `data/deltas/derived_cura_deltas.csv` | **Keep unchanged** — validation anchor |
