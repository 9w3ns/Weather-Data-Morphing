"""
epw_morphing_engine.py — EPW Morphing Orchestrator
====================================================
Coordinates the full EPW morphing pipeline by:
    1. Reading a baseline .epw file
    2. Loading monthly climate deltas from CSV
    3. Applying either the Belcher or BTWS morphing method
    4. Writing the morphed .epw file

This module ties together belcher_morpher.py and btws_morpher.py,
letting the user choose which method to apply for each variable.

Usage:
    engine = EPWMorphingEngine("baseline.epw", "deltas.csv")
    engine.morph(method="belcher")   # or method="btws"
    engine.save("morphed_output.epw")
    engine.print_summary()
"""

import csv
import os
from datetime import datetime
from copy import deepcopy

import numpy as np

from belcher_morpher import BelcherMorpher
from btws_morpher import BTWSMorpher


# ── EPW Column Indices ──────────────────────────────────────────
# Standard EPW data fields (0-indexed after the 8 header rows)
# Reference: EnergyPlus Auxiliary Programs documentation
EPW_COLS = {
    'year':                         0,
    'month':                        1,
    'day':                          2,
    'hour':                         3,
    'minute':                       4,
    'dry_bulb_temperature':         6,
    'dew_point_temperature':        7,
    'relative_humidity':            8,
    'atmospheric_pressure':         9,
    'global_horizontal_radiation': 13,
    'direct_normal_radiation':     14,
    'diffuse_horizontal_radiation':15,
    'wind_direction':              20,
    'wind_speed':                  21,
    'precipitable_water':          28,
    'liquid_precipitation_depth':  33,
}


