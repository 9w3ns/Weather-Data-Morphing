"""
btws_morpher.py — Bounded Temperature Weighted Stretch Morphing
================================================================
Implements the BTWS algorithm from Eames et al. (2024) as described
in Hamann et al. (2025). This is a more advanced morphing method 
that independently preserves projected changes in daily minimum, 
maximum, AND mean temperatures.

Key advantage over Belcher shift+stretch:
    - Preserves physical bounds (min/max) exactly
    - Smooth non-linear weighting via transfer function
    - Better handling of asymmetric climate change signals

Algorithm steps:
    1. Normalize hourly values to [0, 1] range
    2. Apply transfer function (weighting curve)
    3. Calculate scaling factor from projected deltas
    4. Apply bounded transformation
    5. Denormalize back to physical values

References:
    - Eames, M.E. et al. (2024). "A revised morphing algorithm for
      creating future weather for building performance evaluation."
    - Hamann, S. et al. (2025). "Advanced Weather Data Morphing for
      Future Climate-Based Building Simulation."
"""

import numpy as np


class BTWSMorpher:
    """
    Bounded Temperature Weighted Stretch (BTWS) morphing algorithm.
    
    This morpher operates on DAILY arrays (24 hourly values) and uses
    a non-linear transfer function to distribute the climate change 
    signal across the diurnal temperature profile while exactly 
    preserving the projected min, max, and mean changes.
    
    Also applicable to Global Horizontal Radiation (GHR) morphing
    using the same normalization and transfer function approach.
    
    Parameters:
        m (float): Exponent for the lower bound in the transfer function.
                   Higher values shift the peak transformation toward 
                   the maximum. Default: 2.
        n (float): Exponent for the upper bound in the transfer function.
                   Higher values shift the peak transformation toward 
                   the minimum. Default: 2.
        min_dtr (float): Minimum diurnal temperature range (°C) below 
                         which the algorithm falls back to a simple 
                         shift. This prevents numerical instability in
                         tropical climates with narrow DTR. Default: 1.0.
    """

    def __init__(self, m=2, n=2, min_dtr=1.0):
        self.m = m
        self.n = n
        self.min_dtr = min_dtr

    # ── Core Algorithm Components ───────────────────────────────

    def normalize(self, values, v_min, v_max):
        """
        Normalizes values to [0, 1] range.
        Equation (1): x = (T - min(T)) / (max(T) - min(T))
        
        Maps minimum → 0 and maximum → 1 to create a uniform scale
        for applying the transfer function.
        
        :param values: np.ndarray of hourly values.
        :param v_min:  Minimum value (daily min).
        :param v_max:  Maximum value (daily max).
        :return:       np.ndarray of normalized values in [0, 1].
        """
        denom = v_max - v_min
        if abs(denom) < 1e-9:
            return np.full_like(values, 0.5, dtype=float)
        return (values - v_min) / denom

    def denormalize(self, x_prime, v_min_prime, v_max_prime):
        """
        Converts normalized values back to physical units.
        Equation (2): T' = T'_min + x' · (T'_max - T'_min)
        
        :param x_prime:      np.ndarray of transformed normalized values.
        :param v_min_prime:  Future minimum value.
        :param v_max_prime:  Future maximum value.
        :return:             np.ndarray of morphed physical values.
        """
        return v_min_prime + x_prime * (v_max_prime - v_min_prime)

    def transfer_function(self, x):
        """
        Calculates the transfer function (weighting curve).
        Equation (3): g = x^m · (1 - x)^n
        
        Properties:
            - g(0) = 0 : preserves the minimum temperature
            - g(1) = 0 : preserves the maximum temperature
            - g peaks between 0 and 1 : maximum transformation 
              in the middle of the range
            - Smooth, continuous transitions between extremes
        
        :param x: np.ndarray of normalized values in [0, 1].
        :return:  np.ndarray of transfer function values.
        """
        # Clip to [0, 1] to prevent NaN from negative bases
        x_safe = np.clip(x, 0.0, 1.0)
        return (x_safe ** self.m) * ((1 - x_safe) ** self.n)

    def scaling_factor(self, T_mean_prime, T_min_prime, T_max_prime,
                       T_mean, T_min, T_max):
        """
        Calculates the scaling factor S that controls how much 
        the transfer function stretches or compresses the distribution.
        
        Equation (4):
            S = [(T'_mean - T'_min) / (T'_max - T'_min)] × 
                [(T_max - T_min) / (T_mean - T_min)] - 1
        
        Interpretation:
            - S > 0 : distribution is stretched (more spread)
            - S < 0 : distribution is compressed (less spread)
            - S = 0 : no change needed
        
        :param T_mean_prime: Future mean value.
        :param T_min_prime:  Future minimum value.
        :param T_max_prime:  Future maximum value.
        :param T_mean:       Baseline mean value.
        :param T_min:        Baseline minimum value.
        :param T_max:        Baseline maximum value.
        :return:             Scaling factor S (scalar).
        """
        future_range = T_max_prime - T_min_prime
        baseline_range = T_max - T_min
        mean_to_min = T_mean - T_min

        # Guard against division by zero
        if abs(future_range) < 1e-9 or abs(mean_to_min) < 1e-9:
            return 0.0

        part1 = (T_mean_prime - T_min_prime) / future_range
        part2 = baseline_range / mean_to_min
        return (part1 * part2) - 1.0

    # ── Main Morphing Methods ───────────────────────────────────

    def morph_temperature(self, hourly_temps, delta_mean, delta_max, delta_min):
        """
        Morphs a DAILY array of hourly temperatures using the full
        BTWS algorithm. Independently preserves projected changes in
        daily minimum, maximum, and mean temperatures.
        
        :param hourly_temps: np.ndarray of 24 hourly temperatures for 
                             a single day (°C).
        :param delta_mean:   Projected change in mean daily temperature (°C).
        :param delta_max:    Projected change in daily maximum temperature (°C).
        :param delta_min:    Projected change in daily minimum temperature (°C).
        :return:             np.ndarray of 24 morphed hourly temperatures (°C).
        """
        hourly_temps = np.asarray(hourly_temps, dtype=float)

        T_min = np.min(hourly_temps)
        T_max = np.max(hourly_temps)
        T_mean = np.mean(hourly_temps)

        # Future target values
        T_min_prime = T_min + delta_min
        T_max_prime = T_max + delta_max
        T_mean_prime = T_mean + delta_mean

        # ── Fallback for narrow diurnal range ───────────────────
        # In tropical climates (e.g., Thailand), DTR can be as low 
        # as 3-5°C. When DTR < min_dtr, normalization becomes 
        # unstable. Fall back to a simple mean shift.
        diurnal_range = T_max - T_min
        if diurnal_range < self.min_dtr:
            return hourly_temps + delta_mean

        # ── Step 1: Normalize to [0, 1] ─────────────────────────
        x = self.normalize(hourly_temps, T_min, T_max)

        # ── Step 2: Calculate scaling factor S ──────────────────
        S = self.scaling_factor(
            T_mean_prime, T_min_prime, T_max_prime,
            T_mean, T_min, T_max
        )

        # ── Step 3: Transfer function & daily means ─────────────
        g = self.transfer_function(x)
        g_mean = np.mean(g)
        x_mean = np.mean(x)

        # ── Step 4: Apply bounded transformation ────────────────
        # Equation (5): x' = x + (S · x̄ · g) / ḡ
        if abs(g_mean) < 1e-12:
            x_prime = x
        else:
            x_prime = x + (S * x_mean * g) / g_mean

        # Clip to [0, 1] to enforce physical bounds
        x_prime = np.clip(x_prime, 0.0, 1.0)

        # ── Step 5: Denormalize to physical temperatures ────────
        T_prime = self.denormalize(x_prime, T_min_prime, T_max_prime)

        return T_prime

    def morph_solar_radiation(self, hourly_ghr, delta_mean, delta_max, delta_min):
        """
        Morphs a DAILY array of hourly Global Horizontal Radiation 
        using the BTWS algorithm, following the same normalization
        and transfer function approach as temperature.
        
        Important: This morphs GHR only. For physical consistency, 
        DNI and DHI should be recalculated afterwards using:
            GHI = DNI · cos(θ) + DHI
        
        :param hourly_ghr:  np.ndarray of 24 hourly GHR values (Wh/m²).
        :param delta_mean:  Projected change in mean daily GHR (Wh/m²).
        :param delta_max:   Projected change in daily max GHR (Wh/m²).
        :param delta_min:   Projected change in daily min GHR (Wh/m²).
                            Usually 0 since nighttime radiation is always 0.
        :return:            np.ndarray of 24 morphed GHR values, clamped ≥ 0.
        """
        hourly_ghr = np.asarray(hourly_ghr, dtype=float)

        # Separate daytime and nighttime hours
        # (Nighttime GHR = 0; morphing only applies to daytime)
        daytime_mask = hourly_ghr > 0
        result = hourly_ghr.copy()

        if not np.any(daytime_mask):
            return result  # All nighttime, nothing to morph

        daytime_vals = hourly_ghr[daytime_mask]
        R_min = np.min(daytime_vals)
        R_max = np.max(daytime_vals)
        R_mean = np.mean(daytime_vals)

        R_min_prime = max(0, R_min + delta_min)
        R_max_prime = max(0, R_max + delta_max)
        R_mean_prime = max(0, R_mean + delta_mean)

        rad_range = R_max - R_min
        if rad_range < 1.0:  # Very narrow range, just shift
            result[daytime_mask] = np.maximum(0, daytime_vals + delta_mean)
            return result

        # Apply BTWS algorithm to daytime values only
        x = self.normalize(daytime_vals, R_min, R_max)
        S = self.scaling_factor(R_mean_prime, R_min_prime, R_max_prime,
                                R_mean, R_min, R_max)
        g = self.transfer_function(x)
        g_mean = np.mean(g)
        x_mean = np.mean(x)

        if abs(g_mean) < 1e-12:
            x_prime = x
        else:
            x_prime = x + (S * x_mean * g) / g_mean

        x_prime = np.clip(x_prime, 0.0, 1.0)
        morphed_daytime = self.denormalize(x_prime, R_min_prime, R_max_prime)

        result[daytime_mask] = np.maximum(0, morphed_daytime)
        return result

    # ── Diagnostics ─────────────────────────────────────────────

    def validate_morph(self, baseline, morphed, delta_mean, delta_max, delta_min):
        """
        Validates that the morphed output matches expected targets.
        Returns a dict with actual vs expected changes.
        
        :param baseline: np.ndarray of original daily values.
        :param morphed:  np.ndarray of morphed daily values.
        :param delta_mean: Expected change in mean.
        :param delta_max:  Expected change in max.
        :param delta_min:  Expected change in min.
        :return:           dict with validation metrics.
        """
        return {
            'baseline_min':  float(np.min(baseline)),
            'baseline_mean': float(np.mean(baseline)),
            'baseline_max':  float(np.max(baseline)),
            'morphed_min':   float(np.min(morphed)),
            'morphed_mean':  float(np.mean(morphed)),
            'morphed_max':   float(np.max(morphed)),
            'expected_min':  float(np.min(baseline) + delta_min),
            'expected_mean': float(np.mean(baseline) + delta_mean),
            'expected_max':  float(np.max(baseline) + delta_max),
            'error_min':     float(np.min(morphed) - (np.min(baseline) + delta_min)),
            'error_mean':    float(np.mean(morphed) - (np.mean(baseline) + delta_mean)),
            'error_max':     float(np.max(morphed) - (np.max(baseline) + delta_max)),
        }


