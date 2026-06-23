import numpy as np
import pandas as pd

class BTWSMorpher:
    """
    Implements the Bounded Temperature Weighted Stretch (BTWS) morphing algorithm
    based on Eames et al. (2024) and Hamann et al. (2025).
    """
    def __init__(self, m=2, n=2):
        self.m = m
        self.n = n

    def transfer_function(self, x):
        """
        Calculates the transfer function (weighting curve).
        Equation (3): g = x^m * (1 - x)^n
        Provides maximum transformation in the middle of the range, and 
        preserves the physical limits (0 and 1).
        """
        return (x ** self.m) * ((1 - x) ** self.n)

    def morph_temperature(self, hourly_temps, delta_mean, delta_max, delta_min):
        """
        Morphs a daily array of hourly temperatures.
        
        :param hourly_temps: Array of 24 hourly temperatures for a specific day.
        :param delta_mean: Projected change in mean daily temperature.
        :param delta_max: Projected change in daily maximum temperature.
        :param delta_min: Projected change in daily minimum temperature.
        :return: Morphed array of 24 hourly temperatures.
        """
        T_min = np.min(hourly_temps)
        T_max = np.max(hourly_temps)
        T_mean = np.mean(hourly_temps)
        
        # Future targets
        T_min_prime = T_min + delta_min
        T_max_prime = T_max + delta_max
        T_mean_prime = T_mean + delta_mean
        
        # If there's no diurnal range (e.g. constant temp), avoid division by zero
        if T_max == T_min:
            return hourly_temps + delta_mean

        # 1. Normalization (Eq. 1)
        x = (hourly_temps - T_min) / (T_max - T_min)
        
        # 2. Scaling factor (Eq. 4)
        # S = [(T'_mean - T'_min) / (T'_max - T'_min)] * [(max(T) - min(T)) / (mean(T) - min(T))] - 1
        S_part1 = (T_mean_prime - T_min_prime) / (T_max_prime - T_min_prime)
        S_part2 = (T_max - T_min) / (T_mean - T_min)
        S = (S_part1 * S_part2) - 1
        
        # 3. Transfer Function values for this day
        g = self.transfer_function(x)
        g_mean = np.mean(g)
        x_mean = np.mean(x)
        
        # 4. Apply Transformation (Eq. 5)
        # Using the formulation x' = x + (S * x_mean * g) / g_mean 
        # (Handling potential division by zero if g_mean is 0)
        if g_mean == 0:
            x_prime = x
        else:
            x_prime = x + (S * x_mean * g) / g_mean
            
        # Ensure x_prime stays bounded between 0 and 1
        x_prime = np.clip(x_prime, 0.0, 1.0)
        
        # 5. Denormalization (Eq. 2)
        # T' = T'_min + x' * (T'_max - T'_min)
        T_prime = T_min_prime + x_prime * (T_max_prime - T_min_prime)
        
        return T_prime

# Example Usage
if __name__ == "__main__":
    # Simulate a hot Bangkok day: min 28°C, max 35°C, mean 31.5°C
    np.random.seed(42)
    # create a simple sinusoidal temperature profile for 24 hours
    time = np.linspace(0, 2 * np.pi, 24)
    baseline_temps = 31.5 - 3.5 * np.cos(time) 
    
    # 2070 SSP5-8.5 Deltas (Hypothetical)
    d_mean = 4.6  # Mean rises by 4.6
    d_max = 5.3   # Max rises by 5.3
    d_min = 4.4   # Min rises by 4.4
    
    morpher = BTWSMorpher(m=2, n=2)
    morphed_temps = morpher.morph_temperature(baseline_temps, d_mean, d_max, d_min)
    
    print("Baseline Min/Mean/Max: {:.1f} / {:.1f} / {:.1f}".format(
        np.min(baseline_temps), np.mean(baseline_temps), np.max(baseline_temps)
    ))
    print("Morphed  Min/Mean/Max: {:.1f} / {:.1f} / {:.1f}".format(
        np.min(morphed_temps), np.mean(morphed_temps), np.max(morphed_temps)
    ))
    print("Expected Min/Mean/Max: {:.1f} / {:.1f} / {:.1f}".format(
        np.min(baseline_temps)+d_min, np.mean(baseline_temps)+d_mean, np.max(baseline_temps)+d_max
    ))
