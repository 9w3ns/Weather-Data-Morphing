"""
generate_scaled_deltas.py — Pattern Scaling Fallback
======================================================
Since the UC Davis WorldClim servers are unstable/timing out,
this script generates the 8 scenario delta files using IPCC AR6 
pattern scaling.

It uses the verified `derived_cura_deltas.csv` (SSP5-8.5, 2070) 
as the anchor point and scales the deltas proportionally based on 
the IPCC AR6 median global warming levels for each scenario.

Usage:
    python generate_scaled_deltas.py
"""

import os
import csv
from pathlib import Path

# IPCC AR6 Median Global Warming Levels (relative to 1850-1900)
# Data source: IPCC AR6 WGI Summary for Policymakers, Table SPM.1
WARMING_LEVELS = {
    ("ssp126", "2050"): 1.7,
    ("ssp126", "2070"): 1.8,  
    ("ssp245", "2050"): 1.9,
    ("ssp245", "2070"): 2.3,
    ("ssp370", "2050"): 2.0,
    ("ssp370", "2070"): 2.65,
    ("ssp585", "2050"): 2.1,
    ("ssp585", "2070"): 2.95, # Anchor scenario
}

ANCHOR_GWL = 2.95

BASE_DIR = Path(__file__).resolve().parent
DELTAS_DIR = BASE_DIR / "data" / "deltas"
CURA_DELTAS_PATH = DELTAS_DIR / "derived_cura_deltas.csv"

def load_anchor():
    """Loads the SSP5-8.5 2070 anchor data."""
    cura = {}
    with open(CURA_DELTAS_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = int(row['month'])
            cura[m] = {
                'delta_tas': float(row['delta_tas']),
                'delta_tasmax': float(row['delta_tasmax']),
                'delta_tasmin': float(row['delta_tasmin']),
                'alpha_rsds': float(row['alpha_rsds']),
                'alpha_sfcWind': float(row['alpha_sfcWind']),
                'alpha_hurs': float(row['alpha_hurs']),
                'alpha_pr': float(row['alpha_pr']),
            }
            if 'delta_pres' in row:
                cura[m]['delta_pres'] = float(row['delta_pres'])
    return cura

def scale_value(anchor_val, scale, is_alpha=False):
    """
    Scales a value based on global warming level ratio.
    Absolute deltas (temp) scale from 0.0.
    Ratios (alpha) scale from 1.0.
    """
    if is_alpha:
        return round(1.0 + scale * (anchor_val - 1.0), 4)
    else:
        return round(scale * anchor_val, 4)

def generate_files():
    print("=" * 60)
    print("Generating Pattern Scaled Deltas (IPCC AR6)")
    print("=" * 60)

    if not CURA_DELTAS_PATH.exists():
        print(f"ERROR: Anchor file not found: {CURA_DELTAS_PATH}")
        return

    anchor_data = load_anchor()
    
    fieldnames = [
        'month', 'delta_tas', 'delta_tasmax', 'delta_tasmin',
        'alpha_hurs', 'alpha_rsds', 'alpha_sfcWind', 'alpha_pr',
        'delta_pres'
    ]

    for (ssp, period), gwl in WARMING_LEVELS.items():
        scale = gwl / ANCHOR_GWL
        ssp_num = ssp.replace("ssp", "")
        filename = f"bangkok_ssp{ssp_num}_{period}.csv"
        filepath = DELTAS_DIR / filename
        
        rows = []
        for m in range(1, 13):
            d = anchor_data[m]
            row = {
                'month': m,
                'delta_tas': scale_value(d['delta_tas'], scale, False),
                'delta_tasmax': scale_value(d['delta_tasmax'], scale, False),
                'delta_tasmin': scale_value(d['delta_tasmin'], scale, False),
                'alpha_hurs': scale_value(d['alpha_hurs'], scale, True),
                'alpha_rsds': scale_value(d['alpha_rsds'], scale, True),
                'alpha_sfcWind': scale_value(d['alpha_sfcWind'], scale, True),
                'alpha_pr': scale_value(d['alpha_pr'], scale, True),
            }
            if 'delta_pres' in d:
                row['delta_pres'] = scale_value(d['delta_pres'], scale, False)
            rows.append(row)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"✓ Created {filename:<25} | GWL: {gwl:.2f}°C (Scale: {scale:.2%})")

    print(f"\nAll 8 delta files successfully generated in data/deltas/")

if __name__ == "__main__":
    generate_files()
