import sys
import os
import csv
import numpy as np
from epw_morphing_engine import EPWMorphingEngine, EPW_COLS

def read_epw_data(filepath):
    data = {}
    with open(filepath, 'r') as f:
        lines = f.readlines()[8:]
    for var_name, col_idx in EPW_COLS.items():
        if var_name in ('year', 'month', 'day', 'hour', 'minute'):
            if var_name == 'month':
                data[var_name] = np.array([int(line.strip().split(',')[col_idx]) for line in lines if line.strip()])
            continue
        try:
            data[var_name] = np.array([float(line.strip().split(',')[col_idx]) for line in lines if line.strip()])
        except (ValueError, IndexError):
            pass
    return data

def extract_deltas(baseline_data, future_data):
    months = baseline_data['month']
    deltas = []
    
    for m in range(1, 13):
        mask = months == m
        
        # Means
        base_dbt = baseline_data['dry_bulb_temperature'][mask]
        fut_dbt = future_data['dry_bulb_temperature'][mask]
        delta_tas = np.mean(fut_dbt) - np.mean(base_dbt)
        
        # Max/Min mean daily
        base_daily_max = []
        base_daily_min = []
        fut_daily_max = []
        fut_daily_min = []
        indices = np.where(mask)[0]
        for i in range(0, len(indices), 24):
            chunk = indices[i:i+24]
            if len(chunk) > 0:
                base_daily_max.append(np.max(baseline_data['dry_bulb_temperature'][chunk]))
                base_daily_min.append(np.min(baseline_data['dry_bulb_temperature'][chunk]))
                fut_daily_max.append(np.max(future_data['dry_bulb_temperature'][chunk]))
                fut_daily_min.append(np.min(future_data['dry_bulb_temperature'][chunk]))
                
        delta_tasmax = np.mean(fut_daily_max) - np.mean(base_daily_max) if base_daily_max else delta_tas
        delta_tasmin = np.mean(fut_daily_min) - np.mean(base_daily_min) if base_daily_min else delta_tas
        
        # Stretch factors
        base_rh = np.mean(baseline_data['relative_humidity'][mask])
        fut_rh = np.mean(future_data['relative_humidity'][mask])
        alpha_hurs = fut_rh / base_rh if base_rh > 0 else 1.0
        
        base_rsds = np.mean(baseline_data['global_horizontal_radiation'][mask])
        fut_rsds = np.mean(future_data['global_horizontal_radiation'][mask])
        alpha_rsds = fut_rsds / base_rsds if base_rsds > 0 else 1.0
        
        base_wind = np.mean(baseline_data['wind_speed'][mask])
        fut_wind = np.mean(future_data['wind_speed'][mask])
        alpha_sfcWind = fut_wind / base_wind if base_wind > 0 else 1.0
        
        base_pr = np.mean(baseline_data['liquid_precipitation_depth'][mask])
        fut_pr = np.mean(future_data['liquid_precipitation_depth'][mask])
        alpha_pr = fut_pr / base_pr if base_pr > 0 else 1.0
        
        # Pressure shift
        base_pres = np.mean(baseline_data['atmospheric_pressure'][mask])
        fut_pres = np.mean(future_data['atmospheric_pressure'][mask])
        delta_pres = fut_pres - base_pres
        
        deltas.append({
            'month': m,
            'delta_tas': round(delta_tas, 4),
            'delta_tasmax': round(delta_tasmax, 4),
            'delta_tasmin': round(delta_tasmin, 4),
            'alpha_hurs': round(alpha_hurs, 4),
            'alpha_rsds': round(alpha_rsds, 4),
            'alpha_sfcWind': round(alpha_sfcWind, 4),
            'alpha_pr': round(alpha_pr, 4),
            'delta_pres': round(delta_pres, 4)
        })
    return deltas

def main():
    base_epw = r"..\data\epw\Bangkok_baseline_2026_TMYx.epw"
    cura_epw = r"..\data\epw\Bangkok_CURA-lab_2070_ssp585.epw"
    
    print("Reading baseline and CURA-lab EPWs to extract deltas...")
    base_data = read_epw_data(base_epw)
    cura_data = read_epw_data(cura_epw)
    
    deltas = extract_deltas(base_data, cura_data)
    
    delta_csv = r"..\data\deltas\derived_cura_deltas.csv"
    with open(delta_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=deltas[0].keys())
        writer.writeheader()
        writer.writerows(deltas)
        
    print(f"Extracted deltas saved to {delta_csv}")
    
    print("Running Belcher Morpher with derived deltas...")
    engine = EPWMorphingEngine(base_epw, delta_csv)
    engine.morph(method="belcher")
    morphed_data = engine.get_comparison_data()['morphed']
    
    # Compare morphed_data with cura_data
    print("\n--- ERROR ANALYSIS (Our Belcher vs CURA-lab) ---")
    variables_to_check = [
        'dry_bulb_temperature', 
        'dew_point_temperature', 
        'relative_humidity',
        'global_horizontal_radiation',
        'wind_speed'
    ]
    
    for var in variables_to_check:
        our_vals = morphed_data[var]
        cura_vals = cura_data[var]
        
        diff = np.abs(our_vals - cura_vals)
        mean_err = np.mean(diff)
        max_err = np.max(diff)
        max_idx = np.argmax(diff)
        
        print(f"{var}:")
        print(f"  Mean Absolute Error: {mean_err:.3f}")
        print(f"  Max Absolute Error:  {max_err:.3f} (at hour {max_idx})")
        print(f"  Sample values at hour {max_idx}: Our={our_vals[max_idx]:.2f}, CURA={cura_vals[max_idx]:.2f}")

if __name__ == "__main__":
    main()
