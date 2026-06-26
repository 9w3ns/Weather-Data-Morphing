"""
belcher_morpher.py — Standard Belcher Shift/Stretch Morphing
=============================================================
Implements the Belcher, Hacker & Powell (2005) morphing methodology
with refinements by Jentsch (2012). This is the same core approach
used by futureweather.co and CCWorldWeatherGen.

Three operations:
    1. Shift        x' = x + Δx_m
    2. Stretch      x' = x · α_m
    3. Shift+Stretch x' = x + Δx_m + α_m · (x - x̄_m)

References:
    - Belcher, S.E., Hacker, J.N. & Powell, D.S. (2005).
      "Constructing design weather data for future climates."
    - Jentsch, M.F. (2012). Technical Reference Manual for
      CCWeatherGen and CCWorldWeatherGen.
"""

import numpy as np


class BelcherMorpher:
    """
    Standard Belcher shift/stretch morphing for EPW weather variables.
    
    This morpher applies monthly climate change factors (deltas) to 
    hourly baseline weather data. It is simpler than BTWS but well-
    validated and widely used in building simulation.
    """

    # ── Shift ───────────────────────────────────────────────────
    @staticmethod
    def shift(hourly_values, delta):
        """
        Applies an absolute shift to hourly values.
        
            x' = x + Δx_m
        
        Use for variables where the GCM provides an absolute change
        (e.g., atmospheric pressure in Pa).
        
        :param hourly_values: np.ndarray of baseline hourly values.
        :param delta:         Absolute monthly mean change (scalar).
        :return:              np.ndarray of morphed hourly values.
        """
        return hourly_values + delta

    # ── Stretch ─────────────────────────────────────────────────
    @staticmethod
    def stretch(hourly_values, alpha):
        """
        Applies a fractional/percentage stretch to hourly values.
        
            x' = x · α_m
        
        Use for variables where the GCM provides a proportional 
        change (e.g., solar radiation, wind speed, precipitation).
        
        :param hourly_values: np.ndarray of baseline hourly values.
        :param alpha:         Fractional change factor (scalar).
                              1.0 = no change, 1.15 = +15%, 0.85 = -15%.
        :return:              np.ndarray of morphed hourly values.
        """
        return hourly_values * alpha

    # ── Shift + Stretch ─────────────────────────────────────────
    @staticmethod
    def shift_stretch(hourly_values, delta, alpha):
        """
        Applies a combined shift and stretch to hourly values.
        
            x' = x + Δx_m + α_m · (x - x̄_m)
        
        This adjusts both the mean (via shift) and the variance
        (via stretch around the monthly mean). Use for variables 
        where both the average level and the spread are projected 
        to change (e.g., dry bulb temperature).
        
        :param hourly_values: np.ndarray of baseline hourly values
                              for a single month.
        :param delta:         Absolute shift in the monthly mean.
        :param alpha:         Stretch factor for variance around the mean.
                              Calculated as: α = (ΔT_max - ΔT_min) / 
                              (T_max_bar - T_min_bar), where T_max_bar and 
                              T_min_bar are the baseline monthly mean daily 
                              max and min temperatures.
        :return:              np.ndarray of morphed hourly values.
        """
        x_bar = np.mean(hourly_values)
        return hourly_values + delta + alpha * (hourly_values - x_bar)

    # ── Variable-Specific Morphing Methods ──────────────────────

    def morph_dry_bulb_temperature(self, hourly_temps, delta_mean, alpha):
        """
        Morphs dry bulb temperature using shift + stretch.
        
        :param hourly_temps: np.ndarray of hourly temperatures for one month.
        :param delta_mean:   Change in monthly mean temperature (°C).
        :param alpha:        Stretch factor for temperature variance.
        :return:             np.ndarray of morphed temperatures.
        """
        return self.shift_stretch(hourly_temps, delta_mean, alpha)

    def morph_dew_point_temperature(self, hourly_dpt, delta_mean, alpha):
        """
        Morphs dew point temperature using shift + stretch.
        Uses the Jentsch (2012) refinement.
        
        :param hourly_dpt: np.ndarray of hourly dew point temps for one month.
        :param delta_mean: Change in monthly mean dew point temperature (°C).
        :param alpha:      Stretch factor for dew point variance.
        :return:           np.ndarray of morphed dew point temperatures.
        """
        return self.shift_stretch(hourly_dpt, delta_mean, alpha)

    def morph_relative_humidity(self, hourly_rh, alpha):
        """
        Morphs relative humidity using stretch.
        Clamps output to [0, 100]%.
        
        :param hourly_rh: np.ndarray of hourly RH values for one month (%).
        :param alpha:     Fractional change factor for humidity.
        :return:          np.ndarray of morphed RH values, clamped to [0, 100].
        """
        morphed = self.stretch(hourly_rh, alpha)
        return np.clip(morphed, 0.0, 100.0)

    def morph_wind_speed(self, hourly_ws, alpha):
        """
        Morphs wind speed using stretch.
        Clamps output to ≥ 0.
        
        :param hourly_ws: np.ndarray of hourly wind speed for one month (m/s).
        :param alpha:     Fractional change factor for wind speed.
        :return:          np.ndarray of morphed wind speed, clamped to ≥ 0.
        """
        morphed = self.stretch(hourly_ws, alpha)
        return np.maximum(morphed, 0.0)

    def morph_solar_radiation(self, hourly_ghr, alpha):
        """
        Morphs global horizontal radiation using stretch.
        Clamps output to ≥ 0.
        
        :param hourly_ghr: np.ndarray of hourly GHR for one month (Wh/m²).
        :param alpha:      Fractional change factor for solar radiation.
        :return:           np.ndarray of morphed GHR, clamped to ≥ 0.
        """
        morphed = self.stretch(hourly_ghr, alpha)
        return np.maximum(morphed, 0.0)

    def morph_precipitation(self, hourly_precip, alpha):
        """
        Morphs precipitation using stretch.
        Clamps output to ≥ 0.
        
        :param hourly_precip: np.ndarray of hourly precipitation (mm).
        :param alpha:         Fractional change factor for precipitation.
        :return:              np.ndarray of morphed precipitation, clamped to ≥ 0.
        """
        morphed = self.stretch(hourly_precip, alpha)
        return np.maximum(morphed, 0.0)

    def morph_atmospheric_pressure(self, hourly_pres, delta):
        """
        Morphs atmospheric pressure using shift.
        Pressure changes are typically very small under climate change.
        
        :param hourly_pres: np.ndarray of hourly pressure (Pa).
        :param delta:       Absolute change in monthly mean pressure (Pa).
        :return:            np.ndarray of morphed pressure.
        """
        return self.shift(hourly_pres, delta)

    # ── Utility: Calculate Alpha from GCM Deltas ────────────────

    @staticmethod
    def calculate_alpha_temperature(delta_max, delta_min, baseline_monthly_max_mean,
                                     baseline_monthly_min_mean):
        """
        Calculates the stretch factor (alpha) for temperature morphing
        from GCM-projected changes in daily max/min temperatures.
        
            α = (ΔT_max - ΔT_min) / (T̄_max - T̄_min)
        
        :param delta_max:                Change in monthly mean daily max temp (°C).
        :param delta_min:                Change in monthly mean daily min temp (°C).
        :param baseline_monthly_max_mean: Baseline monthly mean of daily max temps (°C).
        :param baseline_monthly_min_mean: Baseline monthly mean of daily min temps (°C).
        :return:                          Stretch factor alpha (dimensionless).
        """
        diurnal_range = baseline_monthly_max_mean - baseline_monthly_min_mean
        if abs(diurnal_range) < 1e-6:
            return 0.0
        return (delta_max - delta_min) / diurnal_range

    @staticmethod
    def calculate_alpha_from_ratio(future_monthly_mean, baseline_monthly_mean):
        """
        Calculates the stretch factor (alpha) as a simple ratio 
        for variables like radiation, wind, and precipitation.
        
            α = future_mean / baseline_mean
        
        :param future_monthly_mean:   Projected future monthly mean.
        :param baseline_monthly_mean: Baseline (historical) monthly mean.
        :return:                      Stretch factor alpha.
        """
        if abs(baseline_monthly_mean) < 1e-9:
            return 1.0
        return future_monthly_mean / baseline_monthly_mean


