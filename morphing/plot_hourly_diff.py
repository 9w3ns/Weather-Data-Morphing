import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from epw_morphing_engine import EPWMorphingEngine

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    epw_path = os.path.join(base_dir, 'data', 'epw', 'Bangkok_baseline_2026_TMYx.epw')
    delta_path = os.path.join(base_dir, 'data', 'deltas', 'bangkok_ssp585_2070.csv')
    
    out_dir = os.path.join(base_dir, 'visualization', '2070_ssp585')
    os.makedirs(out_dir, exist_ok=True)
    
    print("Running Belcher...")
    engine_belcher = EPWMorphingEngine(epw_path, delta_path)
    engine_belcher.morph(method="belcher")
    belcher_temp = engine_belcher.get_comparison_data()['morphed']['dry_bulb_temperature']
    baseline_temp = engine_belcher.get_comparison_data()['baseline']['dry_bulb_temperature']
    
    print("Running BTWS...")
    engine_btws = EPWMorphingEngine(epw_path, delta_path)
    engine_btws.morph(method="btws")
    btws_temp = engine_btws.get_comparison_data()['morphed']['dry_bulb_temperature']
    
    # Pick a hot week in April (Hours ~2160 to ~2328)
    # 30 days in Jan, 28 in Feb, 31 in Mar = 89 days * 24 = 2136. So April starts at 2136
    start_hour = 2136 + (14 * 24) # Mid April (April 15th)
    end_hour = start_hour + (5 * 24) # 5 days
    
    plt.style.use('ggplot')
    plt.figure(figsize=(14, 7))
    
    x = np.arange(start_hour, end_hour)
    
    plt.plot(x, baseline_temp[start_hour:end_hour], 'k--', linewidth=2, label='Baseline (2026)')
    plt.plot(x, belcher_temp[start_hour:end_hour], 'b-', alpha=0.8, linewidth=2, label='Belcher (SSP5-8.5 2070)')
    plt.plot(x, btws_temp[start_hour:end_hour], 'r-.', alpha=0.8, linewidth=2, label='BTWS (SSP5-8.5 2070)')
    
    plt.title('Hourly Dry Bulb Temperature Comparison (Mid-April, 5 Days)', fontsize=16)
    plt.xlabel('Hour of the Year', fontsize=12)
    plt.ylabel('Dry Bulb Temperature (°C)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.4)
    plt.tight_layout()
    
    plot_path = os.path.join(out_dir, 'hourly_temperature_difference.png')
    plt.savefig(plot_path, dpi=150)
    print(f"Plot saved to {plot_path}")

if __name__ == "__main__":
    main()
