"""
extract_worldclim_deltas.py — WorldClim CMIP6 Delta Extraction
================================================================
Downloads WorldClim CMIP6 GeoTIFFs for UKESM1-0-LL, extracts pixel
values at Bangkok coordinates, calculates monthly climate deltas for
8 SSP x time-period combinations, and writes corrected CSV files.

Temperature + Precipitation: extracted directly from WorldClim GeoTIFFs
Solar / Wind / Humidity:     scaled from CURA-lab derived deltas (fallback)

See docs/deltaimprovementmethod.md for full methodology.

Usage:
    python extract_worldclim_deltas.py

Dependencies:
    numpy, requests, tifffile  (pip install tifffile)
"""

import os
import sys
import csv
import zipfile
import io
import math
from pathlib import Path

import numpy as np

try:
    import requests
except ImportError:
    print("ERROR: requests is required. Install with: pip install requests")
    sys.exit(1)

try:
    import tifffile
except ImportError:
    print("ERROR: tifffile is required. Install with: pip install tifffile")
    print("  (This is a lightweight GeoTIFF reader — no GDAL required)")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════

BANGKOK_LAT = 13.7264
BANGKOK_LON = 100.5600

RESOLUTION = "10m"
GCM = "UKESM1-0-LL"

SSPS = ["ssp126", "ssp245", "ssp370", "ssp585"]
PERIODS = {
    "2050": "2041-2060",
    "2070": "2061-2080",
}
# WorldClim CMIP6 at 10m only provides: tmin, tmax, prec
# (srad, wind, vapr are NOT available for future projections)
VARIABLES = ["tmin", "tmax", "prec"]

# Directories (relative to this script)
BASE_DIR = Path(__file__).resolve().parent
WORLDCLIM_DIR = BASE_DIR / "data" / "worldclim"
DELTAS_DIR = BASE_DIR / "data" / "deltas"
CURA_DELTAS_PATH = DELTAS_DIR / "derived_cura_deltas.csv"

# WorldClim URL templates
# Historical baseline (1970-2000):
#   https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_{var}.tif
# Future CMIP6:
#   https://geodata.ucdavis.edu/cmip6/10m/UKESM1-0-LL/ssp585/
#     wc2.1_10m_{var}_UKESM1-0-LL_ssp585_2061-2080.tif
HIST_URL_TEMPLATE = (
    "https://geodata.ucdavis.edu/climate/worldclim/2_1/base/"
    "wc2.1_{res}_{var}.tif"
)
FUTURE_URL_TEMPLATE = (
    "https://geodata.ucdavis.edu/cmip6/{res}/{gcm}/{ssp}/"
    "wc2.1_{res}_{var}_{gcm}_{ssp}_{period}.tif"
)


# ══════════════════════════════════════════════════════════════════
# STEP 0: DIRECTORY SETUP
# ══════════════════════════════════════════════════════════════════

def setup_directories():
    """Creates data/worldclim/ subdirectories if they don't exist."""
    dirs = [
        WORLDCLIM_DIR / "historical",
    ]
    for ssp in SSPS:
        for label, period in PERIODS.items():
            dirs.append(WORLDCLIM_DIR / f"{ssp}_{period}")

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        
    print(f"✓ Directory structure ready: {WORLDCLIM_DIR}")


# ══════════════════════════════════════════════════════════════════
# STEP 1: DOWNLOAD GEOTIFFS
# ══════════════════════════════════════════════════════════════════

