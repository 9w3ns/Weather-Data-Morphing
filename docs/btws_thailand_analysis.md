# Applying the BTWS Method for Thailand's Climate

## Overview

This document analyzes the feasibility of applying the **Bounded Temperature Weighted Stretch (BTWS)** morphing method — as described in *"Advanced Weather Data Morphing for Future Climate-Based Building Simulation"* (Hamann et al., 2025) — to **Thailand's tropical climate**, which differs drastically from the Vienna (temperate/continental) context in which the tool was developed and tested.

**Short answer:** The core algorithm will work, but several aspects need modification or extra care due to fundamental climate differences between Vienna and Thailand.

---

## Key Climate Differences: Vienna vs Thailand

| Feature | Vienna (Temperate) | Thailand (Tropical) |
|---|---|---|
| Temperature range | −8.9 °C to 34.7 °C (~44 °C span) | ~18 °C to 40 °C (~22 °C span) |
| Diurnal temperature range | Large (10–15 °C) | **Narrow (5–8 °C)** |
| Seasonal variation | 4 distinct seasons | 3 seasons (hot/rainy/cool), less variation |
| Humidity | Moderate, variable | **Persistently high (70–90% RH)** |
| Solar radiation | Moderate, highly seasonal | **High year-round (~4.75 kWh/m²/day)** |
| Precipitation pattern | Distributed year-round | **Intense monsoon (May–Oct)** |
| Dominant building load | Heating in winter | **Cooling year-round (sensible + latent)** |

---

## Problems & Required Modifications

### 1. 🔴 Normalization Breaks with Narrow Diurnal Temperature Range

**This is the biggest issue.** The BTWS normalization formula is:

$$x = \frac{T - \min(T)}{\max(T) - \min(T)}$$

When Thailand's daily max–min difference is very small (5–8 °C vs Vienna's 10–15 °C), the denominator becomes tiny. This causes:

- Small absolute errors to be **amplified** into large normalized errors
- The transfer function $g = x^m(1-x)^n$ and scaling factor $S$ to become **numerically unstable**
- Morphed temperatures to overshoot or produce unrealistic hourly profiles

The scaling factor calculation is particularly sensitive:

$$S = \left(\frac{T'_{mean} - T'_{min}}{T'_{max} - T'_{min}}\right) \times \left(\frac{\max(T) - \min(T)}{mean(T) - \min(T)}\right) - 1$$

When the temperature range is narrow, small changes in projected $\Delta T_{tasmax}$ or $\Delta T_{tasmin}$ produce disproportionately large values of $S$, leading to excessive stretching or compression.

> [!WARNING]
> **Modification needed:** Add numerical guards (minimum denominator threshold), or consider using a **Distribution Adjusted Temporal Mapping (DATM)** approach instead of BTWS for days with very narrow diurnal range (e.g., DTR < 6 °C).

---

### 2. 🔴 Humidity–Temperature Coupling

Thailand's climate is **humidity-dominated** — building energy loads are driven as much by latent heat (moisture) as sensible heat (temperature). The paper's tool morphs temperature and humidity independently using different methods (BTWS for temperature, Belcher/Jentsch for relative humidity). In tropical climates:

- Shifting dry bulb temperature without a **non-linear adjustment to vapor pressure** breaks the psychrometric relationship
- Relative humidity can exceed 100% or drop to unrealistic levels after morphing
- Dew point temperature can end up **above** dry bulb temperature (physically impossible)
- Since RH is a ratio dependent on saturated vapor pressure — which changes **exponentially** with temperature — linear morphing approaches produce significant errors in high-humidity environments

> [!WARNING]
> **Modification needed:** Add **psychrometric consistency checks** after morphing. Consider morphing absolute humidity (specific humidity or vapor pressure) instead of relative humidity, then recalculating RH from the morphed temperature. Enforce the constraint that dew point ≤ dry bulb at all timesteps.

---

### 3. 🟡 Solar Radiation — Already Problematic, Worse in Tropics

The paper already identified solar radiation consistency issues in Vienna (27.26% of hours had DHI > GHI). In Thailand, these problems are compounded:

- Solar radiation is **high and relatively constant year-round** — less seasonal variation to anchor the morphing
- Cloud cover is dominated by **convective monsoon patterns**, not the gradual seasonal shifts the algorithm assumes
- The narrow range of solar radiation variation means the same normalization instability seen in temperature applies here
- The physical relationship $GHI = DNI \cdot \cos(\theta) + DHI$ **must** be maintained for accurate building simulation, as solar gain is the dominant cooling load driver in Thailand

> [!IMPORTANT]
> **Modification needed:** Morph DNI and DHI **together with GHI** to maintain physical consistency. Consider separate treatment for dry season vs monsoon season. Apply the constraint $DHI \leq GHI$ and recalculate DNI from the relationship after morphing.

> [!NOTE]
> **Status:** Implemented as Phase 3 in `epw_morphing_engine.py` (ratio-scaling DNI/DHI by `morphed_GHI / baseline_GHI`) and validated in `morphing/validate_phase3.py` — see `docs/belcher_vs_cura_validation.md`. The `DHI \leq GHI` constraint is enforced, but the current clip does not re-solve DNI afterward, so the closure identity is not guaranteed at the ~6% of hours where the clip fires. In the Bangkok baseline this only affects near-zero-GHI edge hours, but under Thailand's monsoon cloud cover (this document's premise) genuine high-irradiance DHI > GHI violations are more likely — recalculating `DNI' = (GHI' - DHI') / cos(θ)` after the clip should be prioritized before relying on this for monsoon months.

---

### 4. 🟡 Precipitation: Monsoon Intensity Not Captured

