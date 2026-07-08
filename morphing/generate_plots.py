import sys
import os
import matplotlib.pyplot as plt
import numpy as np

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from epw_morphing_engine import EPWMorphingEngine, EPW_COLS

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    epw_path = os.path.join(base_dir, 'data', 'epw', 'Bangkok_baseline_2026_TMYx.epw')
    delta_path = os.path.join(base_dir, 'data', 'deltas', 'bangkok_ssp370_2050.csv')
    cura_path = os.path.join(base_dir, 'data', 'epw', 'Bangkok_baseline_2026_TMYx_FUTURE_2050_ssp370.epw')
    
    out_dir = os.path.join(base_dir, 'visualization', '2050_ssp3')
    os.makedirs(out_dir, exist_ok=True)
    
    # Run Belcher
    print("Running Belcher...")
    engine_belcher = EPWMorphingEngine(epw_path, delta_path)
    engine_belcher.morph(method="belcher")
    belcher_data = engine_belcher.get_comparison_data()['morphed']
    baseline_data = engine_belcher.get_comparison_data()['baseline']
    
    # Run BTWS
    print("Running BTWS...")
    engine_btws = EPWMorphingEngine(epw_path, delta_path)
    engine_btws.morph(method="btws")
    btws_data = engine_btws.get_comparison_data()['morphed']
    
    # Load Benchmark
    print("Loading Benchmark (CURA-lab/Future)...")
    engine_cura = EPWMorphingEngine(cura_path, delta_path) # dummy delta
    cura_data = {}
    for var_name, col_idx in EPW_COLS.items():
        if var_name in ('year', 'month', 'day', 'hour', 'minute'): continue
        try:
            cura_data[var_name] = engine_cura._get_column(col_idx)
        except Exception:
            pass
            
    months = np.array([int(row[EPW_COLS['month']]) for row in engine_belcher.data_rows])
    
    def calc_monthly_mean(data_array):
        return [np.mean(data_array[months == m]) for m in range(1, 13)]
        
    variables = {
        'dry_bulb_temperature': ('Dry Bulb Temperature', '°C'),
        'global_horizontal_radiation': ('Global Horizontal Radiation', 'Wh/m²'),
        'relative_humidity': ('Relative Humidity', '%'),
        'wind_speed': ('Wind Speed', 'm/s')
    }
    
    # 1. Monthly Mean Comparison Charts
    plt.style.use('ggplot')
    for var, (title, unit) in variables.items():
        plt.figure(figsize=(10, 6))
        
        m_base = calc_monthly_mean(baseline_data[var])
        m_belcher = calc_monthly_mean(belcher_data[var])
        m_btws = calc_monthly_mean(btws_data[var])
        m_cura = calc_monthly_mean(cura_data[var])
        
        x = np.arange(1, 13)
        plt.plot(x, m_base, 'k--', linewidth=2, label='Baseline (2026)')
        plt.plot(x, m_belcher, 'b-o', alpha=0.7, label='Belcher (Our Tool)')
        plt.plot(x, m_btws, 'r-s', alpha=0.7, label='BTWS (Our Tool)')
        plt.plot(x, m_cura, 'g-.^', alpha=0.7, label='Benchmark EPW')
        
        plt.title(f'Monthly Mean {title} (SSP3-7.0 2050)', fontsize=14)
        plt.xlabel('Month', fontsize=12)
        plt.ylabel(f'{title} ({unit})', fontsize=12)
        plt.xticks(x, ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        plt.legend(fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f'monthly_mean_{var}_ssp3_2050.png'), dpi=150)
        plt.close()
        
    # 2. Temperature Distribution Plot
    plt.figure(figsize=(12, 6))
    plt.hist(baseline_data['dry_bulb_temperature'], bins=50, alpha=0.4, color='black', label='Baseline')
    plt.hist(belcher_data['dry_bulb_temperature'], bins=50, alpha=0.4, color='blue', label='Belcher')
    plt.hist(btws_data['dry_bulb_temperature'], bins=50, alpha=0.4, color='red', label='BTWS')
    plt.axvline(np.mean(baseline_data['dry_bulb_temperature']), color='black', linestyle='--')
    plt.axvline(np.mean(belcher_data['dry_bulb_temperature']), color='blue', linestyle='--')
    plt.axvline(np.mean(btws_data['dry_bulb_temperature']), color='red', linestyle='--')
    plt.title('Hourly Dry Bulb Temperature Distribution (SSP3-7.0 2050)', fontsize=14)
    plt.xlabel('Temperature (°C)', fontsize=12)
    plt.ylabel('Frequency (Hours)', fontsize=12)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'temp_distribution_ssp3_2050.png'), dpi=150)
    plt.close()
    
    print("Done generating plots.")

if __name__ == "__main__":
    main()