class EPWMorphingEngine:
    """
    Orchestrates the complete EPW morphing workflow.
    
    :param epw_path:   Path to the baseline .epw file.
    :param delta_path: Path to the monthly deltas .csv file.
    """

    def __init__(self, epw_path, delta_path):
        self.epw_path = epw_path
        self.delta_path = delta_path

        # Morphers
        self.belcher = BelcherMorpher()
        self.btws = BTWSMorpher(m=2, n=2, min_dtr=1.0)

        # Data storage
        self.header_lines = []      # First 8 lines of EPW
        self.data_rows = []         # List of lists (each row = split by comma)
        self.deltas = {}            # {month: {field: value}}
        self.morph_log = []         # Log of operations performed
        self.method_used = None

        # Load data
        self._load_epw()
        self._load_deltas()

    # ── Data Loading ────────────────────────────────────────────

    def _load_epw(self):
        """Reads and parses the baseline .epw file."""
        with open(self.epw_path, 'r') as f:
            lines = f.readlines()

        # First 8 lines are header
        self.header_lines = lines[:8]

        # Remaining 8760 lines are hourly data
        self.data_rows = []
        for line in lines[8:]:
            line = line.strip()
            if line:
                self.data_rows.append(line.split(','))

        self._log(f"Loaded EPW: {os.path.basename(self.epw_path)} "
                  f"({len(self.data_rows)} hours)")

    def _load_deltas(self):
        """
        Reads monthly climate change factors from CSV.
        
        Expected CSV columns:
            month         : 1-12
            delta_tas     : Change in mean temperature (°C)
            delta_tasmax  : Change in daily max temperature (°C)
            delta_tasmin  : Change in daily min temperature (°C)
            alpha_hurs    : Fractional change in relative humidity
            alpha_rsds    : Fractional change in solar radiation
            alpha_sfcWind : Fractional change in wind speed
            alpha_pr      : Fractional change in precipitation
            
        Optional columns:
            delta_rsds_max : Change in daily max solar radiation (Wh/m²)
            delta_rsds_min : Change in daily min solar radiation (Wh/m²)
            delta_pres     : Change in atmospheric pressure (Pa)
        """
        self.deltas = {}
        with open(self.delta_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                m = int(row['month'])
                self.deltas[m] = {}
                for key, val in row.items():
                    if key != 'month':
                        try:
                            self.deltas[m][key] = float(val)
                        except (ValueError, TypeError):
                            self.deltas[m][key] = 0.0

        self._log(f"Loaded deltas: {os.path.basename(self.delta_path)} "
                  f"({len(self.deltas)} months)")

    # ── Column Extraction Helpers ───────────────────────────────

    def _get_column(self, col_index):
        """Extracts a single column from EPW data as float array."""
        return np.array([float(row[col_index]) for row in self.data_rows])

    def _set_column(self, col_index, values):
        """Writes a float array back into a specific EPW column."""
        for i, val in enumerate(values):
            self.data_rows[i][col_index] = f"{val:.1f}"

    def _get_months(self):
        """Returns month number (1-12) for each of the 8760 hours."""
        return np.array([int(row[EPW_COLS['month']]) for row in self.data_rows])

    def _get_month_mask(self, months_array, month):
        """Returns a boolean mask for a specific month."""
        return months_array == month

    def _get_daily_slices(self, month_indices):
        """
        Groups hourly indices by day (24-hour blocks).
        Returns a list of np.ndarray, each containing 24 indices.
        """
        days = []
        for i in range(0, len(month_indices), 24):
            chunk = month_indices[i:i+24]
            if len(chunk) == 24:
                days.append(chunk)
            elif len(chunk) > 0:
                days.append(chunk)  # Partial last day
        return days

    # ── Morphing Methods ────────────────────────────────────────

    def morph(self, method="belcher"):
        """
        Applies morphing to all supported EPW variables.
        
        :param method: "belcher" for standard shift/stretch, or
                       "btws" for bounded temperature weighted stretch.
        """
        self.method_used = method
        self._log(f"\n{'='*50}")
        self._log(f"MORPHING METHOD: {method.upper()}")
        self._log(f"{'='*50}")

        months = self._get_months()

        # ── Dry Bulb Temperature ────────────────────────────────
        self._morph_dry_bulb(months, method)

        # ── Dew Point Temperature ───────────────────────────────
        self._morph_dew_point(months, method)

        # ── Relative Humidity ───────────────────────────────────
        self._morph_relative_humidity(months)

        # ── Global Horizontal Radiation ─────────────────────────
        self._morph_solar_radiation(months, method)

        # ── Wind Speed ──────────────────────────────────────────
        self._morph_wind_speed(months)

        # ── Precipitation ───────────────────────────────────────
        self._morph_precipitation(months)

        # ── Atmospheric Pressure (if delta provided) ────────────
        self._morph_pressure(months)

        # ── Post-Morphing Consistency Checks ────────────────────
        self._enforce_psychrometric_consistency()

        self._log(f"\nMorphing complete. {len(self.data_rows)} hours processed.")

    # ── Per-Variable Morphing ───────────────────────────────────

    def _morph_dry_bulb(self, months, method):
        """Morphs dry bulb temperature."""
        col = EPW_COLS['dry_bulb_temperature']
        temps = self._get_column(col)
        morphed = temps.copy()

        if method == "belcher":
            # ── Belcher Shift+Stretch (monthly) ─────────────────
            for m in range(1, 13):
                d = self.deltas[m]
                mask = self._get_month_mask(months, m)
                month_vals = temps[mask]

                # Calculate alpha from max/min deltas and baseline
                daily_maxes = []
                daily_mins = []
                indices = np.where(mask)[0]
                for day_start in range(0, len(indices), 24):
                    day_chunk = indices[day_start:day_start+24]
                    if len(day_chunk) > 0:
                        day_vals = temps[day_chunk]
                        daily_maxes.append(np.max(day_vals))
                        daily_mins.append(np.min(day_vals))

                baseline_max_mean = np.mean(daily_maxes) if daily_maxes else np.max(month_vals)
                baseline_min_mean = np.mean(daily_mins) if daily_mins else np.min(month_vals)

                alpha = self.belcher.calculate_alpha_temperature(
                    d['delta_tasmax'], d['delta_tasmin'],
                    baseline_max_mean, baseline_min_mean
                )
                morphed[mask] = self.belcher.morph_dry_bulb_temperature(
                    month_vals, d['delta_tas'], alpha
                )
                self._log(f"  DBT Month {m:2d}: shift={d['delta_tas']:+.1f}°C, "
                         f"alpha={alpha:.4f} [Belcher]")

        elif method == "btws":
            # ── BTWS (daily) ────────────────────────────────────
            for m in range(1, 13):
                d = self.deltas[m]
                mask = self._get_month_mask(months, m)
                indices = np.where(mask)[0]
                daily_slices = self._get_daily_slices(indices)

                for day_idx in daily_slices:
                    day_temps = temps[day_idx]
                    day_morphed = self.btws.morph_temperature(
                        day_temps, d['delta_tas'],
                        d['delta_tasmax'], d['delta_tasmin']
                    )
                    morphed[day_idx] = day_morphed

                self._log(f"  DBT Month {m:2d}: Δmean={d['delta_tas']:+.1f}°C, "
                         f"Δmax={d['delta_tasmax']:+.1f}°C, "
                         f"Δmin={d['delta_tasmin']:+.1f}°C [BTWS]")

        self._set_column(col, morphed)
        self._log(f"  ✓ Dry Bulb Temperature morphed")

    def _morph_dew_point(self, months, method):
        """Morphs dew point temperature."""
        col = EPW_COLS['dew_point_temperature']
        dpt = self._get_column(col)
        morphed = dpt.copy()

        for m in range(1, 13):
            d = self.deltas[m]
            mask = self._get_month_mask(months, m)
            month_vals = dpt[mask]

            if method == "btws":
                # For BTWS: apply daily morphing with same deltas 
                # scaled by ~0.8 (dew point tracks DBT imperfectly)
                indices = np.where(mask)[0]
                daily_slices = self._get_daily_slices(indices)
                dpt_factor = 0.8  # Dew point typically changes ~80% as much as DBT

                for day_idx in daily_slices:
                    day_dpt = dpt[day_idx]
                    day_morphed = self.btws.morph_temperature(
                        day_dpt,
                        d['delta_tas'] * dpt_factor,
                        d['delta_tasmax'] * dpt_factor,
                        d['delta_tasmin'] * dpt_factor
                    )
                    morphed[day_idx] = day_morphed
            else:
                # Belcher: shift+stretch using delta_tas as proxy
                alpha = 0.0  # Simple shift for dew point
                morphed[mask] = self.belcher.morph_dew_point_temperature(
                    month_vals, d['delta_tas'] * 0.8, alpha
                )

        self._set_column(col, morphed)
        self._log(f"  ✓ Dew Point Temperature morphed")

    def _morph_relative_humidity(self, months):
        """Morphs relative humidity using Belcher stretch (both methods)."""
        col = EPW_COLS['relative_humidity']
        rh = self._get_column(col)
        morphed = rh.copy()

        for m in range(1, 13):
            d = self.deltas[m]
            mask = self._get_month_mask(months, m)
            alpha = d.get('alpha_hurs', 1.0)
            morphed[mask] = self.belcher.morph_relative_humidity(rh[mask], alpha)

        self._set_column(col, morphed)
        self._log(f"  ✓ Relative Humidity morphed [Belcher stretch]")

    def _morph_solar_radiation(self, months, method):
        """Morphs global horizontal radiation."""
        col_ghr = EPW_COLS['global_horizontal_radiation']
        ghr = self._get_column(col_ghr)
        morphed = ghr.copy()

        if method == "btws" and all(
            'delta_rsds_max' in self.deltas[m] for m in range(1, 13)
        ):
            # ── BTWS for solar radiation (if max/min deltas provided) ─
            for m in range(1, 13):
                d = self.deltas[m]
                mask = self._get_month_mask(months, m)
                indices = np.where(mask)[0]
                daily_slices = self._get_daily_slices(indices)

                delta_mean = d.get('delta_rsds_mean', 0.0)
                delta_max = d.get('delta_rsds_max', 0.0)
                delta_min = d.get('delta_rsds_min', 0.0)

                for day_idx in daily_slices:
                    day_ghr = ghr[day_idx]
                    day_morphed = self.btws.morph_solar_radiation(
                        day_ghr, delta_mean, delta_max, delta_min
                    )
                    morphed[day_idx] = day_morphed

                self._log(f"  GHR Month {m:2d}: BTWS applied")
        else:
            # ── Belcher stretch for solar radiation ─────────────
            for m in range(1, 13):
                d = self.deltas[m]
                mask = self._get_month_mask(months, m)
                alpha = d.get('alpha_rsds', 1.0)
                morphed[mask] = self.belcher.morph_solar_radiation(
                    ghr[mask], alpha
                )

        self._set_column(col_ghr, morphed)
        self._log(f"  ✓ Global Horizontal Radiation morphed")

    def _morph_wind_speed(self, months):
        """Morphs wind speed using Belcher stretch (both methods)."""
        col = EPW_COLS['wind_speed']
        ws = self._get_column(col)
        morphed = ws.copy()

        for m in range(1, 13):
            d = self.deltas[m]
            mask = self._get_month_mask(months, m)
            alpha = d.get('alpha_sfcWind', 1.0)
            morphed[mask] = self.belcher.morph_wind_speed(ws[mask], alpha)

        self._set_column(col, morphed)
        self._log(f"  ✓ Wind Speed morphed [Belcher stretch]")

    def _morph_precipitation(self, months):
        """Morphs precipitation using Belcher stretch (both methods)."""
        col = EPW_COLS['liquid_precipitation_depth']
        precip = self._get_column(col)
        morphed = precip.copy()

        for m in range(1, 13):
            d = self.deltas[m]
            mask = self._get_month_mask(months, m)
            alpha = d.get('alpha_pr', 1.0)
            morphed[mask] = self.belcher.morph_precipitation(precip[mask], alpha)

        self._set_column(col, morphed)
        self._log(f"  ✓ Precipitation morphed [Belcher stretch]")

    def _morph_pressure(self, months):
        """Morphs atmospheric pressure if delta_pres is provided."""
        col = EPW_COLS['atmospheric_pressure']

        has_pressure_delta = any(
            'delta_pres' in self.deltas[m] and self.deltas[m]['delta_pres'] != 0
            for m in range(1, 13)
        )
        if not has_pressure_delta:
            self._log(f"  ○ Atmospheric Pressure: no delta provided, skipped")
            return

        pres = self._get_column(col)
        morphed = pres.copy()

        for m in range(1, 13):
            d = self.deltas[m]
            mask = self._get_month_mask(months, m)
            delta = d.get('delta_pres', 0.0)
            morphed[mask] = self.belcher.morph_atmospheric_pressure(
                pres[mask], delta
            )

        self._set_column(col, morphed)
        self._log(f"  ✓ Atmospheric Pressure morphed [Belcher shift]")

    # ── Post-Morphing Validation ────────────────────────────────

    def _enforce_psychrometric_consistency(self):
        """
        Ensures dew point ≤ dry bulb at every timestep.
        This is a physical constraint that can be violated when 
        temperature and humidity are morphed independently.
        """
        col_dbt = EPW_COLS['dry_bulb_temperature']
        col_dpt = EPW_COLS['dew_point_temperature']

        dbt = self._get_column(col_dbt)
        dpt = self._get_column(col_dpt)

        violations = np.sum(dpt > dbt)
        if violations > 0:
            # Clamp dew point to not exceed dry bulb
            dpt_fixed = np.minimum(dpt, dbt)
            self._set_column(col_dpt, dpt_fixed)
            self._log(f"  ⚠ Psychrometric fix: {violations} hours had "
                     f"DPT > DBT, clamped to DBT")
        else:
            self._log(f"  ✓ Psychrometric check passed (DPT ≤ DBT)")

    # ── Output ──────────────────────────────────────────────────

    def save(self, output_path):
        """
        Writes the morphed data to a new .epw file.
        
        :param output_path: Path for the output .epw file.
        """
        with open(output_path, 'w', newline='') as f:
            # Write header lines (unchanged)
            for line in self.header_lines:
                f.write(line)
            # Write morphed data rows
            for row in self.data_rows:
                f.write(','.join(row) + '\n')

        self._log(f"\nSaved morphed EPW: {output_path}")

    def print_summary(self):
        """Prints a summary comparing baseline vs morphed statistics."""
        print("\n" + "=" * 60)
        print("EPW MORPHING SUMMARY")
        print("=" * 60)
        print(f"  Source:  {os.path.basename(self.epw_path)}")
        print(f"  Deltas:  {os.path.basename(self.delta_path)}")
        print(f"  Method:  {self.method_used}")
        print("-" * 60)

        # Print the log
        for entry in self.morph_log:
            print(entry)

    def get_comparison_data(self):
        """
        Returns a dict with baseline and morphed arrays for each
        variable, useful for generating comparison plots.
        """
        # Re-read baseline for comparison
        baseline_data = {}
        with open(self.epw_path, 'r') as f:
            lines = f.readlines()[8:]
        
        for var_name, col_idx in EPW_COLS.items():
            if var_name in ('year', 'month', 'day', 'hour', 'minute'):
                continue
            try:
                baseline_data[var_name] = np.array([
                    float(line.strip().split(',')[col_idx]) 
                    for line in lines if line.strip()
                ])
            except (ValueError, IndexError):
                pass

        morphed_data = {}
        for var_name, col_idx in EPW_COLS.items():
            if var_name in ('year', 'month', 'day', 'hour', 'minute'):
                continue
            try:
                morphed_data[var_name] = self._get_column(col_idx)
            except (ValueError, IndexError):
                pass

        return {'baseline': baseline_data, 'morphed': morphed_data}

    # ── Logging ─────────────────────────────────────────────────

    def _log(self, message):
        """Appends a message to the morph log."""
        self.morph_log.append(message)


# ── Example Usage ───────────────────────────────────────────────
if __name__ == "__main__":
    print("EPW Morphing Engine")
    print("=" * 40)
    print()
    print("Usage:")
    print("  from epw_morphing_engine import EPWMorphingEngine")
    print()
    print('  engine = EPWMorphingEngine("../data/epw/Bangkok_baseline_2026_TMYx.epw", "../data/deltas/bangkok_ssp585_2070.csv")')
    print()
    print("  # Option A: Standard Belcher shift/stretch")
    print('  engine.morph(method="belcher")')
    print('  engine.save("morphed_belcher.epw")')
    print()
    print("  # Option B: Bounded Temperature Weighted Stretch")
    print('  engine.morph(method="btws")')
    print('  engine.save("morphed_btws.epw")')
    print()
    print("  engine.print_summary()")
    print()
    print("Delta CSV format:")
    print("  month,delta_tas,delta_tasmax,delta_tasmin,alpha_hurs,"
          "alpha_rsds,alpha_sfcWind,alpha_pr")
    print("  1,1.8,2.1,1.5,0.97,1.02,0.98,0.85")
    print("  2,2.0,2.3,1.7,0.96,1.03,0.97,0.80")
    print("  ...")