The Belcher/Jentsch method uses **monthly mean change factors** which smooth out sub-daily variability. Thailand's monsoon produces:

- Extreme short-duration rainfall events (50–100+ mm/hour)
- Rapid alternation between dry and wet periods within a single day
- Highly localized convective storms that are not represented in coarse GCM data

Monthly morphing factors will shift total precipitation volumes reasonably, but **extreme event intensity will be underrepresented**. This matters for:

- Building drainage and flood resilience design
- Moisture ingress and envelope performance
- Urban heat island mitigation assessments

> [!NOTE]
> **Modification needed:** Supplement monthly morphing with stochastic rainfall generation or sub-daily intensity scaling for monsoon months (May–October). Consider separating dry-season and wet-season morphing factors rather than using uniform monthly averages.

---

### 5. 🟡 GCM Selection and Resolution

The paper uses a single GCM (UKESM1-0-LL). For Thailand:

- Tropical regions have **higher inter-model disagreement** between GCMs, especially for precipitation and cloud cover
- A single model could project anything from increased to decreased monsoon rainfall depending on its representation of ENSO, Indian Ocean Dipole, and monsoon dynamics
- WorldClim's 2.5-minute resolution (~4.5 km) may miss Thailand's complex topography:
  - Northern mountainous regions
  - Coastal effects along the Gulf of Thailand and Andaman Sea
  - Urban Heat Island effects in Bangkok and other major cities
- The bias correction applied by WorldClim is calibrated against global station data, which may be sparse in parts of Thailand

> [!IMPORTANT]
> **Modification needed:** Use a **multi-GCM ensemble** (at least 5–10 models) to capture the range of uncertainty. Consider bias-correcting against **Thai Meteorological Department (TMD)** station data. For Bangkok and other urban areas, consider coupling with an Urban Weather Generator to account for UHI effects.

---

### 6. 🟢 Additional Variables Needed for Tropical Building Simulation

The current tool morphs 6 variables (Dry Bulb Temperature, Dew Point Temperature, Precipitable Water, Relative Humidity, Wind Speed, and Global Horizontal Radiation). For Thailand building simulation, additional variables become critical:

| Variable | Why It Matters for Thailand |
|---|---|
| **Direct Normal Irradiance (DNI)** | Must be co-morphed with GHI for solar gain accuracy |
| **Diffuse Horizontal Irradiance (DHI)** | Dominates under cloudy/monsoon skies; must be co-morphed |
| **Opaque Sky Cover** | Drives cooling load during monsoon; affects radiant exchange |
| **Wet Bulb Temperature** | Critical for cooling tower and HVAC sizing in humid climates |
| **Wind Direction** | Important for natural ventilation design, a key passive strategy in Thailand |

> [!NOTE]
> **Modification needed:** Expand the set of morphed variables to include at minimum DNI and DHI (co-morphed with GHI). Consider adding opaque sky cover and wind direction for comprehensive tropical building simulation.

---

## Summary: Modification Priority

| Priority | Issue | Action |
|---|---|---|
| **Critical** | Narrow diurnal range → normalization instability | Add minimum denominator guards; consider DATM for low-DTR days |
| **Critical** | Humidity–temperature coupling breaks psychrometrics | Morph absolute humidity, recalculate RH; add psychrometric consistency checks |
| **Critical** | Single GCM unreliable for tropics | Use multi-model ensemble (5–10 GCMs) |
| **High** | Solar radiation components inconsistent | Co-morph GHI, DNI, DHI together; enforce physical constraints |
| **High** | Monsoon extremes smoothed out | Seasonal separation of morphing factors; stochastic sub-daily scaling |
| **Medium** | GCM spatial resolution too coarse for local effects | Bias-correct with local Thai Meteorological Department station data |
| **Medium** | UHI effects unrepresented | Couple with Urban Weather Generator for Bangkok, Chiang Mai, etc. |
| **Low** | Missing variables for tropical simulation | Add sky cover, expand radiation components, add wind direction |

---

## Conclusion

The **mathematical core** of the BTWS method — normalize → transfer function → scale → denormalize — is sound and climate-agnostic. The algorithm itself does not inherently fail in tropical climates. However, the **boundary conditions, data coupling assumptions, and input data quality** become much more sensitive in tropical environments where:

1. Temperature ranges are narrow (normalization sensitivity)
2. Humidity dominates energy loads (psychrometric coupling)
3. Monsoon dynamics drive extreme precipitation and cloud patterns (sub-daily variability)
4. GCM uncertainty is higher in the tropics (model selection)

Addressing these issues — particularly the normalization guards, psychrometric consistency, and multi-GCM ensemble — would make the tool applicable to Thailand and other tropical climates while maintaining the BTWS method's advantages over simpler shift-and-stretch approaches.

---

## References

- Hamann, S., Chronis, A., Taut, O., & Galanos, T. (2025). *Advanced Weather Data Morphing for Future Climate-Based Building Simulation.* Proc. of the 2025 Annual Modeling and Simulation Conference (ANNSIM 25).
- Eames, M. E., Xie, H., Mylona, A., Shilston, R., & Hacker, J. (2024). A revised morphing algorithm for creating future weather for building performance evaluation. *Building Services Engineering Research & Technology*, 45(1), 5–20.
- Belcher, S. E., Hacker, J. N., & Powell, D. S. (2005). Constructing design weather data for future climates. *Building Services Engineering Research and Technology*, 26(1), 49–61.
- Jentsch, M. F. (2012). Climate change weather file generators: Technical reference manual for the CCWeatherGen and CCWorldWeatherGen tools. University of Southampton.
- Rodrigues, E., Fernandez, M. S., & Carvalho, D. (2023). Future weather generator for building performance research. *Building and Environment*, 233, 1–13.