def download_file(url, dest_path):
    """
    Downloads a file from URL to dest_path.
    Tries .tif first, then .zip if .tif returns 404.
    Skips if file already exists.
    Returns the path to the usable .tif file.
    """
    tif_path = Path(dest_path)

    # Skip if already downloaded
    if tif_path.exists() and tif_path.stat().st_size > 0:
        print(f"  ○ Already exists: {tif_path.name}")
        return tif_path

    # Try direct .tif download first
    print(f"  ↓ Downloading: {tif_path.name} ...")
    try:
        resp = requests.get(url, stream=True, timeout=120)
        if resp.status_code == 200:
            with open(tif_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            size_mb = tif_path.stat().st_size / (1024 * 1024)
            print(f"    ✓ Downloaded ({size_mb:.1f} MB)")
            return tif_path
        elif resp.status_code == 404:
            print(f"    → .tif not found (404), trying .zip ...")
        else:
            print(f"    ✗ HTTP {resp.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Download failed: {e}")
        # Fall through to try .zip

    # Try .zip version
    zip_url = url.replace(".tif", ".zip")
    try:
        resp = requests.get(zip_url, stream=True, timeout=120)
        if resp.status_code == 200:
            zip_data = io.BytesIO(resp.content)
            zip_path = tif_path.with_suffix('.zip')
            with open(zip_path, 'wb') as f:
                f.write(resp.content)
            
            # Extract the .tif from the .zip
            with zipfile.ZipFile(zip_data) as zf:
                tif_names = [n for n in zf.namelist() if n.endswith('.tif')]
                if tif_names:
                    # Extract the first (or only) .tif
                    extracted = zf.extract(tif_names[0], tif_path.parent)
                    extracted_path = Path(extracted)
                    # Rename to expected name if different
                    if extracted_path != tif_path:
                        if tif_path.exists():
                            tif_path.unlink()
                        extracted_path.rename(tif_path)
                    size_mb = tif_path.stat().st_size / (1024 * 1024)
                    print(f"    ✓ Extracted from .zip ({size_mb:.1f} MB)")
                    return tif_path
                else:
                    print(f"    ✗ No .tif found inside .zip")
                    return None
        else:
            print(f"    ✗ .zip also not found (HTTP {resp.status_code})")
            return None
    except requests.exceptions.RequestException as e:
        print(f"    ✗ .zip download failed: {e}")
        return None


def download_historical():
    """Downloads historical baseline GeoTIFFs (1970-2000)."""
    print("\n── Downloading Historical Baseline ──")
    paths = {}
    for var in VARIABLES:
        url = HIST_URL_TEMPLATE.format(res=RESOLUTION, var=var)
        dest = WORLDCLIM_DIR / "historical" / f"wc2.1_{RESOLUTION}_{var}.tif"
        result = download_file(url, dest)
        if result:
            paths[var] = result
        else:
            print(f"  ✗ FAILED: Could not download historical {var}")
    return paths


def download_future():
    """Downloads future projection GeoTIFFs for all SSP×period combos."""
    print("\n── Downloading Future Projections ──")
    paths = {}  # {(ssp, period_label): {var: path}}
    
    for ssp in SSPS:
        for label, period in PERIODS.items():
            key = (ssp, label)
            paths[key] = {}
            print(f"\n  [{ssp.upper()} / {label}] ({period})")
            
            subdir = WORLDCLIM_DIR / f"{ssp}_{period}"
            for var in VARIABLES:
                filename = f"wc2.1_{RESOLUTION}_{var}_{GCM}_{ssp}_{period}.tif"
                url = FUTURE_URL_TEMPLATE.format(
                    res=RESOLUTION, gcm=GCM, ssp=ssp, period=period, var=var
                )
                dest = subdir / filename
                result = download_file(url, dest)
                if result:
                    paths[key][var] = result
                else:
                    print(f"    ✗ FAILED: {filename}")
    return paths


# ══════════════════════════════════════════════════════════════════
# STEP 2: EXTRACT PIXEL VALUES AT BANGKOK
# ══════════════════════════════════════════════════════════════════

def latlon_to_pixel_10m(lat, lon):
    """
    Converts lat/lon to pixel coordinates for WorldClim 10-minute 
    resolution global rasters.
    
    WorldClim 10m rasters cover -180 to 180 lon, -90 to 90 lat,
    at 10 arc-minute (~0.1667°) resolution.
    
    Raster dimensions: 2160 columns × 1080 rows
    Origin: top-left corner at (-180, 90)
    Pixel size: 1/6 degree (10 arc-minutes)
    """
    pixel_size = 10.0 / 60.0  # 10 arc-minutes in degrees = 0.16667°
    
    col = int((lon - (-180.0)) / pixel_size)
    row = int((90.0 - lat) / pixel_size)
    
    return row, col


def extract_monthly_values(tif_path, lat, lon):
    """
    Reads a WorldClim GeoTIFF and extracts 12 monthly values 
    at the given lat/lon coordinates.
    
    WorldClim GeoTIFFs can be:
    - Multi-band (12 bands, one per month) → shape (12, H, W)
    - Single-band → shape (H, W) — unlikely for monthly data
    
    Returns: list of 12 float values (one per month, index 0 = January)
    """
    data = tifffile.imread(str(tif_path))
    row, col = latlon_to_pixel_10m(lat, lon)
    
    if data.ndim == 3:
        # Multi-band: shape is (bands, height, width)
        n_bands = data.shape[0]
        if n_bands != 12:
            print(f"    ⚠ Expected 12 bands, got {n_bands} in {tif_path.name}")
        
        # Clamp to valid range
        row = min(row, data.shape[1] - 1)
        col = min(col, data.shape[2] - 1)
        
        values = [float(data[b, row, col]) for b in range(min(n_bands, 12))]
    elif data.ndim == 2:
        # Single band
        row = min(row, data.shape[0] - 1)
        col = min(col, data.shape[1] - 1)
        values = [float(data[row, col])]
    else:
        raise ValueError(f"Unexpected array shape: {data.shape}")
    
    return values


def extract_all_values(hist_paths, future_paths):
    """
    Extracts pixel values at Bangkok for all downloaded GeoTIFFs.
    
    Returns:
        historical: {var: [12 monthly values]}
        future:     {(ssp, period_label): {var: [12 monthly values]}}
    """
    print("\n── Extracting Bangkok Pixel Values ──")
    print(f"  Coordinates: {BANGKOK_LAT}°N, {BANGKOK_LON}°E")
    row, col = latlon_to_pixel_10m(BANGKOK_LAT, BANGKOK_LON)
    print(f"  Pixel (row, col): ({row}, {col})")
    
    # Historical
    historical = {}
    for var, path in hist_paths.items():
        values = extract_monthly_values(path, BANGKOK_LAT, BANGKOK_LON)
        historical[var] = values
        print(f"  Historical {var}: {[f'{v:.1f}' for v in values]}")
    
    # Future
    future = {}
    for (ssp, label), var_paths in future_paths.items():
        future[(ssp, label)] = {}
        for var, path in var_paths.items():
            values = extract_monthly_values(path, BANGKOK_LAT, BANGKOK_LON)
            future[(ssp, label)][var] = values
        # Print just temperature mean for summary
        if 'tmin' in future[(ssp, label)] and 'tmax' in future[(ssp, label)]:
            tavg = [
                (future[(ssp, label)]['tmin'][m] + future[(ssp, label)]['tmax'][m]) / 2
                for m in range(12)
            ]
            annual_mean = np.mean(tavg)
            print(f"  {ssp.upper()}/{label}: annual mean T = {annual_mean:.1f}°C")
    
    return historical, future


# ══════════════════════════════════════════════════════════════════
# STEP 3: CALCULATE TEMPERATURE + PRECIPITATION DELTAS
# ══════════════════════════════════════════════════════════════════

def calculate_direct_deltas(historical, future):
    """
    Calculates monthly deltas from WorldClim data.
    
    Temperature: delta = future - historical (°C)
    Precipitation: alpha = future / historical (ratio)
    
    Returns: {(ssp, period_label): {month(1-12): {delta_tas, delta_tasmax, 
              delta_tasmin, alpha_pr}}}
    """
    print("\n── Calculating Temperature & Precipitation Deltas ──")
    
    deltas = {}
    
    for (ssp, label), fut_data in future.items():
        deltas[(ssp, label)] = {}
        
        for m in range(12):
            month_num = m + 1  # 1-indexed
            
            # Historical values
            h_tmin = historical['tmin'][m]
            h_tmax = historical['tmax'][m]
            h_tavg = (h_tmin + h_tmax) / 2.0
            h_prec = historical['prec'][m]
            
            # Future values
            f_tmin = fut_data['tmin'][m]
            f_tmax = fut_data['tmax'][m]
            f_tavg = (f_tmin + f_tmax) / 2.0
            f_prec = fut_data['prec'][m]
            
            # Temperature deltas (absolute shift in °C)
            delta_tas = f_tavg - h_tavg
            delta_tasmax = f_tmax - h_tmax
            delta_tasmin = f_tmin - h_tmin
            
            # Precipitation alpha (ratio, guard against zero)
            if h_prec > 0.01:
                alpha_pr = f_prec / h_prec
            else:
                alpha_pr = 1.0
            
            deltas[(ssp, label)][month_num] = {
                'delta_tas': round(delta_tas, 4),
                'delta_tasmax': round(delta_tasmax, 4),
                'delta_tasmin': round(delta_tasmin, 4),
                'alpha_pr': round(alpha_pr, 4),
            }
        
        # Print annual summary
        annual_dtas = np.mean([
            deltas[(ssp, label)][m]['delta_tas'] for m in range(1, 13)
        ])
        print(f"  {ssp.upper()}/{label}: annual mean ΔT = {annual_dtas:+.2f}°C")
    
    return deltas


# ══════════════════════════════════════════════════════════════════
# STEP 4: SCALE SOLAR/WIND/HUMIDITY FROM CURA-LAB ANCHOR
# ══════════════════════════════════════════════════════════════════

def load_cura_deltas():
    """
    Loads the CURA-lab derived deltas (SSP5-8.5, 2070) as the anchor 
    point for scaling non-temperature variables.
    """
    cura = {}
    with open(CURA_DELTAS_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = int(row['month'])
            cura[m] = {
                'delta_tas': float(row['delta_tas']),
                'alpha_rsds': float(row['alpha_rsds']),
                'alpha_sfcWind': float(row['alpha_sfcWind']),
                'alpha_hurs': float(row['alpha_hurs']),
            }
            # Optional: delta_pres
            if 'delta_pres' in row:
                cura[m]['delta_pres'] = float(row['delta_pres'])
    return cura


def scale_from_cura(deltas, cura):
    """
    Scales solar radiation, wind speed, and humidity alphas from the 
    CURA-lab anchor point (SSP5-8.5, 2070) using temperature ratio.
    
    Logic:
        scale_factor = this_scenario_delta_tas / cura_delta_tas
        alpha_x = 1.0 + scale_factor × (cura_alpha_x - 1.0)
    
    This is a physically-grounded approximation: solar/wind/humidity 
    changes correlate with the magnitude of radiative forcing, which 
    scales with temperature change.
    
    See docs/deltaimprovementmethod.md for full justification.
    """
    print("\n── Scaling Solar/Wind/Humidity from CURA-lab Anchor ──")
    
    for (ssp, label), month_deltas in deltas.items():
        for m in range(1, 13):
            d = month_deltas[m]
            c = cura[m]
            
            # Scale factor: how much of SSP5-8.5/2070 warming does 
            # this scenario represent?
            if abs(c['delta_tas']) > 0.01:
                scale = d['delta_tas'] / c['delta_tas']
            else:
                scale = 0.0
            
            # Scale each non-temperature variable
            # alpha_x = 1.0 + scale × (cura_alpha_x - 1.0)
            d['alpha_rsds'] = round(
                1.0 + scale * (c['alpha_rsds'] - 1.0), 4
            )
            d['alpha_sfcWind'] = round(
                1.0 + scale * (c['alpha_sfcWind'] - 1.0), 4
            )
            d['alpha_hurs'] = round(
                1.0 + scale * (c['alpha_hurs'] - 1.0), 4
            )
        
        # Print summary for this scenario
        jan = month_deltas[1]
        print(f"  {ssp.upper()}/{label}: Jan → "
              f"rsds×{jan['alpha_rsds']:.4f}  "
              f"wind×{jan['alpha_sfcWind']:.4f}  "
              f"hurs×{jan['alpha_hurs']:.4f}")
    
    return deltas


# ══════════════════════════════════════════════════════════════════
# STEP 5: WRITE CSV FILES
# ══════════════════════════════════════════════════════════════════

def write_delta_csvs(deltas):
    """Writes 8 delta CSV files, one per SSP×period combination."""
    print("\n── Writing Delta CSV Files ──")
    
    fieldnames = [
        'month', 'delta_tas', 'delta_tasmax', 'delta_tasmin',
        'alpha_hurs', 'alpha_rsds', 'alpha_sfcWind', 'alpha_pr'
    ]
    
    for (ssp, label), month_deltas in deltas.items():
        # Map SSP name to filename convention
        ssp_num = ssp.replace("ssp", "")
        filename = f"bangkok_ssp{ssp_num}_{label}.csv"
        filepath = DELTAS_DIR / filename
        
        rows = []
        for m in range(1, 13):
            d = month_deltas[m]
            rows.append({
                'month': m,
                'delta_tas': d['delta_tas'],
                'delta_tasmax': d['delta_tasmax'],
                'delta_tasmin': d['delta_tasmin'],
                'alpha_hurs': d['alpha_hurs'],
                'alpha_rsds': d['alpha_rsds'],
                'alpha_sfcWind': d['alpha_sfcWind'],
                'alpha_pr': d['alpha_pr'],
            })
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"  ✓ {filename}")


# ══════════════════════════════════════════════════════════════════
# STEP 6: VALIDATION & SUMMARY
# ══════════════════════════════════════════════════════════════════

def validate_and_summarize(deltas):
    """
    Validates the generated deltas and prints a comparison table.
    
    Checks:
    1. Monotonicity: higher SSP → larger delta_tas
    2. Time progression: 2070 > 2050 for same SSP
    3. Physical bounds: alphas positive, hurs ≤ 1.0
    """
    print("\n" + "=" * 70)
    print("VALIDATION & SUMMARY")
    print("=" * 70)
    
    # ── Summary Table ──
    print("\nAnnual Mean Temperature Delta (°C):")
    print(f"  {'Scenario':<20} {'2050':>8} {'2070':>8} {'OK?':>6}")
    print("  " + "-" * 44)
    
    issues = []
    
    for ssp in SSPS:
        vals = {}
        for label in ["2050", "2070"]:
            key = (ssp, label)
            if key in deltas:
                annual = np.mean([
                    deltas[key][m]['delta_tas'] for m in range(1, 13)
                ])
                vals[label] = annual
        
        ok_time = vals.get("2070", 0) >= vals.get("2050", 0)
        status = "✓" if ok_time else "✗"
        if not ok_time:
            issues.append(f"{ssp}: 2070 < 2050 (not monotonic in time)")
        
        print(f"  {ssp.upper():<20} "
              f"{vals.get('2050', float('nan')):>+8.2f} "
              f"{vals.get('2070', float('nan')):>+8.2f} "
              f"{status:>6}")
    
    # ── Monotonicity across SSPs ──
    print("\nMonotonicity Check (SSP126 < SSP245 < SSP370 < SSP585):")
    for label in ["2050", "2070"]:
        annual_vals = []
        for ssp in SSPS:
            key = (ssp, label)
            if key in deltas:
                annual = np.mean([
                    deltas[key][m]['delta_tas'] for m in range(1, 13)
                ])
                annual_vals.append((ssp, annual))
        
        is_monotonic = all(
            annual_vals[i][1] <= annual_vals[i+1][1]
            for i in range(len(annual_vals) - 1)
        )
        status = "✓" if is_monotonic else "✗"
        vals_str = " < ".join(f"{v:.2f}" for _, v in annual_vals)
        print(f"  {label}: {vals_str}  {status}")
        if not is_monotonic:
            issues.append(f"{label}: SSP ordering not monotonic")
    
    # ── Physical Bounds ──
    print("\nPhysical Bounds Check:")
    bound_ok = True
    for (ssp, label), month_deltas in deltas.items():
        for m in range(1, 13):
            d = month_deltas[m]
            if d['alpha_rsds'] < 0:
                issues.append(f"{ssp}/{label} month {m}: alpha_rsds < 0")
                bound_ok = False
            if d['alpha_sfcWind'] < 0:
                issues.append(f"{ssp}/{label} month {m}: alpha_sfcWind < 0")
                bound_ok = False
            if d['alpha_pr'] < 0:
                issues.append(f"{ssp}/{label} month {m}: alpha_pr < 0")
                bound_ok = False
    print(f"  All alphas positive: {'✓' if bound_ok else '✗'}")
    
    # ── Detailed Monthly Table for SSP5-8.5/2070 ──
    print("\nDetailed Monthly Deltas — SSP5-8.5 / 2070 (thesis design scenario):")
    key585 = ("ssp585", "2070")
    if key585 in deltas:
        print(f"  {'Mon':>4} {'Δtas':>7} {'Δtmax':>7} {'Δtmin':>7} "
              f"{'αrsds':>7} {'αwind':>7} {'αhurs':>7} {'αpr':>7}")
        print("  " + "-" * 56)
        for m in range(1, 13):
            d = deltas[key585][m]
            print(f"  {m:>4} {d['delta_tas']:>+7.2f} {d['delta_tasmax']:>+7.2f} "
                  f"{d['delta_tasmin']:>+7.2f} {d['alpha_rsds']:>7.4f} "
                  f"{d['alpha_sfcWind']:>7.4f} {d['alpha_hurs']:>7.4f} "
                  f"{d['alpha_pr']:>7.4f}")
    
    # ── Issues ──
    if issues:
        print(f"\n⚠ {len(issues)} issue(s) found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✓ All validation checks passed!")
    
    print()


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("WorldClim CMIP6 Delta Extraction for Bangkok")
    print(f"GCM: {GCM}")
    print(f"Resolution: {RESOLUTION}")
    print(f"Scenarios: {', '.join(s.upper() for s in SSPS)}")
    print(f"Periods: {', '.join(f'{k} ({v})' for k, v in PERIODS.items())}")
    print("=" * 70)
    
    # Step 0: Setup
    setup_directories()
    
    # Step 1: Download GeoTIFFs
    hist_paths = download_historical()
    future_paths = download_future()
    
    # Check we got the minimum required data
    missing_hist = [v for v in VARIABLES if v not in hist_paths]
    if missing_hist:
        print(f"\n✗ FATAL: Missing historical data for: {missing_hist}")
        print("  Please download manually from:")
        print(f"  https://geodata.ucdavis.edu/climate/worldclim/2_1/base/")
        print(f"  Place .tif files in: {WORLDCLIM_DIR / 'historical'}")
        sys.exit(1)
    
    missing_future = []
    for key, var_paths in future_paths.items():
        missing = [v for v in VARIABLES if v not in var_paths]
        if missing:
            missing_future.append((key, missing))
    if missing_future:
        print(f"\n✗ FATAL: Missing future data:")
        for (ssp, label), missing in missing_future:
            print(f"  {ssp}/{label}: {missing}")
        print("  Please download manually from:")
        print(f"  https://geodata.ucdavis.edu/cmip6/{RESOLUTION}/{GCM}/")
        sys.exit(1)
    
    # Step 2: Extract pixel values
    historical, future = extract_all_values(hist_paths, future_paths)
    
    # Step 3: Calculate temperature + precipitation deltas
    deltas = calculate_direct_deltas(historical, future)
    
    # Step 4: Scale solar/wind/humidity from CURA-lab anchor
    if not CURA_DELTAS_PATH.exists():
        print(f"\n✗ FATAL: CURA-lab anchor file not found: {CURA_DELTAS_PATH}")
        print("  This file is needed to scale solar/wind/humidity deltas.")
        sys.exit(1)
    
    cura = load_cura_deltas()
    deltas = scale_from_cura(deltas, cura)
    
    # Step 5: Write CSV files
    write_delta_csvs(deltas)
    
    # Step 6: Validate and summarize
    validate_and_summarize(deltas)
    
    print("Done! Delta CSV files have been updated in:")
    print(f"  {DELTAS_DIR}")


if __name__ == "__main__":
    main()