# ── Example Usage ───────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("BELCHER MORPHER — Standard Shift/Stretch Demo")
    print("=" * 60)

    # Simulate a hot Bangkok January: 24 hours
    time = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    baseline_temps = 28.0 - 4.0 * np.cos(time)  # min ~24, max ~32, mean ~28

    # Example monthly deltas for Bangkok 2070 SSP5-8.5
    delta_mean = 3.8   # Mean temp rises by 3.8°C
    delta_max  = 4.2   # Daily max rises by 4.2°C
    delta_min  = 3.5   # Daily min rises by 3.5°C

    # Calculate monthly mean daily max/min from baseline
    # (In practice, compute from all days in the month)
    baseline_max_mean = np.max(baseline_temps)  # simplified for demo
    baseline_min_mean = np.min(baseline_temps)

    morpher = BelcherMorpher()

    # Calculate alpha
    alpha = morpher.calculate_alpha_temperature(
        delta_max, delta_min, baseline_max_mean, baseline_min_mean
    )

    # Morph temperature
    morphed = morpher.morph_dry_bulb_temperature(baseline_temps, delta_mean, alpha)

    print("\n--- Dry Bulb Temperature (Shift+Stretch) ---")
    print(f"  Baseline  Min/Mean/Max: {np.min(baseline_temps):.1f} / "
          f"{np.mean(baseline_temps):.1f} / {np.max(baseline_temps):.1f} °C")
    print(f"  Morphed   Min/Mean/Max: {np.min(morphed):.1f} / "
          f"{np.mean(morphed):.1f} / {np.max(morphed):.1f} °C")
    print(f"  Alpha (stretch factor): {alpha:.4f}")

    # Morph wind speed (pure stretch)
    baseline_wind = np.array([2.5, 2.0, 1.5, 1.2, 1.0, 1.5,
                              2.0, 3.0, 4.0, 4.5, 5.0, 5.2,
                              5.5, 5.0, 4.8, 4.5, 4.0, 3.5,
                              3.0, 2.8, 2.5, 2.3, 2.2, 2.5])
    alpha_wind = 0.95  # Wind decreases by 5%
    morphed_wind = morpher.morph_wind_speed(baseline_wind, alpha_wind)

    print("\n--- Wind Speed (Stretch) ---")
    print(f"  Baseline  Mean: {np.mean(baseline_wind):.2f} m/s")
    print(f"  Morphed   Mean: {np.mean(morphed_wind):.2f} m/s")
    print(f"  Alpha: {alpha_wind}")

    # Morph solar radiation (pure stretch)
    baseline_ghr = np.array([0, 0, 0, 0, 0, 0, 50, 200, 400, 550, 650, 700,
                             720, 680, 600, 450, 250, 80, 0, 0, 0, 0, 0, 0])
    alpha_solar = 1.03  # Solar radiation increases by 3%
    morphed_ghr = morpher.morph_solar_radiation(baseline_ghr, alpha_solar)

    print("\n--- Global Horizontal Radiation (Stretch) ---")
    print(f"  Baseline  Daily Total: {np.sum(baseline_ghr):.0f} Wh/m²")
    print(f"  Morphed   Daily Total: {np.sum(morphed_ghr):.0f} Wh/m²")
    print(f"  Alpha: {alpha_solar}")
    print(f"  Change: {(np.sum(morphed_ghr)/np.sum(baseline_ghr) - 1)*100:+.1f}%")