# ── Example Usage ───────────────────────────────────────────────
if __name__ == "__main__":

    print("=" * 60)
    print("BTWS MORPHER — Bounded Temperature Weighted Stretch Demo")
    print("=" * 60)

    # ── Test 1: Vienna-like temperate day (wide DTR) ────────────
    print("\n--- Test 1: Vienna-like Day (Wide DTR ~12°C) ---")
    time = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    vienna_temps = 15.0 - 6.0 * np.cos(time)  # min ~9, max ~21

    morpher = BTWSMorpher(m=2, n=2)
    morphed_vienna = morpher.morph_temperature(vienna_temps, 2.5, 3.0, 2.0)
    v = morpher.validate_morph(vienna_temps, morphed_vienna, 2.5, 3.0, 2.0)

    print(f"  Baseline  Min/Mean/Max: {v['baseline_min']:.1f} / "
          f"{v['baseline_mean']:.1f} / {v['baseline_max']:.1f} °C")
    print(f"  Morphed   Min/Mean/Max: {v['morphed_min']:.1f} / "
          f"{v['morphed_mean']:.1f} / {v['morphed_max']:.1f} °C")
    print(f"  Expected  Min/Mean/Max: {v['expected_min']:.1f} / "
          f"{v['expected_mean']:.1f} / {v['expected_max']:.1f} °C")
    print(f"  Errors    Min/Mean/Max: {v['error_min']:.3f} / "
          f"{v['error_mean']:.3f} / {v['error_max']:.3f} °C")

    # ── Test 2: Bangkok-like tropical day (narrow DTR) ──────────
    print("\n--- Test 2: Bangkok-like Day (Narrow DTR ~7°C) ---")
    bangkok_temps = 31.5 - 3.5 * np.cos(time)  # min ~28, max ~35

    morphed_bangkok = morpher.morph_temperature(bangkok_temps, 4.6, 5.3, 4.4)
    b = morpher.validate_morph(bangkok_temps, morphed_bangkok, 4.6, 5.3, 4.4)

    print(f"  Baseline  Min/Mean/Max: {b['baseline_min']:.1f} / "
          f"{b['baseline_mean']:.1f} / {b['baseline_max']:.1f} °C")
    print(f"  Morphed   Min/Mean/Max: {b['morphed_min']:.1f} / "
          f"{b['morphed_mean']:.1f} / {b['morphed_max']:.1f} °C")
    print(f"  Expected  Min/Mean/Max: {b['expected_min']:.1f} / "
          f"{b['expected_mean']:.1f} / {b['expected_max']:.1f} °C")
    print(f"  Errors    Min/Mean/Max: {b['error_min']:.3f} / "
          f"{b['error_mean']:.3f} / {b['error_max']:.3f} °C")

    # ── Test 3: Edge case — very narrow DTR (monsoon day) ───────
    print("\n--- Test 3: Monsoon Day (DTR < 1°C — Fallback) ---")
    monsoon_temps = 29.0 + 0.3 * np.random.randn(24)  # nearly constant

    morphed_monsoon = morpher.morph_temperature(monsoon_temps, 3.0, 3.2, 2.8)
    m_val = morpher.validate_morph(monsoon_temps, morphed_monsoon, 3.0, 3.2, 2.8)

    print(f"  Baseline  Min/Mean/Max: {m_val['baseline_min']:.1f} / "
          f"{m_val['baseline_mean']:.1f} / {m_val['baseline_max']:.1f} °C")
    print(f"  Morphed   Min/Mean/Max: {m_val['morphed_min']:.1f} / "
          f"{m_val['morphed_mean']:.1f} / {m_val['morphed_max']:.1f} °C")
    print(f"  (Fallback to simple shift applied — DTR too narrow)")
