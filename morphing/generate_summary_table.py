import sys
import os
import numpy as np

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from epw_morphing_engine import EPWMorphingEngine, EPW_COLS

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    epw_path = os.path.join(base_dir, 'data', 'epw', 'Bangkok_baseline_2026_TMYx.epw')
    delta_path = os.path.join(base_dir, 'data', 'deltas', 'bangkok_ssp370_2050.csv')
    
    # Run Belcher
    engine_belcher = EPWMorphingEngine(epw_path, delta_path)
    engine_belcher.morph(method="belcher")
    belcher_data = engine_belcher.get_comparison_data()['morphed']
    baseline_data = engine_belcher.get_comparison_data()['baseline']
    
    # Run BTWS
    engine_btws = EPWMorphingEngine(epw_path, delta_path)
    engine_btws.morph(method="btws")
    btws_data = engine_btws.get_comparison_data()['morphed']
    
    variables = {
        'dry_bulb_temperature': ('Dry Bulb Temperature', '°C'),
        'dew_point_temperature': ('Dew Point Temperature', '°C'),
        'relative_humidity': ('Relative Humidity', '%'),
        'atmospheric_pressure': ('Atmospheric Pressure', 'Pa'),
        'global_horizontal_radiation': ('Global Horiz. Radiation', 'Wh/m²'),
        'direct_normal_radiation': ('Direct Normal Radiation', 'Wh/m²'),
        'diffuse_horizontal_radiation': ('Diffuse Horiz. Radiation', 'Wh/m²'),
        'wind_speed': ('Wind Speed', 'm/s'),
        'liquid_precipitation_depth': ('Precipitation', 'mm')
    }
    
    output_path = os.path.join(base_dir, 'visualization', '2050_ssp3', 'data_summary_table.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# 2050 SSP 3.0 Climate Data Comparison Table\n\n")
        f.write("This table compares the annual averages across all weather data types before and after morphing.\n\n")
        f.write("| Variable | Unit | Baseline (2026) | Belcher (2050 SSP3) | BTWS (2050 SSP3) | Delta (Future - Baseline) | Changed? |\n")
        f.write("|----------|------|-----------------|---------------------|------------------|---------------------------|----------|\n")
        
        for var, (title, unit) in variables.items():
            if var not in baseline_data:
                continue
                
            base_mean = np.mean(baseline_data[var])
            belch_mean = np.mean(belcher_data[var])
            btws_mean = np.mean(btws_data[var])
            
            # Calculate Delta
            delta = belch_mean - base_mean
            
            # Highlight if it changed
            changed = "✅ **YES**" if abs(delta) > 0.01 else "❌ NO"
            
            # Format the strings
            base_str = f"{base_mean:.2f}"
            belch_str = f"{belch_mean:.2f}"
            btws_str = f"{btws_mean:.2f}"
            delta_str = f"{delta:+.2f}"
            
            if changed == "✅ **YES**":
                f.write(f"| **{title}** | {unit} | {base_str} | **{belch_str}** | **{btws_str}** | **{delta_str}** | {changed} |\n")
            else:
                f.write(f"| {title} | {unit} | {base_str} | {belch_str} | {btws_str} | {delta_str} | {changed} |\n")
    print(f"Table saved to {output_path}")

if __name__ == "__main__":
    main()
